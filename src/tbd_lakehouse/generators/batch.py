"""`mise run gen:batch`: drop customer/product/return NDJSON files into the landing bucket.

First drop: the full customer pool and product catalog. Later drops (every 3-5 minutes):
customer changes (updates + new customers), product changes and returns of recently
delivered order lines (written by the stream generator to .state/generators/<data project>/recent_orders.txt).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from random import Random

from tbd_lakehouse.config import Settings, load_settings
from tbd_lakehouse.generators import _io
from tbd_lakehouse.generators._io import GcsStorage, Storage
from tbd_lakehouse.model import customer_ids, make_customer, make_product, make_return, product_ids

POOL = 2000
CUSTOMER_CHANGES = 20
PRODUCT_CHANGES = 5
MAX_RETURNS = 10


def _ndjson(rows: list[dict]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


def _load_state(state_dir: Path) -> dict:
    p = state_dir / "batch_state.json"
    return json.loads(p.read_text()) if p.exists() else {"initialized": False, "next_customer": POOL + 1, "seq": 0}


def _save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "batch_state.json").write_text(json.dumps(state))


def _recent_orders(state_dir: Path) -> list[tuple[str, str]]:
    p = state_dir / "recent_orders.txt"
    if not p.exists():
        return []
    return [tuple(line.split()) for line in p.read_text().splitlines() if len(line.split()) == 2]


def drop(storage: Storage, rng: Random, state_dir: Path, now: datetime) -> list[str]:
    """Write one drop; returns the object names written."""
    state = _load_state(state_dir)
    if not state["initialized"]:
        customers = [make_customer(c, rng, now) for c in customer_ids(POOL)]
        products = [make_product(p, rng, now) for p in product_ids()]
        returns: list[dict] = []
        state["initialized"] = True
    else:
        n_new = rng.randint(3, 7)
        updated = rng.sample(customer_ids(POOL), CUSTOMER_CHANGES - n_new)
        new = [f"C{state['next_customer'] + i:06d}" for i in range(n_new)]
        state["next_customer"] += n_new
        customers = [make_customer(c, rng, now) for c in updated + new]
        products = [make_product(p, rng, now) for p in rng.sample(product_ids(), PRODUCT_CHANGES)]
        recent = _recent_orders(state_dir)
        picks = rng.sample(recent, min(MAX_RETURNS, len(recent))) if recent else []
        returns = [make_return(o, p, rng, now) for o, p in picks]

    stamp = now.strftime("%Y%m%dT%H%M%S")
    written = []
    for entity, rows in (("customers", customers), ("products", products), ("returns", returns)):
        if not rows:
            continue
        name = f"{entity}/{entity}-{stamp}-{state['seq']}.json"
        storage.upload(name, _ndjson(rows))
        written.append(name)
    state["seq"] += 1
    _save_state(state_dir, state)
    return written


def run(settings: Settings, min_interval: int = 180, max_interval: int = 300, seed: int | None = None,
        storage: Storage | None = None, once: bool = False, state_dir: Path | None = None) -> None:
    storage = storage or GcsStorage(settings.data_project_id, settings.landing_bucket)
    state_dir = state_dir or _io.state_dir_for(settings)
    rng = Random(seed)
    while True:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for name in drop(storage, rng, state_dir, now):
            print(f"gs://{settings.landing_bucket}/{name}", flush=True)
        if once:
            return
        wait = rng.randint(min_interval, max_interval)
        print(f"next drop in {wait}s (Ctrl-C to stop)", flush=True)
        time.sleep(wait)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="write a single drop and exit")
    ap.add_argument("--min-interval", type=int, default=180)
    ap.add_argument("--max-interval", type=int, default=300)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    try:
        run(load_settings(), a.min_interval, a.max_interval, a.seed, once=a.once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
