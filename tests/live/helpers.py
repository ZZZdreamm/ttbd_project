"""Small query helpers shared by the live tests (they run against the team's real account)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def _rows(conn, sql: str) -> tuple[list[str], list[tuple]]:
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, cur.fetchall()


def one(conn, sql: str) -> dict[str, Any]:
    """Exactly one row as a dict; keys as Snowflake returns them (UPPER for SELECT, lower for SHOW)."""
    cols, rows = _rows(conn, sql)
    assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {sql}"
    return dict(zip(cols, rows[0]))


def scalar(conn, sql: str) -> Any:
    _, rows = _rows(conn, sql)
    assert rows, f"no rows: {sql}"
    return rows[0][0]


def all_rows(conn, sql: str) -> list[tuple]:
    return _rows(conn, sql)[1]


def tag_refs(conn, fqn: str) -> dict[str, str]:
    """UPPER column name -> PII_TYPE value for every tagged column of a table."""
    db = fqn.split(".")[0]
    sql = (f"SELECT column_name, tag_value FROM TABLE({db}.INFORMATION_SCHEMA.TAG_REFERENCES_ALL_COLUMNS("
           f"'{fqn}', 'TABLE')) WHERE tag_name = 'PII_TYPE'")
    return {c.upper(): v for c, v in all_rows(conn, sql)}


def refresh(sf: Callable, name: str) -> None:
    """Refresh a dynamic table now (as its owner role)."""
    sf("PIPELINE_ADMIN").cursor().execute(f"ALTER DYNAMIC TABLE LAKEHOUSE.{name} REFRESH")


def wait_until(fn: Callable[[], Any], timeout: float, interval: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if fn():
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)
