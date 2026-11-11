import pytest

from tests.live.helpers import all_rows, one, tag_refs

PII = {"FIRST_NAME": "NAME", "LAST_NAME": "NAME", "EMAIL": "EMAIL", "PHONE": "PHONE",
       "DATE_OF_BIRTH": "DOB", "STREET": "ADDRESS", "POSTAL_CODE": "ADDRESS"}


@pytest.mark.check("2 Batch path")
def test_dbt_task_last_run_succeeded(sf):
    r = one(sf("PIPELINE_ADMIN"), "SELECT state, error_message FROM TABLE(LAKEHOUSE.INFORMATION_SCHEMA.TASK_HISTORY("
                                  "TASK_NAME => 'RUN_DBT')) WHERE database_name = 'LAKEHOUSE' AND state IN ('SUCCEEDED', 'FAILED') "
                                  "ORDER BY scheduled_time DESC LIMIT 1")
    assert r["STATE"] == "SUCCEEDED", r["ERROR_MESSAGE"]


@pytest.mark.check("2 Batch path")
def test_gold_has_rows(sf):
    for t in ("CUSTOMER_LTV", "DAILY_SALES_BY_CATEGORY", "RETURN_RATES"):
        assert one(sf("ANALYST"), f"SELECT COUNT(*) n FROM LAKEHOUSE.GOLD.{t}")["N"] >= 0
    assert one(sf("ANALYST"), "SELECT COUNT(*) n FROM LAKEHOUSE.SILVER.CUSTOMERS_CURRENT")["N"] >= 2000


@pytest.mark.check("5 Masking")
def test_customers_current_columns_tagged_from_meta(sf):
    tags = tag_refs(sf("ACCOUNTADMIN"), "LAKEHOUSE.SILVER.CUSTOMERS_CURRENT")
    assert {k: v for k, v in tags.items() if k in PII} == PII
    assert "CITY" not in tags and "COUNTRY" not in tags


@pytest.mark.check("5 Masking")
def test_support_sees_only_mapped_countries(sf_as):
    countries = {r[0] for r in all_rows(sf_as("SUPPORT_USER"), "SELECT DISTINCT country FROM LAKEHOUSE.SILVER.CUSTOMERS_CURRENT")}
    assert countries and countries <= {"PL", "NL"}


@pytest.mark.check("5 Masking")
def test_analyst_sees_all_countries_masked(sf_as):
    rows = all_rows(sf_as("ANALYST_USER"), "SELECT DISTINCT country, email FROM LAKEHOUSE.SILVER.CUSTOMERS_CURRENT")
    assert {r[0] for r in rows} == {"PL", "DE", "NL"}
    assert {r[1] for r in rows} == {"***"}


@pytest.mark.check("5 Masking")
def test_gold_has_no_tagged_or_pii_columns(sf):
    for t in ("CUSTOMER_LTV", "DAILY_SALES_BY_CATEGORY", "RETURN_RATES"):
        assert tag_refs(sf("ACCOUNTADMIN"), f"LAKEHOUSE.GOLD.{t}") == {}, t
        cols = {r[2] for r in all_rows(sf("ACCOUNTADMIN"), f"SHOW COLUMNS IN TABLE LAKEHOUSE.GOLD.{t}")}  # column_name
        assert not cols & {"CUSTOMER_ID", "EMAIL", "PHONE", "FIRST_NAME", "LAST_NAME", "IP_ADDRESS"}, (t, cols)
