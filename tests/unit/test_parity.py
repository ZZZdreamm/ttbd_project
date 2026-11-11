from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from tbd_lakehouse.lab.parity import PARITY_QUERIES, compare_frames


def test_compare_equal_despite_case_and_decimal():
    a = pd.DataFrame({"REVENUE": [Decimal("10.50")], "STATUS": ["paid"]})
    b = pd.DataFrame({"revenue": [10.5], "status": ["paid"]})
    assert compare_frames(a, b) == []


def test_compare_reports_row_count_and_value_diffs():
    d = compare_frames(pd.DataFrame({"x": [1, 2]}), pd.DataFrame({"x": [1, 3]}))
    assert any("x" in m and "2" in m and "3" in m for m in d)
    assert any("row count" in m for m in compare_frames(pd.DataFrame({"x": [1]}), pd.DataFrame({"x": [1, 2]})))


def test_compare_reports_missing_columns():
    assert any("columns" in m for m in compare_frames(pd.DataFrame({"x": [1]}), pd.DataFrame({"y": [1]})))


def test_compare_normalises_dates_and_timestamps():
    a = pd.DataFrame({"d": [date(2026, 11, 20)], "t": [datetime(2026, 11, 20, 12, 0)]})
    b = pd.DataFrame({"d": [pd.Timestamp("2026-11-20")], "t": [pd.Timestamp("2026-11-20 12:00:00")]})
    assert compare_frames(a, b) == []


def test_compare_null_equals_null():
    assert compare_frames(pd.DataFrame({"x": [None]}), pd.DataFrame({"x": [float("nan")]})) == []


def test_queries_use_db_placeholder_only():
    assert set(PARITY_QUERIES) == {"rt_by_country_status", "daily_sales", "ltv_summary"}
    assert all("{db}" in q and "LAKEHOUSE" not in q for q in PARITY_QUERIES.values())
