from datetime import datetime

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    spark = (
        SparkSession.builder
        .master("local[1]")
        .appName("nyctaxi-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield spark
    spark.stop()


# Same columns as bronze.yellow_trips_raw (TLC parquet + Auto Loader columns)
YELLOW_BRONZE_SCHEMA = """
    VendorID int, tpep_pickup_datetime timestamp_ntz, tpep_dropoff_datetime timestamp_ntz,
    passenger_count bigint, trip_distance double, RatecodeID bigint, store_and_fwd_flag string,
    PULocationID int, DOLocationID int, payment_type bigint, fare_amount double, extra double,
    mta_tax double, tip_amount double, tolls_amount double, improvement_surcharge double,
    total_amount double, congestion_surcharge double, Airport_fee double, cbd_congestion_fee double,
    _rescued_data string, _source_file string, _ingestion_time timestamp
"""


def yellow_row(**overrides):
    """One valid yellow trip (2025-01). Pass column=value to change only what the test is about."""
    row = {
        "VendorID": 2,
        "tpep_pickup_datetime": datetime(2025, 1, 10, 8, 0),
        "tpep_dropoff_datetime": datetime(2025, 1, 10, 8, 20),
        "passenger_count": 1,
        "trip_distance": 3.0,
        "RatecodeID": 1,
        "store_and_fwd_flag": "N",
        "PULocationID": 161,
        "DOLocationID": 237,
        "payment_type": 1,
        "fare_amount": 15.0,
        "extra": 0.0,
        "mta_tax": 0.5,
        "tip_amount": 3.0,
        "tolls_amount": 0.0,
        "improvement_surcharge": 1.0,
        "total_amount": 22.75,
        "congestion_surcharge": 2.5,
        "Airport_fee": 0.0,
        "cbd_congestion_fee": 0.75,
        "_rescued_data": None,
        "_source_file": "dbfs:/Volumes/test/landing/raw_files/yellow/yellow_tripdata_2025-01.parquet",
        "_ingestion_time": datetime(2025, 3, 1),
    }
    row.update(overrides)
    return row


@pytest.fixture
def yellow_bronze(spark):
    """yellow_bronze({}, {"trip_distance": 0.0}) -> bronze DataFrame with 2 rows."""
    def make(*overrides):
        return spark.createDataFrame([yellow_row(**o) for o in overrides], YELLOW_BRONZE_SCHEMA)
    return make
