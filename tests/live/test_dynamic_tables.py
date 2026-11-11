from datetime import datetime, timedelta, timezone

import pytest

from tests.live.helpers import all_rows, one, refresh, scalar, tag_refs

T0 = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=30)
COLS = ("EVENT_ID, EVENT_TYPE, EVENT_TS, ORDER_ID, CUSTOMER_ID, ITEMS_JSON, TOTAL_AMOUNT, CURRENCY, PAYMENT_METHOD, "
        "CARD_LAST4, IP_ADDRESS, SHIPPING_STREET, SHIPPING_CITY, SHIPPING_POSTAL_CODE, SHIPPING_COUNTRY, _INGESTED_AT")


@pytest.fixture
def insert_order_events(sf):
    """insert_order_events(order_id, [(event_id, type, ts)], ip=...) as PIPELINE_ADMIN; cleaned up after."""
    orders = []

    def _insert(order_id, events, ip="10.0.0.1"):
        orders.append(order_id)
        values = ", ".join(
            f"('{eid}', '{kind}', '{ts:%Y-%m-%d %H:%M:%S}'::TIMESTAMP_NTZ, '{order_id}', 'C000001', '[]', 10.00, 'EUR', "
            f"'card', '4242', '{ip}', 'ul. Testowa 1', 'Gdansk', '80-001', 'PL', CURRENT_TIMESTAMP())"
            for eid, kind, ts in events)
        sf("PIPELINE_ADMIN").cursor().execute(f"INSERT INTO LAKEHOUSE.BRONZE.ORDERS_EVENTS ({COLS}) VALUES {values}")

    yield _insert
    for o in orders:
        sf("PIPELINE_ADMIN").cursor().execute(f"DELETE FROM LAKEHOUSE.BRONZE.ORDERS_EVENTS WHERE ORDER_ID = '{o}'")


@pytest.mark.check("3 Streaming path")
def test_orders_latest_dedupes_and_orders_by_event_ts(sf, insert_order_events):
    m = timedelta(minutes=1)
    # out of order, with a duplicated event (redelivery)
    insert_order_events("O-T1", [("t1-e1", "placed", T0), ("t1-e3", "shipped", T0 + 2 * m), ("t1-e2", "paid", T0 + m),
                                 ("t1-e3", "shipped", T0 + 2 * m)])
    refresh(sf, "SILVER.ORDERS_LATEST")
    rows = all_rows(sf("PII_ADMIN"), "SELECT status FROM LAKEHOUSE.SILVER.ORDERS_LATEST WHERE order_id = 'O-T1'")
    assert rows == [("shipped",)]


@pytest.mark.check("6 Tag propagation")
def test_tags_propagated_to_orders_latest(sf):
    tags = tag_refs(sf("ACCOUNTADMIN"), "LAKEHOUSE.SILVER.ORDERS_LATEST")
    assert tags["IP_ADDRESS"] == "IP" and tags["CARD_LAST4"] == "CARD" and tags["SHIPPING_STREET"] == "ADDRESS"
    assert "SHIPPING_COUNTRY" not in tags and "SHIPPING_CITY" not in tags


@pytest.mark.check("6 Tag propagation")
def test_dt_stores_raw_and_masks_on_read(sf, insert_order_events):
    insert_order_events("O-T2", [("t2-e9", "placed", T0)], ip="10.20.30.40")
    refresh(sf, "SILVER.ORDERS_LATEST")
    q = "SELECT ip_address FROM LAKEHOUSE.SILVER.ORDERS_LATEST WHERE order_id = 'O-T2'"
    assert scalar(sf("PII_ADMIN"), q) == "10.20.30.40"   # refresh role (PIPELINE_ADMIN) was exempt
    assert scalar(sf("SUPPORT"), q) == "10.20.x.x"
    assert scalar(sf("ANALYST"), q) == "***"


@pytest.mark.check("3 Streaming path")
def test_target_lag_default_is_5_minutes(sf):
    for schema, name in (("SILVER", "ORDERS_LATEST"), ("SILVER", "CLICKSTREAM"), ("GOLD", "ORDERS_BY_COUNTRY_STATUS_RT")):
        dt = one(sf("PIPELINE_ADMIN"), f"SHOW DYNAMIC TABLES LIKE '{name}' IN SCHEMA LAKEHOUSE.{schema}")
        assert dt["target_lag"] == "5 minutes" and dt["owner"] == "PIPELINE_ADMIN" and dt["warehouse"] == "WH_TRANSFORM"


@pytest.mark.check("3 Streaming path")
def test_rt_gold_has_rows_and_no_tagged_columns(sf):
    refresh(sf, "GOLD.ORDERS_BY_COUNTRY_STATUS_RT")
    assert tag_refs(sf("ACCOUNTADMIN"), "LAKEHOUSE.GOLD.ORDERS_BY_COUNTRY_STATUS_RT") == {}
    cols = {r[2] for r in all_rows(sf("ACCOUNTADMIN"), "SHOW COLUMNS IN TABLE LAKEHOUSE.GOLD.ORDERS_BY_COUNTRY_STATUS_RT")}
    assert cols == {"SHIPPING_COUNTRY", "STATUS", "ORDER_COUNT", "REVENUE"}
    assert scalar(sf("ANALYST"), "SELECT COUNT(*) FROM LAKEHOUSE.GOLD.ORDERS_BY_COUNTRY_STATUS_RT") > 0
