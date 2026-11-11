import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import pytest

from tests.live.helpers import scalar, wait_until

pytestmark = pytest.mark.check("3 Streaming path")


def test_published_event_reaches_bronze(sf, settings):
    from google.cloud import pubsub_v1

    event_id = f"test-{uuid.uuid4()}"
    ev = {"event_id": event_id, "event_type": "placed", "event_ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
          "order_id": "O-TEST", "customer_id": "C000001", "items_json": "[]", "total_amount": 1.0, "currency": "EUR",
          "payment_method": "blik", "card_last4": None, "ip_address": "10.1.2.3", "shipping_street": "x",
          "shipping_city": "y", "shipping_postal_code": "z", "shipping_country": "PL"}
    pub = pubsub_v1.PublisherClient()
    pub.publish(f"projects/{settings.data_project_id}/topics/orders-events", json.dumps(ev).encode()).result(timeout=30)

    bridge = subprocess.Popen([sys.executable, "-m", "tbd_lakehouse.bridge.main"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              env={**os.environ, "BRIDGE_CHANNEL_SUFFIX": "-test"})  # don't steal a running bridge's channels
    try:
        q = f"SELECT COUNT(*) FROM LAKEHOUSE.BRONZE.ORDERS_EVENTS WHERE event_id = '{event_id}'"
        assert wait_until(lambda: scalar(sf("PIPELINE_ADMIN"), q) >= 1, timeout=120, interval=5), "event not in bronze within 2 min"
    finally:
        bridge.send_signal(signal.SIGINT)
        try:
            out, _ = bridge.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            bridge.kill()
            out, _ = bridge.communicate()
    # The Snowpipe Streaming runtime handles Ctrl-C itself (final flush) and re-raises SIGINT.
    assert bridge.returncode in (0, -signal.SIGINT), out[-2000:]
    assert "Traceback" not in out, out[-2000:]
    sf("PIPELINE_ADMIN").cursor().execute("DELETE FROM LAKEHOUSE.BRONZE.ORDERS_EVENTS WHERE order_id = 'O-TEST'")
