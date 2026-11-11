"""The same gold queries in Snowflake, Spark and DuckDB, and a tolerant result comparison.

`{db}` is LAKEHOUSE in Snowflake, the Horizon catalog name in Spark/DuckDB.
Every query is fully ordered so results compare row by row.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

PARITY_QUERIES: dict[str, str] = {
    "rt_by_country_status": (
        "SELECT shipping_country, status, order_count, revenue "
        "FROM {db}.GOLD.ORDERS_BY_COUNTRY_STATUS_RT ORDER BY shipping_country, status"
    ),
    "daily_sales": (
        "SELECT order_date, category, orders, units, revenue "
        "FROM {db}.GOLD.DAILY_SALES_BY_CATEGORY ORDER BY order_date, category"
    ),
    "ltv_summary": (
        "SELECT COUNT(*) AS customers, SUM(ltv) AS total_ltv, MAX(ltv) AS max_ltv, MIN(first_order_at) AS first_order "
        "FROM {db}.GOLD.CUSTOMER_LTV"
    ),
}


def _norm(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, pd.Timestamp):
        v = v.to_pydatetime()
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            v = v.astimezone(tz=None).replace(tzinfo=None)
        return v.date().isoformat() if (v.hour, v.minute, v.second, v.microsecond) == (0, 0, 0, 0) else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "item"):  # numpy scalars
        return _norm(v.item())
    return v


def _equal(a, b, tol: float) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=tol, abs_tol=tol)
    return a == b


def compare_frames(a: pd.DataFrame, b: pd.DataFrame, tol: float = 1e-6) -> list[str]:
    """Human-readable differences between two results; [] means equal."""
    a = a.rename(columns=str.lower)
    b = b.rename(columns=str.lower)
    if list(a.columns) != list(b.columns):
        return [f"columns differ: {list(a.columns)} vs {list(b.columns)}"]
    if len(a) != len(b):
        return [f"row count differs: {len(a)} vs {len(b)}"]
    diffs = []
    for i, (ra, rb) in enumerate(zip(a.itertuples(index=False), b.itertuples(index=False))):
        for col, va, vb in zip(a.columns, ra, rb):
            na, nb = _norm(va), _norm(vb)
            if not _equal(na, nb, tol):
                diffs.append(f"row {i}, column {col}: {na!r} vs {nb!r}")
                if len(diffs) >= 20:
                    return diffs + ["..."]
    return diffs
