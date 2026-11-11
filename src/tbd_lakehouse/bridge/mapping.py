"""Pub/Sub message JSON -> bronze row (keys match bronze columns, case-insensitively)."""

from __future__ import annotations

import json
from datetime import datetime

from tbd_lakehouse.model import CLICK_COLUMNS, ORDER_COLUMNS

TABLE_COLUMNS = {"ORDERS_EVENTS": ORDER_COLUMNS, "CLICKSTREAM_EVENTS": CLICK_COLUMNS}
REQUIRED = {"event_id", "event_type", "event_ts"}


class BadMessage(ValueError):
    """The payload can't become a bronze row; it is acked and skipped (never blocks the stream)."""


def to_row(table: str, payload: bytes, publish_time: datetime) -> dict:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise BadMessage(f"not JSON: {e}") from e
    if not isinstance(data, dict):
        raise BadMessage("payload is not a JSON object")
    missing = REQUIRED - data.keys()
    if missing:
        raise BadMessage(f"missing keys: {sorted(missing)}")
    row = {col: data.get(col) for col in TABLE_COLUMNS[table]}
    row["_ingested_at"] = publish_time.isoformat()
    return row
