import json

import pytest

from tbd_lakehouse.ops import session
from tests.live.helpers import one, scalar, wait_until

pytestmark = pytest.mark.check("7 Guardrails")


def _state(sf):
    c = sf("ACCOUNTADMIN")
    cur = c.cursor(); cur.execute("SHOW DYNAMIC TABLES IN DATABASE LAKEHOUSE")
    i = [d[0] for d in cur.description].index("scheduling_state")
    dts = cur.fetchall()
    dt_states = {r[i] for r in dts}
    cur.execute("SHOW TASKS IN DATABASE LAKEHOUSE")
    j = [d[0] for d in cur.description].index("state")
    n = [d[0] for d in cur.description].index("name")
    task_states = {r[j] for r in cur.fetchall() if r[n] != "NIGHTLY_STOP"}  # the safety net stays on
    cur.execute("SHOW PIPES IN DATABASE LAKEHOUSE")
    cols = [d[0] for d in cur.description]
    pipes = [".".join(r[cols.index(k)] for k in ("database_name", "schema_name", "name")) for r in cur.fetchall()]
    pipe_states = {json.loads(scalar(c, f"SELECT SYSTEM$PIPE_STATUS('{p}')"))["executionState"] for p in pipes}
    ingest_disabled = one(c, "SHOW USERS LIKE 'INGEST_SVC'")["disabled"]
    assert dts and pipes and task_states
    return dt_states, task_states, pipe_states, ingest_disabled


def test_stop_suspends_everything_and_start_restores(sf):
    session.stop()
    assert _state(sf) == ({"SUSPENDED"}, {"suspended"}, {"PAUSED"}, "true")
    session.start()
    # unpausing a pipe is asynchronous: give it a moment
    restored = ({"ACTIVE"}, {"started"}, {"RUNNING"}, "false")
    assert wait_until(lambda: _state(sf) == restored, timeout=120, interval=10), _state(sf)


def test_redeploy_after_stop_keeps_everything_stopped(sf, run):
    session.stop()
    try:
        run("mise run dcm")
        assert _state(sf) == ({"SUSPENDED"}, {"suspended"}, {"PAUSED"}, "true")
    finally:
        session.start()
