import re
from pyspark.sql import functions as F 
from pyspark.sql import SparkSession, DataFrame
from delta.tables import DeltaTable

# SILVER_SCHEMA using list instead of dict because list can maintain the order of columns
SILVER_SCHEMA = [
    ("pickup_ts",             "timestamp_ntz"),
    ("dropoff_ts",            "timestamp_ntz"),
    ("vendor_id",             "int"),
    ("passenger_count",       "int"),
    ("trip_distance",         "double"),
    ("ratecode_id",           "int"),
    ("store_and_fwd_flag",    "boolean"),
    ("pu_location_id",        "int"),
    ("do_location_id",        "int"),
    ("payment_type",          "int"),
    ("trip_type",             "int"),       # only green
    ("fare_amount",           "double"),
    ("extra",                 "double"),
    ("mta_tax",               "double"),
    ("tip_amount",            "double"),
    ("tolls_amount",          "double"),
    ("improvement_surcharge", "double"),
    ("congestion_surcharge",  "double"),
    ("airport_fee",           "double"),    # only yellow
    ("cbd_congestion_fee",    "double"),
    ("total_amount",          "double"),
]

# common columns of yellow and green
_COMMON = {
    "vendor_id":             "VendorID",
    "passenger_count":       "passenger_count",
    "trip_distance":         "trip_distance",
    "ratecode_id":           "RatecodeID",
    "store_and_fwd_flag":    "store_and_fwd_flag",
    "pu_location_id":        "PULocationID",
    "do_location_id":        "DOLocationID",
    "payment_type":          "payment_type",
    "fare_amount":           "fare_amount",
    "extra":                 "extra",
    "mta_tax":               "mta_tax",
    "tip_amount":            "tip_amount",
    "tolls_amount":          "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "congestion_surcharge":  "congestion_surcharge",
    "cbd_congestion_fee":    "cbd_congestion_fee",
    "total_amount":          "total_amount",
}


COLUMN_MAPPINGS = {
    "yellow": {
        **_COMMON,            # ** is to unpack a dict into another one
        "pickup_ts":   "tpep_pickup_datetime",
        "dropoff_ts":  "tpep_dropoff_datetime",
        "airport_fee": "Airport_fee",
    },
    "green": {
        **_COMMON,
        "pickup_ts":  "lpep_pickup_datetime",
        "dropoff_ts": "lpep_dropoff_datetime",
        "trip_type":  "trip_type",
    },
}

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# temporary columns: used while processing, never written to silver.trips
TEMP_COLUMNS = ["_rescued_data", "_file_month", "dq_reason"]


# this will be use for creating hash trip_id 
TRIP_ID_COLUMNS = [
    "taxi_type", "vendor_id", "pickup_ts", "dropoff_ts",
    "pu_location_id", "do_location_id", "trip_distance",
    "fare_amount", "total_amount", "payment_type",
] 

def _check_month(month: str) -> str:
    """month goes into delete conditions (MERGE, replaceWhere) -> must be exactly YYYY-MM."""
    month = month.strip()
    if not _MONTH_PATTERN.match(month):
        raise ValueError(f"month must be YYYY-MM, got: {month!r}")
    return month
 
 
def _check_taxi_type(taxi_type: str) -> str:
    taxi_type = taxi_type.lower().strip()
    if taxi_type not in COLUMN_MAPPINGS:
        raise ValueError(f"Invalid taxi_type: {taxi_type}")
    return taxi_type

# ====================================================Transformation===============================================

def standardize(df: DataFrame, taxi_type: str) -> DataFrame:
    taxi_type = taxi_type.lower().strip()

    if taxi_type not in ("yellow", "green"):
        raise ValueError(f"Invalid taxi_type: {taxi_type}")

    mapping = COLUMN_MAPPINGS[taxi_type]
    expr = []

    for name, dtype in SILVER_SCHEMA:
        if name == "store_and_fwd_flag":
            src = F.col("store_and_fwd_flag")
            expr.append(
                F.when(src == "Y", True)
                .when(src == "N", False).alias(name)
            )
        elif name in mapping:
            expr.append(F.col(mapping[name]).cast(dtype).alias(name))
        else:
            expr.append(F.lit(None).cast(dtype).alias(name))
        
    expr.append(F.lit(taxi_type).alias("taxi_type"))
    expr.append(F.col("_source_file").alias("source_file"))
    expr.append(F.col("_ingestion_time").alias("ingestion_time"))

    if "_rescued_data" in df.columns:
        expr.append(F.col("_rescued_data"))
    else:
        expr.append(F.lit(None).cast("string").alias("_rescued_data"))


    return df.select(*expr)


