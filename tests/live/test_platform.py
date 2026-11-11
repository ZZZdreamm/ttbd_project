import pytest

from tests.live.helpers import one, scalar

pytestmark = pytest.mark.check("7 Guardrails")


def test_guardrails_present(sf):
    c = sf("ACCOUNTADMIN")
    rm = one(c, "SHOW RESOURCE MONITORS LIKE 'RM_LAB'")
    assert float(rm["credit_quota"]) == 12
    assert rm["level"] == "ACCOUNT"
    for wh in ("WH_TRANSFORM", "WH_QUERY"):
        w = one(c, f"SHOW WAREHOUSES LIKE '{wh}'")
        assert w["size"] == "X-Small" and int(w["auto_suspend"]) == 60


def test_budget_limit_and_stop_action(sf):
    c = sf("ACCOUNTADMIN")
    assert int(scalar(c, "CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_SPENDING_LIMIT()")) == 12
    actions = c.cursor().execute("CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!GET_CUSTOM_ACTIONS()").fetchall()
    assert any("LAKEHOUSE.OPS.STOP_ALL" in str(a[1]) for a in actions), actions


def test_stop_all_tolerates_missing_objects(sf):
    c = sf("ACCOUNTADMIN")
    out = scalar(c, "CALL LAKEHOUSE.OPS.STOP_ALL()")  # no DCM objects yet: must not raise
    assert "INGEST_SVC" in out
    assert "refused" not in scalar(c, "CALL LAKEHOUSE.OPS.START_ALL()")
    assert one(c, "SHOW USERS LIKE 'INGEST_SVC'")["disabled"] == "false"


def test_external_volume_verifies(sf):
    r = scalar(sf("ACCOUNTADMIN"), "SELECT SYSTEM$VERIFY_EXTERNAL_VOLUME('EV_LAKEHOUSE')")
    assert '"success":true' in r.replace(" ", "")


def test_demo_users_log_in_with_pat_and_no_secondary_roles(sf_as):
    for user, role in (("ANALYST_USER", "ANALYST"), ("SUPPORT_USER", "SUPPORT"), ("PII_ADMIN_USER", "PII_ADMIN")):
        row = one(sf_as(user), "SELECT CURRENT_USER() u, CURRENT_ROLE() r, CURRENT_SECONDARY_ROLES() s")
        assert (row["U"], row["R"]) == (user, role)
        assert '"roles":""' in row["S"].replace(" ", ""), row["S"]
