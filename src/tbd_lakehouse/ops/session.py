"""`mise run stop` / `mise run start`: suspend or resume everything that can spend credits.

Run `stop` at the end of every session. `start` refuses once RM_LAB has used the whole cap.
"""

from __future__ import annotations

import sys

from tbd_lakehouse.sf import connect


def _call(proc: str) -> str:
    with connect("ACCOUNTADMIN") as c:
        return c.cursor().execute(f"CALL LAKEHOUSE.OPS.{proc}()").fetchone()[0]


def stop() -> None:
    print(_call("STOP_ALL").rstrip())
    print("Stopped: pipes paused, dynamic tables and tasks suspended, INGEST_SVC disabled, warehouses suspended.")


def start() -> None:
    out = _call("START_ALL").rstrip()
    print(out)
    if out.startswith("refused"):
        raise SystemExit(1)
    print("Started. Remember `mise run stop` when you finish.")


if __name__ == "__main__":
    {"stop": stop, "start": start}[sys.argv[1]]()
