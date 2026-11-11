import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from tbd_lakehouse.lab.engines import duckdb_df, snowflake_df, spark_df
    from tbd_lakehouse.lab.parity import PARITY_QUERIES, compare_frames

    mo.md(
        """
        # Gold layer: Snowflake vs Spark vs DuckDB

        The same SQL runs in three engines. Spark and DuckDB read the **same Iceberg files** in your
        GCS bucket through **Snowflake Horizon** (Iceberg REST catalog, vended credentials).
        Gold tables contain no PII, so no masking applies and the results must be identical.

        Tip: run `mise run test` for the automated version of this check (it pauses refreshes first,
        so all engines see the same snapshot).
        """
    )
    return PARITY_QUERIES, compare_frames, duckdb_df, mo, snowflake_df, spark_df


@app.cell
def _(mo, PARITY_QUERIES):
    query = mo.ui.dropdown(options=list(PARITY_QUERIES), value="rt_by_country_status", label="Query")
    query
    return (query,)


@app.cell
def _(PARITY_QUERIES, compare_frames, duckdb_df, mo, query, snowflake_df, spark_df):
    sql = PARITY_QUERIES[query.value]
    sf = snowflake_df(sql.format(db="LAKEHOUSE"), role="ANALYST")
    sp = spark_df(sql, "ANALYST_USER")
    dd = duckdb_df(sql, "ANALYST_USER")
    diffs = compare_frames(sf, sp) + compare_frames(sf, dd)
    verdict = mo.callout(mo.md("**Identical in all three engines**"), kind="success") if not diffs else \
        mo.callout(mo.md("**Differences:**\n\n" + "\n".join(f"- {d}" for d in diffs)), kind="danger")
    mo.vstack([
        mo.md(f"```sql\n{sql}\n```"),
        verdict,
        mo.hstack([mo.vstack([mo.md("**Snowflake**"), sf]), mo.vstack([mo.md("**Spark**"), sp]),
                   mo.vstack([mo.md("**DuckDB**"), dd])], widths="equal"),
    ])
    return


if __name__ == "__main__":
    app.run()
