import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from tbd_lakehouse.lab import engines
    from tbd_lakehouse.lab.engines import duckdb_df, snowflake_df_as, spark_df

    # Register the new user for the lab helpers (role MARKETING, user MARKETING_USER).
    engines.DEMO_ROLES["MARKETING_USER"] = "MARKETING"

    mo.md(
        """
        # Team 06: the MARKETING role

        **Scenario:** marketing may *segment* customers but must not be able to *identify* them.

        | PII_TYPE | MARKETING sees | Function |
        |---|---|---|
        | NAME | `Kowalski` -> `K*w*l*k*` | every second character |
        | EMAIL | 12 hex characters | pseudonym `LEFT(SHA2(LOWER(val)), 12)`: same input, same output, so customers can be counted and joined |
        | PHONE | `+48 600 100 200` -> `+48*********` | **own idea:** keep only the international dialling code (the country); numbers without `+` are fully masked |
        | ADDRESS | `***` | constant |
        | DOB | `1987-06-14` -> `1980-01-01` | **own idea:** decade of birth (generation cohort) |
        | IP | `10.1.2.3` -> `10.1.0.0` | network only |
        | CARD | `****` | constant |

        The policies live in `snowflake/sql/mp_pii_string.sql` and `mp_pii_date.sql` (a `WHEN CURRENT_ROLE() = 'MARKETING'` branch).
        Everything below reads the **same rows** as `PII_ADMIN_USER` (raw) and `MARKETING_USER` (masked), in Snowflake and in Spark through Horizon.
        """
    )
    return duckdb_df, mo, snowflake_df_as, spark_df


