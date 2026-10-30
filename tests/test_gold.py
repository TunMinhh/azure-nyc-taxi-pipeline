from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from nyctaxi.gold import (
    FOREIGN_KEYS,
    UNKNOWN_ID,
    build_code_dim,
    build_dim_date,
    build_dim_location,
    build_dim_time,
    build_fact_trip,
    date_bounds,
    orphan_keys,
)
from nyctaxi.silver import build_silver_trips, split_valid_rejected

DIMENSIONS_YML = Path(__file__).resolve().parents[1] / "config" / "dimensions.yml"


def silver_trips(yellow_bronze, *overrides):
    """Bronze rows -> valid silver.trips rows (same path as 03_silver)."""
    valid, _ = split_valid_rejected(build_silver_trips(yellow_bronze(*overrides), "yellow", "2025-01"))
    return valid


@pytest.fixture
def dims_config():
    with open(DIMENSIONS_YML) as f:
        return yaml.safe_load(f)


@pytest.fixture
def zones(spark):
    return spark.createDataFrame(
        [(161, "Manhattan", "Midtown Center", "Yellow Zone"),
         (237, "Manhattan", "Upper East Side South", "Yellow Zone")],
        "location_id int, borough string, zone string, service_zone string",
    )


# ---------- small dimensions ----------

def test_code_dim_from_config_has_unknown_member(spark, dims_config):
    dim = build_code_dim(spark, dims_config["payment"], "payment_id", "payment_desc")
    labels = {r.payment_id: r.payment_desc for r in dim.collect()}
    assert labels[UNKNOWN_ID] == "Missing"
    assert labels[0] == "Flex Fare trip"
    assert dict(dim.dtypes) == {"payment_id": "int", "payment_desc": "string"}


def test_dim_location_adds_unknown_member(zones):
    dim = build_dim_location(zones)
    assert dim.count() == 3
    unknown = dim.filter(f"location_id = {UNKNOWN_ID}").first()
    assert (unknown.borough, unknown.zone) == ("Missing", "Missing")


# ---------- dim_time ----------

def test_dim_time_has_one_row_per_second(spark):
    dim = build_dim_time(spark)
    assert dim.count() == 86400
    assert dim.select("time_id").distinct().count() == 86400


@pytest.mark.parametrize("time_id, hour, minute, second, period", [
    (0, 0, 0, 0, "Night"),
    (55959, 5, 59, 59, "Night"),
    (60000, 6, 0, 0, "Morning"),
    (120000, 12, 0, 0, "Afternoon"),
    (180000, 18, 0, 0, "Evening"),
    (235959, 23, 59, 59, "Evening"),
])
def test_dim_time_ids_and_periods(spark, time_id, hour, minute, second, period):
    row = build_dim_time(spark).filter(f"time_id = {time_id}").first()
    assert (row.hour, row.minute, row.second, row.time_period) == (hour, minute, second, period)


# ---------- dim_date ----------

def test_dim_date_has_every_day_in_range(spark):
    dim = build_dim_date(spark, date(2024, 12, 31), date(2025, 1, 6))
    assert [r.date_id for r in dim.orderBy("date_id").collect()] == [
        20241231, 20250101, 20250102, 20250103, 20250104, 20250105, 20250106,
    ]


@pytest.mark.parametrize("day, day_name, day_of_week, is_weekend", [
    (date(2025, 1, 4), "Saturday", 6, True),
    (date(2025, 1, 5), "Sunday", 7, True),
    (date(2025, 1, 6), "Monday", 1, False),
])
def test_dim_date_iso_weekday(spark, day, day_name, day_of_week, is_weekend):
    row = build_dim_date(spark, day, day).first()
    assert (row.day_name, row.day_of_week, row.is_weekend) == (day_name, day_of_week, is_weekend)
    assert (row.month_name, row.quarter, row.year) == ("January", 1, 2025)


