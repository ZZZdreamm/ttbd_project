"""Query engines for the lab: Snowflake (connector), Spark and DuckDB (both via Horizon).

Demo users (ANALYST_USER, SUPPORT_USER, PII_ADMIN_USER) authenticate to Horizon with the PATs
Terraform wrote to .secrets/. Masking and row access on protected tables are enforced by Horizon
(server-side scan planning) for Spark; DuckDB can't do server-side planning, so it can only read
unprotected tables (gold) and fails on protected ones.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

from tbd_lakehouse.config import load_settings
from tbd_lakehouse.sf import SECRETS, connect

DEMO_ROLES = {"ANALYST_USER": "ANALYST", "SUPPORT_USER": "SUPPORT", "PII_ADMIN_USER": "PII_ADMIN"}
DATABASE = "LAKEHOUSE"


def _host() -> str:
    return f"https://{load_settings().snowflake_account.lower()}.snowflakecomputing.com"


def _pat(user: str) -> str:
    return (SECRETS / f"{user.lower()}.pat").read_text().strip()


def snowflake_df(sql: str, role: str) -> pd.DataFrame:
    """Run SQL in Snowflake as TERRAFORM_SVC with `role` (masking follows CURRENT_ROLE())."""
    with connect(role) as c:
        cur = c.cursor()
        cur.execute(sql)
        return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def snowflake_df_as(sql: str, user: str) -> pd.DataFrame:
    """Run SQL in Snowflake as a demo user (needed for row access, which keys on CURRENT_USER())."""
    with connect(DEMO_ROLES[user], user=user) as c:
        cur = c.cursor()
        cur.execute(sql)
        return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


# ---------------------------------------------------------------- Spark
_spark = None


def spark_catalog(user: str) -> str:
    return f"hz_{user.lower()}"


def spark_session(user: str):
    """Local SparkSession with a Horizon Iceberg REST catalog for `user`, named spark_catalog(user)."""
    global _spark
    from pyspark.sql import SparkSession

    if _spark is None:
        jars = ",".join(sorted(glob.glob(os.environ.get("ICEBERG_JARS", "/opt/jars") + "/*.jar")))
        _spark = (
            SparkSession.builder.appName("tbd-lab").master("local[*]")
            .config("spark.jars", jars)
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config("spark.sql.iceberg.vectorization.enabled", "false")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        _spark.sparkContext.setLogLevel("ERROR")
    cat = spark_catalog(user)
    if _spark.conf.get(f"spark.sql.catalog.{cat}", None) is None:
        for k, v in {
            "": "org.apache.iceberg.spark.SparkCatalog",
            ".type": "rest",
            ".uri": f"{_host()}/polaris/api/catalog",
            ".warehouse": DATABASE,
            ".credential": _pat(user),
            ".scope": f"session:role:{DEMO_ROLES[user]}",
            ".header.X-Iceberg-Access-Delegation": "vended-credentials",
        }.items():
            _spark.conf.set(f"spark.sql.catalog.{cat}{k}", v)
    return _spark


def spark_df(sql_template: str, user: str) -> pd.DataFrame:
    return spark_session(user).sql(sql_template.format(db=spark_catalog(user))).toPandas()


# ---------------------------------------------------------------- DuckDB
def duckdb_connect(user: str):
    """DuckDB with Horizon attached as `horizon` (vended GCS credentials)."""
    import duckdb

    con = duckdb.connect()
    for ext in ("httpfs", "iceberg"):
        con.install_extension(ext)
        con.load_extension(ext)
    host = _host()
    con.execute(
        f"""CREATE SECRET horizon (TYPE iceberg, CLIENT_ID '', CLIENT_SECRET '{_pat(user)}',
            OAUTH2_SERVER_URI '{host}/polaris/api/catalog/v1/oauth/tokens',
            OAUTH2_SCOPE 'session:role:{DEMO_ROLES[user]}')"""
    )
    con.execute(
        f"""ATTACH '{DATABASE}' AS horizon (TYPE iceberg, ENDPOINT '{host}/polaris/api/catalog',
            SECRET horizon, ACCESS_DELEGATION_MODE 'vended_credentials')"""
    )
    return con


def duckdb_df(sql_template: str, user: str) -> pd.DataFrame:
    return duckdb_connect(user).sql(sql_template.format(db="horizon")).df()