@app.cell
def _():
    # The same functions as in the SQL policies, written again in Python.
    import hashlib
    import re

    def _digits(val):
        return re.sub(r"[^0-9+]", "", val)

    def f_name(val):  # REGEXP_REPLACE(val, '(.).', '\\1*')
        return None if val is None else re.sub(r"(.).", r"\1*", val)

    def f_email(val):  # LEFT(SHA2(LOWER(val)), 12)
        return None if val is None else hashlib.sha256(val.lower().encode()).hexdigest()[:12]

    def f_phone(val):  # dialling code only when the number starts with '+'
        if val is None:
            return None
        d = _digits(val)
        if val.lstrip().startswith("+"):
            return d[:3] + "*" * max(len(d) - 3, 0)
        return "*" * len(d)

    def f_address(val):  # constant, also for NULL (ELSE branch of the policy)
        return "***"

    def f_card(val):
        return "****"

    def f_ip(val):  # network only
        if val is None:
            return None
        p = val.split(".")
        return f"{p[0]}.{p[1]}.0.0"

    def f_dob(val):  # decade of birth
        return None if val is None else val.replace(year=(val.year // 10) * 10, month=1, day=1)

    MASKS = {
        "customers": {
            "first_name": f_name, "last_name": f_name, "email": f_email, "phone": f_phone,
            "date_of_birth": f_dob, "street": f_address, "postal_code": f_address,
        },
        "orders": {
            "card_last4": f_card, "ip_address": f_ip,
            "shipping_street": f_address, "shipping_postal_code": f_address,
        },
    }
    return (MASKS,)


@app.cell
def _(mo, snowflake_df_as, spark_df):
    import pandas as pd

    def _norm(df):
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        return df.astype(object).where(df.notna(), None)

    def read_both(sql_ids, cols, table, key, n=20):
        """Pick n keys as PII_ADMIN_USER, then read exactly those rows as admin and as MARKETING_USER, in both engines."""
        ids = list(_norm(snowflake_df_as(sql_ids.format(db="LAKEHOUSE"), "PII_ADMIN_USER"))[key])
        in_list = ", ".join(f"'{i}'" for i in ids)
        q = f"SELECT {key}, {cols} FROM {{db}}.{table} WHERE {key} IN ({in_list}) ORDER BY {key}"
        out = {}
        for who in ("PII_ADMIN_USER", "MARKETING_USER"):
            out[("snowflake", who)] = _norm(snowflake_df_as(q.format(db="LAKEHOUSE"), who)).set_index(key)
            out[("spark", who)] = _norm(spark_df(q, who)).set_index(key)
        return out

    customers = read_both(
        "SELECT customer_id FROM {db}.SILVER.CUSTOMERS_CURRENT ORDER BY customer_id LIMIT 20",
        "first_name, last_name, email, phone, date_of_birth, street, postal_code, country",
        "SILVER.CUSTOMERS_CURRENT", "customer_id",
    )
    orders = read_both(
        "SELECT order_id FROM {db}.SILVER.ORDERS_LATEST ORDER BY order_id LIMIT 20",
        "status, card_last4, ip_address, shipping_street, shipping_postal_code",
        "SILVER.ORDERS_LATEST", "order_id",
    )
    mo.md(
        f"Read **{len(customers[('snowflake', 'PII_ADMIN_USER')])}** customers (batch) and "
        f"**{len(orders[('snowflake', 'PII_ADMIN_USER')])}** orders (streaming) as raw and as MARKETING_USER, in Snowflake and Spark."
    )
    return customers, orders, pd


@app.cell
def _(MASKS, mo, pd):
    def check(data, kind):
        rows = []
        for engine in ("snowflake", "spark"):
            raw = data[(engine, "PII_ADMIN_USER")]
            masked = data[(engine, "MARKETING_USER")]
            for col, fn in MASKS[kind].items():
                ok = True
                example = ""
                for key in raw.index.intersection(masked.index):
                    expected = fn(raw.at[key, col])
                    got = masked.at[key, col]
                    # Spark returns dates as datetime.date / Timestamp: compare as text
                    if str(expected) != str(got) and not (expected is None and got is None):
                        ok = False
                        example = f"{key}: expected {expected!r}, got {got!r}"
                        break
                    if not example:
                        example = f"{raw.at[key, col]!r} -> {got!r}"
                rows.append({"engine": engine, "column": col, "rows compared": len(raw.index.intersection(masked.index)),
                             "result": "PASS" if ok else "FAIL", "example": example})
        return pd.DataFrame(rows)

    return (check,)


@app.cell
def _(check, customers, mo):
    res_c = check(customers, "customers")
    mo.vstack([
        mo.md("## Batch: `SILVER.CUSTOMERS_CURRENT` (tags set by dbt, apply_method MANUAL)"),
        mo.ui.table(res_c, selection=None, page_size=20),
        mo.callout(mo.md(f"**{(res_c.result == 'PASS').sum()} / {len(res_c)} PASS**"),
                   kind="success" if (res_c.result == "PASS").all() else "danger"),
    ])
    return


@app.cell
def _(check, mo, orders):
    res_o = check(orders, "orders")
    mo.vstack([
        mo.md("## Streaming: `SILVER.ORDERS_LATEST` (tags PROPAGATED from bronze)"),
        mo.ui.table(res_o, selection=None, page_size=20),
        mo.callout(mo.md(f"**{(res_o.result == 'PASS').sum()} / {len(res_o)} PASS**"),
                   kind="success" if (res_o.result == "PASS").all() else "danger"),
    ])
    return


@app.cell
def _(mo, snowflake_df_as, spark_df):
    _q = "SELECT country, COUNT(*) AS customers FROM {db}.SILVER.CUSTOMERS_CURRENT GROUP BY country ORDER BY country"
    _parts = []
    for _u in ("PII_ADMIN_USER", "MARKETING_USER", "SUPPORT_USER"):
        _parts.append(mo.vstack([
            mo.md(f"**{_u}**: Snowflake"), snowflake_df_as(_q.format(db="LAKEHOUSE"), _u),
            mo.md(f"**{_u}**: Spark"), spark_df(_q, _u),
        ]))
    mo.vstack([
        mo.md(
            """
            ## Which rows does MARKETING see?

            `CUSTOMERS_CURRENT` carries the row access policy `RAP_SUPPORT_COUNTRY` (attached by dbt on `country`):

            ```sql
            CURRENT_ROLE() IN (<all_rows_roles>)
            OR EXISTS (SELECT 1 FROM GOVERNANCE.SUPPORT_COUNTRY_MAP m WHERE m.user_name = CURRENT_USER() AND m.country = country)
            ```

            I added `MARKETING` to `all_rows_roles` (`snowflake/governance.tf`), so it sees **all countries**: segmentation needs the whole
            customer base, and its protection is the masking, not the row filter. `SUPPORT_USER` is not in that list, so it only sees
            the countries mapped to it in `SUPPORT_COUNTRY_MAP` (PL, NL). Without the change MARKETING would have seen **zero rows**
            (the policy is deny-by-default), because it is not listed and not in the map.
            """
        ),
        mo.hstack(_parts, widths="equal"),
    ])
    return


@app.cell
def _(duckdb_df, mo, snowflake_df_as, spark_df):
    # DuckDB is still refused for protected tables (no server-side scan planning).
    _msgs = []
    for _u in ("MARKETING_USER", "ANALYST_USER"):
        try:
            duckdb_df("SELECT * FROM {db}.SILVER.CUSTOMERS_CURRENT LIMIT 1", _u)
            _msgs.append(mo.callout(mo.md(f"DuckDB as {_u} read a protected table - this should not happen!"), kind="danger"))
        except Exception as e:  # expected
            _msgs.append(mo.callout(mo.md(f"**DuckDB is refused as {_u}, as expected:** `{str(e)[:250]}`"), kind="success"))

    # SUPPORT_USER must see what it saw before MARKETING existed.
    _q = ("SELECT first_name, email, phone, date_of_birth, street, country FROM {db}.SILVER.CUSTOMERS_CURRENT "
          "ORDER BY customer_id LIMIT 5")
    _qo = "SELECT ip_address FROM {db}.SILVER.ORDERS_LATEST ORDER BY order_id LIMIT 5"
    _ok = {}
    for _eng, _fn in (("snowflake", lambda s: snowflake_df_as(s.format(db="LAKEHOUSE"), "SUPPORT_USER")),
                      ("spark", lambda s: spark_df(s, "SUPPORT_USER"))):
        _c, _o = _fn(_q), _fn(_qo)
        _c.columns = [x.lower() for x in _c.columns]
        _o.columns = [x.lower() for x in _o.columns]
        _ok[_eng] = {
            "first_name = X***": bool(_c.first_name.str.fullmatch(r".\*\*\*").all()),
            "email = ***@domain": bool(_c.email.str.fullmatch(r"\*\*\*@.+").all()),
            "phone = ***dddd": bool(_c.phone.str.fullmatch(r"\*\*\*\d{0,4}").all()),
            "dob = Jan 1": bool(_c.date_of_birth.map(lambda d: (d.month, d.day) == (1, 1)).all()),
            "street = ***": bool((_c.street == "***").all()),
            "countries only PL/NL": bool(set(_c.country) <= {"PL", "NL"}),
            "ip = a.b.x.x": bool(_o.ip_address.str.fullmatch(r"\d+\.\d+\.x\.x").all()),
        }
    import pandas as _pd

    _tbl = _pd.DataFrame(_ok).map(lambda b: "PASS" if b else "FAIL")
    mo.vstack([mo.md("## DuckDB still refused, SUPPORT unchanged"), *_msgs,
               mo.md("**SUPPORT_USER (unchanged behaviour):**"), mo.ui.table(_tbl.reset_index(names="check"), selection=None)])
    return


if __name__ == "__main__":
    app.run()
