import json
from datetime import datetime, timedelta
from random import Random

from tbd_lakehouse.model import (
    CLICK_COLUMNS, CUSTOMER_COLUMNS, ORDER_COLUMNS, PRODUCT_COLUMNS, RETURN_COLUMNS,
    customer_ids, make_click, make_customer, make_order_lifecycle, make_product, make_return,
    price_for, product_ids,
)

NOW = datetime(2026, 11, 20, 12, 0, 0)


def test_id_spaces():
    assert customer_ids(3) == ["C000001", "C000002", "C000003"]
    assert product_ids(2) == ["P0001", "P0002"] and len(product_ids()) == 200 and len(customer_ids()) == 2000


def test_lifecycle_is_ordered_and_consistent():
    evs = make_order_lifecycle("O1", make_customer("C000001", Random(1), NOW), Random(1), NOW)
    assert evs[0]["event_type"] == "placed"
    assert [e["event_ts"] for e in evs] == sorted(e["event_ts"] for e in evs)
    assert len({e["event_id"] for e in evs}) == len(evs)
    assert {e["order_id"] for e in evs} == {"O1"}
    assert evs[-1]["event_type"] in {"delivered", "cancelled"}
    assert all(set(e) == ORDER_COLUMNS for e in evs)


def test_lifecycle_items_priced_from_catalog_and_total_matches():
    e = make_order_lifecycle("O2", make_customer("C000002", Random(2), NOW), Random(7), NOW)[0]
    items = json.loads(e["items_json"])
    assert 1 <= len(items) <= 3
    assert all(it["unit_price"] == price_for(it["product_id"]) for it in items)
    assert round(sum(it["qty"] * it["unit_price"] for it in items), 2) == e["total_amount"]


def test_card_last4_only_for_card_payments():
    for seed in range(30):
        e = make_order_lifecycle(f"O{seed}", make_customer("C000003", Random(seed), NOW), Random(seed), NOW)[0]
        assert (e["card_last4"] is not None) == (e["payment_method"] == "card")


def test_shipping_address_is_the_customers():
    c = make_customer("C000004", Random(4), NOW)
    e = make_order_lifecycle("O4", c, Random(4), NOW)[0]
    assert (e["shipping_street"], e["shipping_city"], e["shipping_country"]) == (c["street"], c["city"], c["country"])


def test_customer_has_all_pii_and_locale_matches_country():
    c = make_customer("C000001", Random(3), NOW)
    assert set(c) == CUSTOMER_COLUMNS
    assert c["country"] in {"PL", "DE", "NL"} and "@" in c["email"]
    assert c["updated_at"] == NOW.isoformat()


def test_same_seed_same_data():
    assert make_customer("C000009", Random(5), NOW) == make_customer("C000009", Random(5), NOW)


def test_product_click_return_shapes():
    assert set(make_product("P0001", Random(1), NOW)) == PRODUCT_COLUMNS
    assert make_product("P0001", Random(1), NOW)["unit_price"] == price_for("P0001")
    assert set(make_click("C000001", "P0001", Random(1), NOW)) == CLICK_COLUMNS
    r = make_return("O1", "P0001", Random(1), NOW + timedelta(days=1))
    assert set(r) == RETURN_COLUMNS and r["order_id"] == "O1" and r["qty"] >= 1
