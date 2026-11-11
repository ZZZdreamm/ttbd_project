"""`mise run bridge`: Pub/Sub -> Snowpipe Streaming (high-performance SDK) -> bronze Iceberg tables.

At-least-once: a message is acked only after Snowflake has committed the batch that holds it,
so a crash or Ctrl-C re-delivers it. Duplicates are removed downstream (dedup by event_id).
"""

from __future__ import annotations

import logging
import os
import signal
import time
from typing import Protocol

from tbd_lakehouse.bridge.mapping import BadMessage, to_row
from tbd_lakehouse.config import Settings, load_settings

log = logging.getLogger("bridge")

ROUTES = {  # subscription -> (bronze table, streaming pipe)
    "orders-events-bridge": ("ORDERS_EVENTS", "PIPE_ORDERS_STREAM"),
    "clickstream-events-bridge": ("CLICKSTREAM_EVENTS", "PIPE_CLICKS_STREAM"),
}


def channel_name(table: str) -> str:
    """Stable per-table channel (offsets resume across restarts); tests add a suffix."""
    return f"bridge-{table.lower()}{os.environ.get('BRIDGE_CHANNEL_SUFFIX', '')}"


class Message(Protocol):
    data: bytes
    publish_time: object

    def ack(self) -> None: ...
    def nack(self) -> None: ...


class Writer(Protocol):
    def append(self, rows: list[dict]) -> str: ...
    def committed_offset(self) -> str | None: ...


class OffsetCounter:
    """Monotonic integer offset tokens per channel, continuing after the last committed one."""

    def __init__(self, last_committed: str | None):
        self._last = int(last_committed) if last_committed else 0

    def next_range(self, n: int) -> tuple[str, str]:
        start, self._last = self._last + 1, self._last + n
        return str(start), str(self._last)


class Bridge:
    def __init__(self, subscription: str, table: str, writer: Writer, batch_size: int = 500,
                 flush_seconds: float = 2.0, retry_seconds: float = 15.0):
        self.subscription, self.table, self.writer = subscription, table, writer
        self.batch_size, self.flush_seconds, self.retry_seconds = batch_size, flush_seconds, retry_seconds
        self._pending: list[tuple[int, list[Message]]] = []  # (end offset, messages) awaiting commit
        self._broken = False  # channel closed and not reopened yet (e.g. after `mise run stop`)
        self._last_reopen = float("-inf")

    def handle(self, messages: list[Message]) -> None:
        rows, good = [], []
        for m in messages:
            try:
                rows.append(to_row(self.table, m.data, m.publish_time))
                good.append(m)
            except BadMessage as e:
                log.warning("%s: skipping bad message (%s)", self.subscription, e)
                m.ack()
        if self._broken and not self._reopen():
            for m in good:  # Pub/Sub keeps them until the channel is back
                m.nack()
            return
        if rows:
            try:
                token = self.writer.append(rows)
            except Exception as e:  # channel errors: let Pub/Sub redeliver, reopen the channel
                log.error("%s: append failed, nacking %d messages: %s", self.subscription, len(good), e)
                for m in good:
                    m.nack()
                self._break()
                return
            self._pending.append((int(token), good))
        try:
            self._ack_committed()
        except Exception as e:
            log.error("%s: channel lost while waiting for commits: %s", self.subscription, e)
            self._break()

    def _break(self) -> None:
        self._pending.clear()  # their offsets will never commit on a reopened channel
        self._broken = True
        self._reopen()

    def _reopen(self) -> bool:
        """Reopen the channel, at most every retry_seconds; True when it's usable again."""
        reset = getattr(self.writer, "reset", None)
        if reset is None:
            self._broken = False
            return True
        now = time.monotonic()
        if now - self._last_reopen < self.retry_seconds:
            return False
        self._last_reopen = now
        try:
            reset()
        except Exception as e:
            log.error("%s: could not reopen channel yet (retrying every %.0fs; `mise run start` "
                      "resumes the pipes): %s", self.subscription, self.retry_seconds, e)
            return False
        log.info("%s: channel reopened", self.subscription)
        self._broken = False
        return True

    def _ack_committed(self) -> None:
        committed = self.writer.committed_offset()
        if committed is None:
            return
        done = int(committed)
        while self._pending and self._pending[0][0] <= done:
            for m in self._pending.pop(0)[1]:
                m.ack()

    @property
    def pending(self) -> int:
        return sum(len(ms) for _, ms in self._pending)


