"""Check 1: what Terraform describes is what exists (run on the host: needs terraform + gcloud ADC)."""

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.check("1 Infra")
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("root", ["gcp", "snowflake"])
def test_terraform_roots_have_no_drift(root):
    env = {**os.environ, "TF_VAR_snowflake_account": os.environ["SNOWFLAKE_ACCOUNT"], "TF_IN_AUTOMATION": "1"}
    p = subprocess.run(["terraform", f"-chdir={ROOT / root}", "plan", "-detailed-exitcode", "-input=false", "-lock=false",
                        "-no-color"], capture_output=True, text=True, env=env)
    # 0 = no changes, 2 = changes pending, 1 = error
    assert p.returncode == 0, f"terraform plan in {root}/ exit {p.returncode}:\n{(p.stdout + p.stderr)[-1500:]}"


def test_expected_gcp_resources_exist(settings):
    from google.cloud import pubsub_v1, storage

    gcs = storage.Client(project=settings.data_project_id)
    for b in (settings.landing_bucket, settings.lakehouse_bucket):
        assert gcs.lookup_bucket(b) is not None, f"bucket {b} missing"
    sub = pubsub_v1.SubscriberClient()
    for s in ("orders-events-bridge", "clickstream-events-bridge", "landing-notifications-snowpipe"):
        sub.get_subscription(subscription=sub.subscription_path(settings.data_project_id, s))


def test_expected_snowflake_objects_exist(sf):
    c = sf("ACCOUNTADMIN").cursor()
    names = {r[1] for r in c.execute("SHOW SCHEMAS IN DATABASE LAKEHOUSE").fetchall()}
    assert {"BRONZE", "SILVER", "GOLD", "GOVERNANCE", "OPS"} <= names
    assert {r[1] for r in c.execute("SHOW ICEBERG TABLES IN SCHEMA LAKEHOUSE.BRONZE").fetchall()} >= {
        "ORDERS_EVENTS", "CLICKSTREAM_EVENTS", "CUSTOMERS_RAW", "PRODUCTS_RAW", "RETURNS_RAW"}
    pipes = {r[1] for r in c.execute("SHOW PIPES IN SCHEMA LAKEHOUSE.BRONZE").fetchall()}
    assert pipes == {"PIPE_CUSTOMERS", "PIPE_PRODUCTS", "PIPE_RETURNS", "PIPE_ORDERS_STREAM", "PIPE_CLICKS_STREAM"}
