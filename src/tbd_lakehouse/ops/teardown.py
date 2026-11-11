"""`mise run destroy`, before Terraform: drop the tables dbt built.

Terraform doesn't know about them, but they keep the row access policy (and tags) in use, so
Terraform couldn't drop the policy. dbt writes its Iceberg tables under `_dbt/` in the bucket.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from snowflake.connector import DictCursor

from tbd_lakehouse.sf import connect


def dbt_built_tables(rows: Iterable[Mapping[str, str]]) -> list[str]:
    return [
        f'"{r["database_name"]}"."{r["schema_name"]}"."{r["name"]}"'
        for r in rows
        if r["base_location"].startswith("_dbt/")
    ]


def drop_dbt_tables() -> None:
    with connect("ACCOUNTADMIN") as c:
        cur = c.cursor(DictCursor)
        if not cur.execute("SHOW DATABASES LIKE 'LAKEHOUSE'").fetchall():
            print("no LAKEHOUSE database: nothing to drop")
            return
        tables = dbt_built_tables(cur.execute("SHOW ICEBERG TABLES IN DATABASE LAKEHOUSE").fetchall())
        for t in tables:
            cur.execute(f"DROP ICEBERG TABLE IF EXISTS {t}")
            print(f"dropped {t}")


if __name__ == "__main__":
    drop_dbt_tables()
