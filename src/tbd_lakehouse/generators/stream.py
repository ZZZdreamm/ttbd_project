"""`mise run gen:stream`: publish order-lifecycle and clickstream events to Pub/Sub.

Each order emits placed -> paid -> shipped -> delivered (or cancelled) as its event times
come due, so statuses change in near-real-time. Delivered order lines are appended to
.state/generators/<data project>/recent_orders.txt so the batch generator can create returns for them.
"""

from __future__ import annotations

import argparse
import heapq
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random

from tbd_lakehouse.config import Settings, load_settings
from tbd_lakehouse.generators import _io
from tbd_lakehouse.generators._io import Publisher, PubSubPublisher
from tbd_lakehouse.model import customer_ids, make_click, make_customer, make_order_lifecycle, product_ids

KEEP_RECENT = 1000
# An order emits ~4 lifecycle events; starting one every 12 ticks gives ~1 order event per 3 clicks.
ORDER_EVERY = 12


def _record_delivered(state_dir: Path, event: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "recent_orders.txt"
    lines = p.read_text().splitlines() if p.exists() else []
    lines += [f"{event['order_id']} {it['product_id']}" for it in json.loads(event["items_json"])]
    p.write_text("\n".join(lines[-KEEP_RECENT:]) + "\n")


def run(settings: Settings, rate: float = 2.0, seed: int | None = None, publisher: Publisher | None = None,
        state_dir: Path | None = None, max_events: int | None = None, time_scale: float = 1.0) -> None:
    """rate = events per second; time_scale > 1 compresses order lifecycles (tests)."""
    publisher = publisher or PubSubPublisher()
    state_dir = state_dir or _io.state_dir_for(settings)
    topics = {
        "orders": f"projects/{settings.data_project_id}/topics/orders-events",
        "clicks": f"projects/{settings.data_project_id}/topics/clickstream-events",
    }
    rng = Random(seed)
    pending: list[tuple[datetime, int, dict]] = []  # (due, tiebreak, event)
    sim_start = datetime.now(timezone.utc).replace(tzinfo=None)
    wall_start = time.monotonic()
    tick, sent = 0, 0

    def now() -> datetime:
        return sim_start + timedelta(seconds=(time.monotonic() - wall_start) * time_scale)

    while max_events is None or sent < max_events:
        t = now()
        while pending and pending[0][0] <= t:
            _, _, ev = heapq.heappop(pending)
            publisher.publish(topics["orders"], json.dumps(ev).encode())
            sent += 1
            if ev["event_type"] == "delivered":
                _record_delivered(state_dir, ev)
        cid = rng.choice(customer_ids())
        if tick % ORDER_EVERY == 0:
            customer = make_customer(cid, Random(cid), t)  # stable address per customer
            order_id = f"O-{t:%Y%m%d%H%M%S}-{rng.randint(0, 99999):05d}"
            for ev in make_order_lifecycle(order_id, customer, rng, t):
                heapq.heappush(pending, (datetime.fromisoformat(ev["event_ts"]), tick, ev))
        else:
            publisher.publish(topics["clicks"], json.dumps(make_click(cid, rng.choice(product_ids()), rng, t)).encode())
            sent += 1
        tick += 1
        time.sleep(1 / rate)
    if hasattr(publisher, "flush"):
        publisher.flush()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rate", type=float, default=2.0, help="events per second (default 2)")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    s = load_settings()
    print(f"publishing to projects/{s.data_project_id}/topics/{{orders,clickstream}}-events at {a.rate}/s (Ctrl-C to stop)")
    try:
        run(s, rate=a.rate, seed=a.seed)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
