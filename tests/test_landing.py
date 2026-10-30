from nyctaxi.landing import month_range

def test_month_range_within_one_year():
    assert month_range("2025-01", "2025-03") == ["2025-01", "2025-02", "2025-03"]


def test_month_range_crosses_year():
    assert month_range("2024-11", "2025-02") == ["2024-11", "2024-12", "2025-01", "2025-02"]


def test_month_range_single_month():
    assert month_range("2025-05", "2025-05") == ["2025-05"]


def test_month_range_start_after_end_is_empty():
    assert month_range("2025-03", "2025-01") == []


def test_month_range_accepts_month_without_leading_zero():
    assert month_range("2025-1", "2025-2") == ["2025-01", "2025-02"]
