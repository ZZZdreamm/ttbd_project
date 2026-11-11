import json
from datetime import datetime, timezone
from random import Random
from uuid import uuid4

import pytest

from tbd_lakehouse.model import make_customer
from tests.live.helpers import one, scalar, wait_until

pytestmark = pytest.mark.check("2 Batch path")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_dropped_file_reaches_bronze(sf, gcs):
    cid = f"T-{uuid4().hex[:8]}"
    row = make_customer(cid, Random(1), _now())
    gcs.upload(f"customers/customers-{_now():%Y%m%dT%H%M%S}-test.json", json.dumps(row) + "\n")
    q = f"SELECT COUNT(*) FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW WHERE customer_id = '{cid}'"
    assert wait_until(lambda: scalar(sf("PIPELINE_ADMIN"), q) == 1, timeout=360), "file not auto-ingested within 6 min (Snowpipe latency is usually 1-4 min)"
    meta = one(sf("PIPELINE_ADMIN"), f"SELECT _file, _ingested_at FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW WHERE customer_id = '{cid}'")
    assert meta["_FILE"].startswith("customers/customers-") and meta["_INGESTED_AT"] is not None
    sf("PIPELINE_ADMIN").cursor().execute(f"DELETE FROM LAKEHOUSE.BRONZE.CUSTOMERS_RAW WHERE customer_id = '{cid}'")


def test_all_auto_ingest_pipes_running(sf):
    for pipe in ("PIPE_CUSTOMERS", "PIPE_PRODUCTS", "PIPE_RETURNS"):
        status = json.loads(scalar(sf("PIPELINE_ADMIN"), f"SELECT SYSTEM$PIPE_STATUS('LAKEHOUSE.BRONZE.{pipe}')"))
        assert status["executionState"] in ("RUNNING", "PAUSED"), status
        assert status["notificationChannelName"].endswith("/subscriptions/landing-notifications-snowpipe")


def test_dcm_redeploy_is_noop(run):
    out = run("mise run dcm")
    assert "No changes" in out, out[-2000:]
