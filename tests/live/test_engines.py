"""Spark and DuckDB via Horizon (run inside the lab container: `mise run test`)."""

import pytest

from tbd_lakehouse.lab.engines import duckdb_df, snowflake_df, snowflake_df_as, spark_df
from tbd_lakehouse.lab.parity import PARITY_QUERIES, compare_frames

USERS = ["ANALYST_USER", "SUPPORT_USER", "PII_ADMIN_USER"]


@pytest.mark.check("4 Parity")
@pytest.mark.parametrize("name", list(PARITY_QUERIES))
def test_parity(frozen, name):
    sql = PARITY_QUERIES[name]
    sf_df = snowflake_df(sql.format(db="LAKEHOUSE"), role="ANALYST")
    assert len(sf_df) > 0, f"{name}: no rows in Snowflake yet (let data flow, run `mise run dbt:run`)"
    assert compare_frames(sf_df, spark_df(sql, "ANALYST_USER")) == [], "Spark differs from Snowflake"
    assert compare_frames(sf_df, duckdb_df(sql, "ANALYST_USER")) == [], "DuckDB differs from Snowflake"


@pytest.mark.check("5 Masking")
@pytest.mark.parametrize("user", USERS)
def test_spark_masking_matches_snowflake(frozen, user):
    sql = ("SELECT customer_id, first_name, email, phone, date_of_birth, country "
           "FROM {db}.SILVER.CUSTOMERS_CURRENT ORDER BY customer_id LIMIT 50")
    sf_df = snowflake_df_as(sql.format(db="LAKEHOUSE"), user)
    sp_df = spark_df(sql, user)
    assert compare_frames(sf_df, sp_df) == []
    if user == "ANALYST_USER":
        assert set(sp_df["email"]) == {"***"}
    if user == "SUPPORT_USER":
        assert set(sp_df["country"]) <= {"PL", "NL"} and all(e.startswith("***@") for e in sp_df["email"])
    if user == "PII_ADMIN_USER":
        assert all("@" in e and not e.startswith("***") for e in sp_df["email"])


@pytest.mark.check("6 Tag propagation")
@pytest.mark.parametrize("user,expected", [("ANALYST_USER", "***"), ("SUPPORT_USER", ".x.x"), ("PII_ADMIN_USER", None)])
def test_spark_masks_propagated_columns(frozen, user, expected):
    sql = "SELECT order_id, ip_address FROM {db}.SILVER.ORDERS_LATEST ORDER BY order_id LIMIT 20"
    sp_df = spark_df(sql, user)
    assert len(sp_df) > 0
    assert compare_frames(snowflake_df_as(sql.format(db="LAKEHOUSE"), user), sp_df) == []
    ips = set(sp_df["ip_address"])
    if expected == "***":
        assert ips == {"***"}
    elif expected:
        assert all(ip.endswith(expected) for ip in ips)
    else:
        assert all(not ip.endswith(".x.x") and ip != "***" for ip in ips)


@pytest.mark.check("5 Masking")
@pytest.mark.parametrize("table", ["SILVER.CUSTOMERS_CURRENT", "SILVER.ORDERS_LATEST"])
def test_duckdb_cannot_read_protected_table(table):
    with pytest.raises(Exception, match="(?i)server-side scan planning|plan scan"):
        duckdb_df(f"SELECT * FROM {{db}}.{table} LIMIT 1", "ANALYST_USER")
