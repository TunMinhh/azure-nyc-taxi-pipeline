from datetime import datetime

import pytest

from nyctaxi.silver import SILVER_SCHEMA, build_silver_trips, split_valid_rejected, standardize


def tag(yellow_bronze, *overrides, month="2025-01"):
    return build_silver_trips(yellow_bronze(*overrides), "yellow", month)


# ---------- standardize ----------

def test_standardize_outputs_silver_schema_in_order(yellow_bronze):
    df = standardize(yellow_bronze({}), "yellow")
    expected = [name for name, _ in SILVER_SCHEMA] + ["taxi_type", "source_file", "ingestion_time", "_rescued_data"]
    assert df.columns == expected


def test_standardize_maps_yellow_columns(yellow_bronze):
    row = standardize(yellow_bronze({}), "yellow").first()
    assert row.pickup_ts == datetime(2025, 1, 10, 8, 0)
    assert row.vendor_id == 2
    assert row.taxi_type == "yellow"
    assert row.trip_type is None          # green only


@pytest.mark.parametrize("flag, expected", [("Y", True), ("N", False), (None, None)])
def test_standardize_store_and_fwd_flag_to_boolean(yellow_bronze, flag, expected):
    row = standardize(yellow_bronze({"store_and_fwd_flag": flag}), "yellow").first()
    assert row.store_and_fwd_flag is expected


def test_standardize_rejects_unknown_taxi_type(yellow_bronze):
    with pytest.raises(ValueError):
        standardize(yellow_bronze({}), "fhv")


# ---------- reject rules ----------

@pytest.mark.parametrize("override, expected", [
    ({}, None),
    ({"_rescued_data": '{"new_col": 1}'}, "schema_mismatch"),
    ({"tpep_pickup_datetime": None}, "missing_file_month_or_pickup_ts"),
    # month edge: up to 1 day outside the file month is still valid
    ({"tpep_pickup_datetime": datetime(2024, 12, 31, 23, 50),
      "tpep_dropoff_datetime": datetime(2025, 1, 1, 0, 10)}, None),
    ({"tpep_pickup_datetime": datetime(2024, 12, 30, 8, 0),
      "tpep_dropoff_datetime": datetime(2024, 12, 30, 8, 20)}, "pickup_outside_file_month"),
    ({"tpep_dropoff_datetime": None}, "invalid_trip_duration"),
    ({"tpep_dropoff_datetime": datetime(2025, 1, 10, 8, 0)}, "invalid_trip_duration"),    # 0 min
    ({"tpep_dropoff_datetime": datetime(2025, 1, 10, 14, 0)}, None),                       # exactly 360 min
    ({"tpep_dropoff_datetime": datetime(2025, 1, 10, 14, 1)}, "invalid_trip_duration"),    # 361 min
    ({"trip_distance": 0.0}, "invalid_trip_distance"),
    ({"trip_distance": 200.0}, None),
    ({"trip_distance": 200.1}, "invalid_trip_distance"),
    ({"total_amount": None}, "missing_total_amount"),
    ({"total_amount": -22.75}, "negative_total_amount_review"),
    # first matching rule wins: bad duration AND bad distance -> duration
    ({"tpep_dropoff_datetime": datetime(2025, 1, 10, 8, 0), "trip_distance": 0.0}, "invalid_trip_duration"),
])
def test_reject_reason(yellow_bronze, override, expected):
    assert tag(yellow_bronze, override).first().dq_reason == expected


# ---------- duplicates ----------

def test_identical_rows_give_one_valid_and_one_duplicate(yellow_bronze):
    reasons = [r.dq_reason for r in tag(yellow_bronze, {}, {}).collect()]
    assert reasons.count(None) == 1
    assert reasons.count("duplicate_trip_id") == 1


def test_duplicate_keeps_row_with_passenger_count(yellow_bronze):
    valid, rejected = split_valid_rejected(
        tag(yellow_bronze, {"passenger_count": None}, {"passenger_count": 2})
    )
    assert [r.passenger_count for r in valid.collect()] == [2]
    assert [r.dq_reason for r in rejected.collect()] == ["duplicate_trip_id"]


def test_different_trips_are_not_duplicates(yellow_bronze):
    reasons = [r.dq_reason for r in tag(yellow_bronze, {"trip_distance": 3.0}, {"trip_distance": 3.1}).collect()]
    assert reasons == [None, None]


def test_split_removes_temp_columns_from_valid(yellow_bronze):
    valid, rejected = split_valid_rejected(tag(yellow_bronze, {}, {"trip_distance": 0.0}))
    assert not {"_rescued_data", "_file_month", "dq_reason"} & set(valid.columns)
    assert {"file_month", "dq_reason"} <= set(rejected.columns)


# ---------- trip_id and input guards ----------

def test_trip_id_is_stable_sha256(yellow_bronze):
    first = tag(yellow_bronze, {}).first().trip_id
    second = tag(yellow_bronze, {}).first().trip_id
    assert first == second
    assert len(first) == 64


@pytest.mark.parametrize("month", ["2025-1", "2025-13", "2025-01' OR '1'='1"])
def test_build_rejects_bad_month(yellow_bronze, month):
    with pytest.raises(ValueError, match="YYYY-MM"):
        tag(yellow_bronze, {}, month=month)


def test_build_fails_when_month_has_no_rows(yellow_bronze):
    with pytest.raises(ValueError, match="No Bronze rows"):
        tag(yellow_bronze, {}, month="2025-02")
