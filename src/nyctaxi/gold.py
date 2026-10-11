from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

UNKNOWN_ID = -1          # unknown member: replaces a null foreign key
UNKNOWN_DESC = "Missing"


# Small code dimensions (payment, vendor, ratecode) from config/dimensions.yml
def build_code_dim(spark: SparkSession, mapping: dict, id_col: str, desc_col: str) -> DataFrame:
    """{1: "Credit card", ...} -> DataFrame (id_col int, desc_col string)."""
    rows = [(int(code), str(label)) for code, label in mapping.items()]
    return spark.createDataFrame(rows, f"{id_col} int, {desc_col} string")


# dim_location (from silver.taxi_zones) + unknown member
def build_dim_location(zones: DataFrame) -> DataFrame:
    unknown = zones.sparkSession.createDataFrame(
        [(UNKNOWN_ID, UNKNOWN_DESC, UNKNOWN_DESC, UNKNOWN_DESC)],
        "location_id int, borough string, zone string, service_zone string",
    )
    return (
        zones.select("location_id", "borough", "zone", "service_zone")
        .unionByName(unknown)
    )



# dim_date: one row per day, every day in [start, end] (also days without trips)
def date_bounds(trips: DataFrame) -> tuple:
    """Smallest pickup date and largest dropoff date in silver.trips."""
    row = trips.agg(
        F.min(F.to_date("pickup_ts")).alias("start"),
        F.max(F.to_date("dropoff_ts")).alias("end"),
    ).first()
    return row["start"], row["end"]


def build_dim_date(spark: SparkSession, start, end) -> DataFrame:
    days = spark.range(1).select(
        F.explode(F.sequence(F.lit(start), F.lit(end))).alias("full_date")
    )
    d = F.col("full_date")
    iso_dow = ((F.dayofweek(d) + 5) % 7) + 1          # 1 = Monday ... 7 = Sunday
    return days.select(
        F.date_format(d, "yyyyMMdd").cast("int").alias("date_id"),
        d.alias("full_date"),
        F.dayofmonth(d).alias("day"),
        F.date_format(d, "EEEE").alias("day_name"),
        F.month(d).alias("month"),
        F.date_format(d, "MMMM").alias("month_name"),
        F.quarter(d).alias("quarter"),
        F.year(d).alias("year"),
        iso_dow.alias("day_of_week"),
        (iso_dow >= 6).alias("is_weekend"),
    )



# dim_time: one row per second of the day (86,400 rows), time_id = HHMMSS
def build_dim_time(spark: SparkSession) -> DataFrame:
    s = F.col("id")
    hour = (s / 3600).cast("int")
    minute = ((s % 3600) / 60).cast("int")
    second = (s % 60).cast("int")
    return spark.range(86400).select(
        (hour * 10000 + minute * 100 + second).alias("time_id"),
        hour.alias("hour"),
        minute.alias("minute"),
        second.alias("second"),
        F.when(hour < 6, "Night")
        .when(hour < 12, "Morning")
        .when(hour < 18, "Afternoon")
        .otherwise("Evening")
        .alias("time_period"),
    )



# fact_trip: 1 trip per row
def _date_id(ts: str):
    return F.date_format(ts, "yyyyMMdd").cast("int")


def _time_id(ts: str):
    return F.hour(ts) * 10000 + F.minute(ts) * 100 + F.second(ts)


def _fk(col: str):
    """Foreign key: null -> unknown member -1."""
    return F.coalesce(F.col(col), F.lit(UNKNOWN_ID)).cast("int")


def build_fact_trip(trips: DataFrame) -> DataFrame:
    """silver.trips -> fact_trip. Only keys + measures, no joins (Power BI does the joins)."""
    return trips.select(
        "trip_id",
        _date_id("pickup_ts").alias("pickup_date_id"),
        _time_id("pickup_ts").alias("pickup_time_id"),
        _date_id("dropoff_ts").alias("dropoff_date_id"),
        _time_id("dropoff_ts").alias("dropoff_time_id"),
        _fk("pu_location_id").alias("pickup_location_id"),
        _fk("do_location_id").alias("dropoff_location_id"),
        _fk("vendor_id").alias("vendor_id"),
        _fk("payment_type").alias("payment_id"),
        _fk("ratecode_id").alias("ratecode_id"),
        "passenger_count",
        "trip_distance",
        "trip_duration_min",
        "fare_amount",
        "extra",
        "mta_tax",
        "tip_amount",
        "tolls_amount",
        "improvement_surcharge",
        "congestion_surcharge",
        "airport_fee",
        "cbd_congestion_fee",
        "total_amount",
        # Revenue defined in ONE place. fare < 0 = Flex Fare rows whose money is meaningless.
        # Not yet excluded: reversed trips (is_reversed), ~1.7% overstatement -> see README.
        F.when(F.col("fare_amount") >= 0, F.col("total_amount")).otherwise(F.lit(0.0)).alias("revenue"),
        "taxi_type",
        "source_file",
        "ingestion_time",
    )



# Checks + role-playing views
# (fact column, dimension table, dimension key)
FOREIGN_KEYS = [
    ("pickup_date_id", "dim_date", "date_id"),
    ("dropoff_date_id", "dim_date", "date_id"),
    ("pickup_time_id", "dim_time", "time_id"),
    ("dropoff_time_id", "dim_time", "time_id"),
    ("pickup_location_id", "dim_location", "location_id"),
    ("dropoff_location_id", "dim_location", "location_id"),
    ("vendor_id", "dim_vendor", "vendor_id"),
    ("payment_id", "dim_payment", "payment_id"),
    ("ratecode_id", "dim_ratecode", "ratecode_id"),
]


def orphan_keys(fact: DataFrame, dim: DataFrame, fk_col: str, dim_key: str) -> DataFrame:
    """Fact keys that have no row in the dimension (must be empty). Returns key + count."""
    keys = dim.select(F.col(dim_key).alias(fk_col))
    return fact.join(keys, on=fk_col, how="left_anti").groupBy(fk_col).count()


def create_role_playing_views(spark: SparkSession, catalog: str) -> None:
    """dim_location plays two roles -> one view per role, columns renamed by role."""
    for role in ("pickup", "dropoff"):
        spark.sql(f"""
            CREATE OR REPLACE VIEW {catalog}.gold.dim_{role}_location AS
            SELECT location_id  AS {role}_location_id,
                   borough      AS {role}_borough,
                   zone         AS {role}_zone,
                   service_zone AS {role}_service_zone
            FROM {catalog}.gold.dim_location
        """)