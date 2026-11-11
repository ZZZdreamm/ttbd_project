import json
from datetime import datetime, timezone
from random import Random

import pytest

from tbd_lakehouse.bridge.main import Bridge, OffsetCounter
from tbd_lakehouse.bridge.mapping import BadMessage, TABLE_COLUMNS, to_row
from tbd_lakehouse.model import ORDER_COLUMNS, make_customer, make_order_lifecycle

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
ORDERS_EVENTS_COLUMNS = ORDER_COLUMNS


def order_json(i: int) -> bytes:
    ev = make_order_lifecycle(f"O{i}", make_customer("C000001", Random(i), NOW.replace(tzinfo=None)),
                              Random(i), NOW.replace(tzinfo=None))[0]
    return json.dumps(ev).encode()


class FakeMessage:
    def __init__(self, data: bytes):
        self.data, self.publish_time = data, NOW
        self.acked = self.nacked = False

    def ack(self):
        self.acked = True

    def nack(self):
        self.nacked = True


class FakeWriter:
    """Commits lag behind appends by `commit_lag` advance() calls."""

    def __init__(self, commit_lag: int = 0, fail: bool = False):
        self.rows, self.fail, self.commit_lag = [], fail, commit_lag
        self._appended, self._committed = [], None

    def append(self, rows):
        if self.fail:
            raise RuntimeError("channel invalid")
        self.rows += rows
        token = str(len(self.rows))
        self._appended.append(token)
        if self.commit_lag == 0:
            self._committed = token
        return token

    def advance(self):
        if self._appended:
            self._committed = self._appended[-1]

    def committed_offset(self):
        return self._committed


def test_ack_only_after_commit():
    w = FakeWriter(commit_lag=1); b = Bridge("s", "ORDERS_EVENTS", w)
    msgs = [FakeMessage(order_json(i)) for i in range(3)]
    b.handle(msgs); assert not any(m.acked for m in msgs)
    w.advance(); b.handle([]); assert all(m.acked for m in msgs)


def test_partial_commit_acks_only_committed_batches():
    w = FakeWriter(commit_lag=1); b = Bridge("s", "ORDERS_EVENTS", w)
    first, second = [FakeMessage(order_json(1))], [FakeMessage(order_json(2))]
    b.handle(first); w.advance(); b.handle(second)
    assert first[0].acked and not second[0].acked
    w.advance(); b.handle([])
    assert second[0].acked


def test_bad_message_is_acked_and_skipped():
    w = FakeWriter(); b = Bridge("s", "ORDERS_EVENTS", w)
    bad = FakeMessage(b"not json"); b.handle([bad]); w.advance(); b.handle([])
    assert bad.acked and w.rows == []


def test_writer_error_nacks_batch():
    w = FakeWriter(fail=True); b = Bridge("s", "ORDERS_EVENTS", w)
    m = FakeMessage(order_json(1)); b.handle([m]); assert m.nacked and not m.acked


def test_to_row_maps_all_bronze_columns():
    r = to_row("ORDERS_EVENTS", order_json(1), NOW)
    assert set(r) == ORDERS_EVENTS_COLUMNS | {"_ingested_at"}
    assert r["_ingested_at"] == NOW.isoformat()
    assert set(TABLE_COLUMNS) == {"ORDERS_EVENTS", "CLICKSTREAM_EVENTS"}


def test_to_row_rejects_missing_keys_and_non_objects():
    with pytest.raises(BadMessage):
        to_row("ORDERS_EVENTS", b'{"event_id": "x"}', NOW)
    with pytest.raises(BadMessage):
        to_row("ORDERS_EVENTS", b"[1, 2]", NOW)


def test_offset_counter_resumes_after_committed_token():
    c = OffsetCounter(last_committed="41")
    assert c.next_range(3) == ("42", "44") and c.next_range(1) == ("45", "45")
    assert OffsetCounter(None).next_range(2) == ("1", "2")


class FlakyWriter(FakeWriter):
    def __init__(self):
        super().__init__(fail=True)
        self.resets = 0

    def reset(self):
        self.resets += 1
        self.fail = False


def test_writer_is_reset_after_error_and_recovers():
    w = FlakyWriter(); b = Bridge("s", "ORDERS_EVENTS", w)
    m1 = FakeMessage(order_json(1)); b.handle([m1])
    assert m1.nacked and w.resets == 1
    m2 = FakeMessage(order_json(2)); b.handle([m2])
    assert m2.acked


def test_channel_suffix_from_env(monkeypatch):
    from tbd_lakehouse.bridge.main import channel_name
    assert channel_name("ORDERS_EVENTS") == "bridge-orders_events"
    monkeypatch.setenv("BRIDGE_CHANNEL_SUFFIX", "-test")
    assert channel_name("ORDERS_EVENTS") == "bridge-orders_events-test"


class PausedPipeWriter(FakeWriter):
    """`mise run stop`: the channel is closed and can't be reopened until `mise run start`."""

    def __init__(self):
        super().__init__(fail=True)
        self.paused, self.closed, self.resets = True, True, 0

    def committed_offset(self):
        if self.closed:
            raise RuntimeError("ClosedChannelError: channel is closed")
        return super().committed_offset()

    def reset(self):
        self.resets += 1
        if self.paused:
            raise RuntimeError("HTTP 409 ERR_PIPE_IN_INVALID_STATE")
        self.closed = self.fail = False


def test_bridge_survives_stop_and_recovers_after_start():
    w = PausedPipeWriter(); b = Bridge("s", "ORDERS_EVENTS", w, retry_seconds=0)
    m1 = FakeMessage(order_json(1)); b.handle([m1])           # append fails, reopen fails: no crash
    m2 = FakeMessage(order_json(2)); b.handle([m2])           # still stopped: kept for redelivery
    assert m1.nacked and m2.nacked and not m2.acked
    b.handle([])                                               # idle while stopped: no crash
    w.paused = False                                           # `mise run start`
    m3 = FakeMessage(order_json(3)); b.handle([m3])
    assert m3.acked and w.rows


def test_reopen_attempts_are_rate_limited():
    w = PausedPipeWriter(); b = Bridge("s", "ORDERS_EVENTS", w, retry_seconds=3600)
    for i in range(5):
        b.handle([FakeMessage(order_json(i))])
    assert w.resets == 1
