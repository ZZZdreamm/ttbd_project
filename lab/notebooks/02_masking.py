import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from tbd_lakehouse.lab.engines import duckdb_df, snowflake_df_as, spark_df

    mo.md(
        """
        # Masking outside Snowflake

        `SILVER.CUSTOMERS_CURRENT` is tagged (from dbt `meta`) and has a row access policy.
        `SILVER.ORDERS_LATEST` got its tags by **propagation** from bronze.

        Spark reads them through Horizon's **Scan Plan API**: Snowflake evaluates the masking and row
        access policies for the PAT's role/user and hands Spark only what it may see.
        DuckDB can't do server-side scan planning, so Horizon refuses to give it protected tables.

        Remember: anyone with direct access to the GCS bucket can read the raw Parquet files.
        Bucket IAM is part of the governance story.
        """
    )
    return duckdb_df, mo, snowflake_df_as, spark_df


@app.cell
def _(mo):
    user = mo.ui.radio(options=["ANALYST_USER", "SUPPORT_USER", "PII_ADMIN_USER"], value="SUPPORT_USER", label="Read as")
    table = mo.ui.dropdown(options=["SILVER.CUSTOMERS_CURRENT", "SILVER.ORDERS_LATEST"], value="SILVER.CUSTOMERS_CURRENT")
    mo.hstack([user, table])
    return table, user


@app.cell
def _(mo, snowflake_df_as, spark_df, table, user):
    cols = {"SILVER.CUSTOMERS_CURRENT": "customer_id, first_name, email, phone, date_of_birth, city, country",
            "SILVER.ORDERS_LATEST": "order_id, status, card_last4, ip_address, shipping_street, shipping_country"}[table.value]
    sql = f"SELECT {cols} FROM {{db}}.{table.value} ORDER BY 1 LIMIT 20"
    sf = snowflake_df_as(sql.format(db="LAKEHOUSE"), user.value)
    sp = spark_df(sql, user.value)
    mo.hstack([mo.vstack([mo.md(f"**Snowflake as {user.value}**"), sf]),
               mo.vstack([mo.md(f"**Spark (Horizon Scan Plan) as {user.value}**"), sp])], widths="equal")
    return


@app.cell
def _(duckdb_df, mo, table):
    try:
        duckdb_df(f"SELECT * FROM {{db}}.{table.value} LIMIT 1", "ANALYST_USER")
        out = mo.callout(mo.md("DuckDB read a protected table - this should not happen!"), kind="danger")
    except Exception as e:  # expected
        out = mo.callout(mo.md(f"**DuckDB is refused, as expected:** `{str(e)[:300]}`"), kind="success")
    out
    return


if __name__ == "__main__":
    app.run()
