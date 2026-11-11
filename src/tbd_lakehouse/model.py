"""Synthetic e-commerce data with customer PII (EU locales).

Keys match the bronze table columns (lowercase; Snowflake matches case-insensitively).
Timestamps are ISO-8601 strings in UTC without offset (bronze uses TIMESTAMP_NTZ).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from random import Random

from faker import Faker

COUNTRIES = {"PL": "pl_PL", "DE": "de_DE", "NL": "nl_NL"}
CATEGORIES = ["books", "electronics", "garden", "toys", "sports", "home", "beauty", "fashion"]
PAYMENT_METHODS = ["card", "card", "blik", "paypal", "ideal"]
RETURN_REASONS = ["damaged", "wrong size", "not as described", "changed mind", "late delivery"]
PAGES = ["home", "search", "product", "cart", "checkout"]

CUSTOMER_COLUMNS = {"customer_id", "first_name", "last_name", "email", "phone", "date_of_birth",
                    "street", "city", "postal_code", "country", "updated_at"}
PRODUCT_COLUMNS = {"product_id", "name", "category", "unit_price", "updated_at"}
RETURN_COLUMNS = {"return_id", "order_id", "product_id", "qty", "reason", "returned_at"}
ORDER_COLUMNS = {"event_id", "event_type", "event_ts", "order_id", "customer_id", "items_json",
                 "total_amount", "currency", "payment_method", "card_last4", "ip_address",
                 "shipping_street", "shipping_city", "shipping_postal_code", "shipping_country"}
CLICK_COLUMNS = {"event_id", "event_type", "event_ts", "session_id", "customer_id", "product_id",
                 "page", "ip_address"}

_FAKERS: dict[str, Faker] = {}


def _faker(locale: str, rng: Random) -> Faker:
    fk = _FAKERS.setdefault(locale, Faker(locale))
    fk.seed_instance(rng.getrandbits(32))
    return fk


def _uuid(rng: Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _ts(t: datetime) -> str:
    return t.isoformat()


def customer_ids(n: int = 2000) -> list[str]:
    return [f"C{i:06d}" for i in range(1, n + 1)]


def product_ids(n: int = 200) -> list[str]:
    return [f"P{i:04d}" for i in range(1, n + 1)]


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16)


def price_for(product_id: str) -> float:
    """Stable catalog price, so orders and the product feed agree."""
    return round(5 + (_h(product_id) % 19500) / 100, 2)


def category_for(product_id: str) -> str:
    return CATEGORIES[_h("cat" + product_id) % len(CATEGORIES)]


def make_customer(customer_id: str, rng: Random, updated_at: datetime) -> dict:
    country = rng.choice(list(COUNTRIES))
    fk = _faker(COUNTRIES[country], rng)
    first, last = fk.first_name(), fk.last_name()
    local = f"{first}.{last}".lower().replace(" ", "")
    local = "".join(ch for ch in local if ch.isascii() and (ch.isalnum() or ch == "."))
    dob = fk.date_of_birth(minimum_age=18, maximum_age=80)
    return {
        "customer_id": customer_id,
        "first_name": first,
        "last_name": last,
        "email": f"{local}{rng.randint(1, 99)}@{fk.free_email_domain()}",
        "phone": fk.phone_number(),
        "date_of_birth": dob.isoformat(),
        "street": fk.street_address(),
        "city": fk.city(),
        "postal_code": fk.postcode(),
        "country": country,
        "updated_at": _ts(updated_at),
    }


def make_product(product_id: str, rng: Random, updated_at: datetime) -> dict:
    fk = _faker("en_US", rng)
    return {
        "product_id": product_id,
        "name": f"{fk.color_name()} {fk.word()} {category_for(product_id)[:-1] or 'item'}".title(),
        "category": category_for(product_id),
        "unit_price": price_for(product_id),
        "updated_at": _ts(updated_at),
    }


def make_order_lifecycle(order_id: str, customer: dict, rng: Random, start: datetime) -> list[dict]:
    """placed -> paid -> shipped -> delivered, or placed -> cancelled; increasing event_ts."""
    items = [
        {"product_id": pid, "qty": rng.randint(1, 3), "unit_price": price_for(pid)}
        for pid in rng.sample(product_ids(), rng.randint(1, 3))
    ]
    total = round(sum(i["qty"] * i["unit_price"] for i in items), 2)
    method = rng.choice(PAYMENT_METHODS)
    fk = _faker(COUNTRIES[customer["country"]], rng)
    base = {
        "order_id": order_id,
        "customer_id": customer["customer_id"],
        "items_json": json.dumps(items),
        "total_amount": total,
        "currency": "EUR",
        "payment_method": method,
        "card_last4": f"{rng.randint(0, 9999):04d}" if method == "card" else None,
        "ip_address": fk.ipv4_public(),
        "shipping_street": customer["street"],
        "shipping_city": customer["city"],
        "shipping_postal_code": customer["postal_code"],
        "shipping_country": customer["country"],
    }
    if rng.random() < 0.1:
        steps = [("placed", 0), ("cancelled", rng.randint(20, 120))]
    else:
        steps = [("placed", 0), ("paid", rng.randint(5, 30)), ("shipped", rng.randint(60, 180)),
                 ("delivered", rng.randint(120, 360))]
    t, events = start, []
    for kind, delay in steps:
        t = t + timedelta(seconds=delay)
        events.append({**base, "event_id": _uuid(rng), "event_type": kind, "event_ts": _ts(t)})
    return events


def make_click(customer_id: str, product_id: str, rng: Random, at: datetime) -> dict:
    page = rng.choice(PAGES)
    return {
        "event_id": _uuid(rng),
        "event_type": "add_to_cart" if page == "product" and rng.random() < 0.3 else "page_view",
        "event_ts": _ts(at),
        "session_id": _uuid(rng)[:8],
        "customer_id": customer_id,
        "product_id": product_id,
        "page": page,
        "ip_address": _faker("en_US", rng).ipv4_public(),
    }


def make_return(order_id: str, product_id: str, rng: Random, at: datetime) -> dict:
    return {
        "return_id": _uuid(rng),
        "order_id": order_id,
        "product_id": product_id,
        "qty": 1,
        "reason": rng.choice(RETURN_REASONS),
        "returned_at": _ts(at),
    }
