"""Live checks for `mise run test`. Mark each test with @pytest.mark.check("<n> <name>")."""

from __future__ import annotations

import pytest

from tbd_lakehouse.config import load_settings
from tbd_lakehouse.sf import connect

pytest_plugins = ["tests.live.report"]


def pytest_configure(config):
    config.addinivalue_line("markers", "check(name): which exercise check this test belongs to")


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture(scope="session")
def sf():
    """sf(role) -> connection as TERRAFORM_SVC using that role (cached per role)."""
    conns = {}

    def _get(role: str):
        if role not in conns:
            conns[role] = connect(role)
        return conns[role]

    yield _get
    for c in conns.values():
        c.close()


@pytest.fixture(scope="session")
def sf_as():
    """sf_as(user) -> connection as a demo user (PAT), e.g. 'SUPPORT_USER'."""
    conns = {}
    roles = {"ANALYST_USER": "ANALYST", "SUPPORT_USER": "SUPPORT", "PII_ADMIN_USER": "PII_ADMIN"}

    def _get(user: str):
        if user not in conns:
            conns[user] = connect(roles[user], user=user)
        return conns[user]

    yield _get
    for c in conns.values():
        c.close()


@pytest.fixture(scope="session")
def gcs(settings):
    """Upload objects to the team's landing bucket."""
    from tbd_lakehouse.generators._io import GcsStorage

    return GcsStorage(settings.data_project_id, settings.landing_bucket)


@pytest.fixture(scope="session")
def run():
    """run(cmd) -> combined stdout/stderr; fails the test on a non-zero exit."""
    import subprocess

    from tbd_lakehouse.sf import SECRETS

    def _run(cmd: str) -> str:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=SECRETS.parent)
        out = p.stdout + p.stderr
        assert p.returncode == 0, f"{cmd} failed ({p.returncode}):\n{out[-3000:]}"
        return out

    return _run


DYNAMIC_TABLES = ("SILVER.ORDERS_LATEST", "SILVER.CLICKSTREAM", "GOLD.ORDERS_BY_COUNTRY_STATUS_RT")


@pytest.fixture(scope="session")
def frozen(sf):
    """Bring silver/gold up to date, then pause their refreshes so every engine reads the same snapshot.

    Only the dynamic tables and the dbt task are paused: pipes and the bridge keep running (bronze
    keeps growing), but silver/gold don't change until the fixture resumes them.
    """
    import time

    c = sf("PIPELINE_ADMIN").cursor()
    for dt in DYNAMIC_TABLES:
        c.execute(f"ALTER DYNAMIC TABLE LAKEHOUSE.{dt} REFRESH")
    c.execute("ALTER TASK LAKEHOUSE.OPS.RUN_DBT SUSPEND")
    t0 = c.execute("SELECT TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYY-MM-DD HH24:MI:SS.FF3 TZHTZM')").fetchone()[0]
    c.execute("EXECUTE TASK LAKEHOUSE.OPS.RUN_DBT")
    state = None
    for _ in range(60):
        time.sleep(10)
        rows = c.execute(
            "SELECT state FROM TABLE(LAKEHOUSE.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'RUN_DBT', "
            "SCHEDULED_TIME_RANGE_START => TO_TIMESTAMP_LTZ(%s, 'YYYY-MM-DD HH24:MI:SS.FF3 TZHTZM'))) WHERE database_name = 'LAKEHOUSE' AND state IN ('SUCCEEDED', 'FAILED')",
            (t0,)).fetchall()
        if rows:
            state = rows[0][0]
            break
    for dt in DYNAMIC_TABLES:
        c.execute(f"ALTER DYNAMIC TABLE LAKEHOUSE.{dt} SUSPEND")
    try:
        assert state == "SUCCEEDED", f"dbt run before the parity check: {state}"
        yield
    finally:
        for dt in DYNAMIC_TABLES:
            c.execute(f"ALTER DYNAMIC TABLE LAKEHOUSE.{dt} RESUME")
        c.execute("ALTER TASK LAKEHOUSE.OPS.RUN_DBT RESUME")