def test_date_bounds_use_min_pickup_and_max_dropoff(yellow_bronze):
    trips = silver_trips(
        yellow_bronze,
        {"tpep_pickup_datetime": datetime(2024, 12, 31, 23, 50), "tpep_dropoff_datetime": datetime(2025, 1, 1, 0, 10)},
        {"tpep_pickup_datetime": datetime(2025, 1, 31, 23, 50), "tpep_dropoff_datetime": datetime(2025, 2, 1, 0, 10)},
    )
    assert date_bounds(trips) == (date(2024, 12, 31), date(2025, 2, 1))


# ---------- fact_trip ----------

# Power BI depends on these columns: a rename or drop must fail here, not in the report
FACT_COLUMNS = [
    "trip_id",
    "pickup_date_id", "pickup_time_id", "dropoff_date_id", "dropoff_time_id",
    "pickup_location_id", "dropoff_location_id", "vendor_id", "payment_id", "ratecode_id",
    "passenger_count", "trip_distance", "trip_duration_min",
    "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
    "improvement_surcharge", "congestion_surcharge", "airport_fee", "cbd_congestion_fee",
    "total_amount", "revenue",
    "taxi_type", "source_file", "ingestion_time",
]


def test_fact_trip_columns(yellow_bronze):
    assert build_fact_trip(silver_trips(yellow_bronze, {})).columns == FACT_COLUMNS


def test_fact_trip_date_and_time_keys(yellow_bronze):
    row = build_fact_trip(silver_trips(yellow_bronze, {})).first()   # 2025-01-10 08:00 -> 08:20
    assert (row.pickup_date_id, row.pickup_time_id) == (20250110, 80000)
    assert (row.dropoff_date_id, row.dropoff_time_id) == (20250110, 82000)


def test_fact_trip_null_codes_become_unknown_member(yellow_bronze):
    row = build_fact_trip(silver_trips(yellow_bronze, {"RatecodeID": None, "payment_type": None})).first()
    assert (row.ratecode_id, row.payment_id) == (UNKNOWN_ID, UNKNOWN_ID)


@pytest.mark.parametrize("override, revenue", [
    ({}, 22.75),                                                              # normal trip: revenue = total_amount
    ({"payment_type": 0, "fare_amount": -4.75, "total_amount": 3.0}, 0.0),    # Flex Fare with negative fare
])
def test_fact_trip_revenue(yellow_bronze, override, revenue):
    assert build_fact_trip(silver_trips(yellow_bronze, override)).first().revenue == revenue


# ---------- integrity checks ----------

def test_orphan_keys_finds_missing_key(spark):
    fact = spark.createDataFrame([(161,), (999,), (999,)], "pickup_location_id int")
    dim = spark.createDataFrame([(161,)], "location_id int")
    orphans = orphan_keys(fact, dim, "pickup_location_id", "location_id")
    assert [(r.pickup_location_id, r["count"]) for r in orphans.collect()] == [(999, 2)]


def test_every_fact_key_exists_in_its_dimension(spark, yellow_bronze, dims_config, zones):
    """Same check as 04_gold, on builders only: no fact key may miss its dimension row."""
    trips = silver_trips(yellow_bronze, {}, {"RatecodeID": None, "trip_distance": 5.0})
    fact = build_fact_trip(trips)
    dims = {
        "dim_date": build_dim_date(spark, *date_bounds(trips)),
        "dim_time": build_dim_time(spark),
        "dim_location": build_dim_location(zones),
        "dim_vendor": build_code_dim(spark, dims_config["vendor"], "vendor_id", "vendor_name"),
        "dim_payment": build_code_dim(spark, dims_config["payment"], "payment_id", "payment_desc"),
        "dim_ratecode": build_code_dim(spark, dims_config["ratecode"], "ratecode_id", "ratecode_desc"),
    }
    for fk_col, dim_table, dim_key in FOREIGN_KEYS:
        assert orphan_keys(fact, dims[dim_table], fk_col, dim_key).count() == 0, fk_col