class SnowpipeWriter:
    """One Snowpipe Streaming channel (high-performance architecture) on a pipe."""

    def __init__(self, settings: Settings, pipe: str, channel: str, private_key_pem: str):
        self._props = {
            "account": settings.snowflake_account,
            "user": "INGEST_SVC",
            "role": "INGEST",
            "private_key": private_key_pem,
            "url": f"https://{settings.snowflake_account.lower()}.snowflakecomputing.com",
        }
        self._pipe, self._name = pipe, channel
        self._client = None
        self._open()

    def _open(self) -> None:
        from snowflake.ingest.streaming import StreamingIngestClient

        if self._client is None:
            self._client = StreamingIngestClient(f"bridge-{self._name}", "LAKEHOUSE", "BRONZE", self._pipe,
                                                 properties=self._props)
        self._channel, _ = self._client.open_channel(self._name)
        self._offsets = OffsetCounter(self._channel.get_latest_committed_offset_token())

    def reset(self) -> None:
        """Recreate client and channel: after `mise run stop` the SDK invalidates the whole client."""
        for close in (lambda: self._channel.close(wait_for_flush=False), lambda: self._client.close()):
            try:
                close()
            except Exception:
                pass
        self._client = None
        self._open()

    def append(self, rows: list[dict]) -> str:
        start, end = self._offsets.next_range(len(rows))
        self._channel.append_rows(rows, start_offset_token=start, end_offset_token=end)
        return end

    def committed_offset(self) -> str | None:
        return self._channel.get_latest_committed_offset_token()

    def close(self) -> None:
        self._channel.close()
        self._client.close()


class _PulledMessage:
    def __init__(self, subscriber, subscription_path: str, received):
        self._sub, self._path, self._ack_id = subscriber, subscription_path, received.ack_id
        self.data = received.message.data
        self.publish_time = received.message.publish_time

    def ack(self) -> None:
        self._sub.acknowledge(subscription=self._path, ack_ids=[self._ack_id])

    def nack(self) -> None:
        self._sub.modify_ack_deadline(subscription=self._path, ack_ids=[self._ack_id], ack_deadline_seconds=0)


def run(settings: Settings, batch_size: int = 500) -> None:
    from google.api_core import exceptions as gexc
    from google.cloud import pubsub_v1

    from tbd_lakehouse.sf import SECRETS

    pem = (SECRETS / "ingest_svc.p8").read_text()
    subscriber = pubsub_v1.SubscriberClient()
    bridges, writers = {}, []
    for sub, (table, pipe) in ROUTES.items():
        w = SnowpipeWriter(settings, pipe, channel_name(table), pem)
        writers.append(w)
        bridges[subscriber.subscription_path(settings.data_project_id, sub)] = Bridge(sub, table, w, batch_size)

    stop = {"now": False}
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.update(now=True))

    log.info("bridging %s -> LAKEHOUSE.BRONZE (Ctrl-C to stop)", ", ".join(ROUTES))
    totals = {p: 0 for p in bridges}
    last_report = time.monotonic()
    while not stop["now"]:
        for path, bridge in bridges.items():
            try:
                resp = subscriber.pull(request={"subscription": path, "max_messages": batch_size}, timeout=10)
                received = resp.received_messages
            except (gexc.DeadlineExceeded, gexc.ServiceUnavailable):
                received = []  # an empty subscription can time out instead of returning nothing
            msgs = [_PulledMessage(subscriber, path, r) for r in received]
            bridge.handle(msgs)
            totals[path] += len(msgs)
        if time.monotonic() - last_report > 30:
            log.info("received so far: %s", {p.rsplit('/', 1)[-1]: n for p, n in totals.items()})
            last_report = time.monotonic()
        time.sleep(0.5)

    log.info("stopping: waiting for the last commits")
    deadline = time.monotonic() + 30
    while any(b.pending for b in bridges.values()) and time.monotonic() < deadline:
        for b in bridges.values():
            b.handle([])
        time.sleep(1)
    for w in writers:
        w.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("snowflake", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    run(load_settings())


if __name__ == "__main__":
    main()
