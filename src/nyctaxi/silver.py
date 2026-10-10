from pyspark.sql import functions as F 
from pyspark.sql import SparkSession, DataFrame

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


    return df.select(*expr)


    