def standardize_zone(df: DataFrame) -> DataFrame:
    return df.select(
        F.col("LocationID").cast("int").alias("location_id"),
        F.col("Borough").cast("string").alias("borough"),
        F.col("Zone").cast("string").alias("zone"),
        F.col("service_zone").cast("string").alias("service_zone")
    )

def add_derived(df: DataFrame) -> DataFrame:
    return (df
        .withColumn(
            "trip_duration_min",
            (F.unix_timestamp(df.dropoff_ts) - F.unix_timestamp(df.pickup_ts)) / 60
        ) 
        
        .withColumn(
            "_file_month",
            F.to_date(F.regexp_extract("source_file", r"(\d{4}-\d{2})\.parquet$", 1), "yyyy-MM")
        )
    )



def add_reject_reason(df: DataFrame) -> DataFrame:
    in_file_month = F.to_date("pickup_ts").between(
        F.date_sub(F.col("_file_month"), 1),
        F.add_months(F.col("_file_month"), 1)
    )

    duration = F.col("trip_duration_min")
    distance = F.col("trip_distance")

    return df.withColumn(
        "dq_reason",                                # data-quality if this column has the null value, it means it passed all the data quality check
        F.when(
            F.col("_rescued_data").isNotNull(),
            "schema_mismatch"
        )
        .when(
            F.col("_file_month").isNull()
            | F.col("pickup_ts").isNull(),
            "missing_file_month_or_pickup_ts"
        )
        .when(
            ~in_file_month,
            "pickup_outside_file_month"
        )
        .when(
            F.col("dropoff_ts").isNull()
            | duration.isNull()
            | (duration <= 0)
            | (duration > 360),
            "invalid_trip_duration"
        )
        .when(
            distance.isNull() | (distance <= 0) | (distance > 200),
            "invalid_trip_distance"
        )
        .when(
            F.col("total_amount").isNull(),
            "missing_total_amount"
        )
        .when(
            F.col("total_amount") < 0,
            "negative_total_amount_review"
        )
    )

def add_trip_id(df: DataFrame) -> DataFrame:
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in TRIP_ID_COLUMNS]
    return df.withColumn("trip_id", F.sha2(F.concat_ws("|", *parts), 256))



def build_silver_trips(df: DataFrame, taxi_type: str, month: str) -> DataFrame:
    taxi_type = _check_taxi_type(taxi_type)
    month = _check_month(month)

    one_month = df.filter(F.col("_source_file").endswith(f"_{month}.parquet"))
    if one_month.isEmpty():
        raise ValueError(f"No Bronze rows for {taxi_type} {month}")

    return add_trip_id(add_reject_reason(add_derived(standardize(one_month, taxi_type))))


def split_valid_rejected(tagged: DataFrame) -> tuple[DataFrame, DataFrame]:
    """dq_reason null -> silver.trips, otherwise -> silver.trips_quarantine."""
    valid = (
        tagged.filter(F.col("dq_reason").isNull())
        .drop(*TEMP_COLUMNS)
        .dropDuplicates(["trip_id"])        # MERGE fails if two source rows share a trip_id
    )

    rejected = (
        tagged.filter(F.col("dq_reason").isNotNull())
        .withColumnRenamed("_file_month", "file_month")   # kept for replaceWhere
    )

    return valid, rejected


# ===================================Write=======================================


def merge_trips(spark: SparkSession, valid: DataFrame, table: str, taxi_type: str, month: str) -> None:
    """Upsert one source x one month into silver.trips.
    - same trip_id -> update
    - new trip_id  -> insert
    - row of THIS taxi_type and THIS month no longer in the batch -> delete
    """
    taxi_type = _check_taxi_type(taxi_type)
    month = _check_month(month)
 
    if not spark.catalog.tableExists(table):
        valid.write.saveAsTable(table)
        return
 
    (
        DeltaTable.forName(spark, table).alias("t")
        .merge(valid.alias("s"), "t.trip_id = s.trip_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .whenNotMatchedBySourceDelete(
            condition=f"t.taxi_type = '{taxi_type}' AND t.source_file LIKE '%_{month}.parquet'"
        )
        .execute()
    )
 
 
def write_quarantine(spark: SparkSession, rejected: DataFrame, table: str, taxi_type: str, month: str) -> None:
    """Replace rejected rows of one source x one month (re-run does not duplicate)."""
    taxi_type = _check_taxi_type(taxi_type)
    month = _check_month(month)
 
    if not spark.catalog.tableExists(table):
        rejected.write.saveAsTable(table)
        return
 
    (
        rejected.write.mode("overwrite")
        .option("replaceWhere", f"taxi_type = '{taxi_type}' AND file_month = DATE'{month}-01'")
        .saveAsTable(table)
    )


