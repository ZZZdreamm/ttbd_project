import json
import re

import pytest

from tbd_lakehouse.config import load_settings
from tbd_lakehouse.generators import batch, stream
from tests.unit.fakes import FakePublisher, FakeStorage

ENV = {"TF_VAR_semester": "2026z", "TF_VAR_team_id": "07", "TF_VAR_billing_account": "x",
       "TF_VAR_notification_email": "a@b.pl", "SNOWFLAKE_ACCOUNT": "MYORG-TBD07"}


@pytest.fixture
def fake_storage():
    return FakeStorage()


def count_lines(storage, prefix):
    return sum(len(v.splitlines()) for k, v in storage.objects.items() if k.startswith(prefix))


def test_batch_first_drop_is_full_load(tmp_path, fake_storage):
    batch.run(load_settings(ENV), once=True, storage=fake_storage, seed=1, state_dir=tmp_path)
    assert count_lines(fake_storage, "customers/") == 2000
    assert count_lines(fake_storage, "products/") == 200
    first = json.loads(next(v for k, v in fake_storage.objects.items() if k.startswith("customers/")).splitlines()[0])
    assert first["customer_id"] == "C000001" and "email" in first


def test_batch_later_drop_is_incremental_and_names_files(tmp_path, fake_storage):
    s = load_settings(ENV)
    batch.run(s, once=True, storage=fake_storage, seed=1, state_dir=tmp_path)
    before = dict(fake_storage.objects)
    batch.run(s, once=True, storage=fake_storage, seed=2, state_dir=tmp_path)
    new = {k: v for k, v in fake_storage.objects.items() if k not in before}
    assert count_lines(FakeStorageView(new), "customers/") == 20
    assert count_lines(FakeStorageView(new), "products/") == 5
    assert all(re.fullmatch(r"(customers|products|returns)/\1-\d{8}T\d{6}-\d+\.json", n) for n in fake_storage.names())
    ids = [json.loads(l)["customer_id"] for k, v in new.items() if k.startswith("customers/") for l in v.splitlines()]
    assert any(int(i[1:]) > 2000 for i in ids) and any(int(i[1:]) <= 2000 for i in ids)  # new + updated


def test_returns_skipped_without_recent_orders(tmp_path, fake_storage):
    s = load_settings(ENV)
    batch.run(s, once=True, storage=fake_storage, seed=1, state_dir=tmp_path)
    batch.run(s, once=True, storage=fake_storage, seed=2, state_dir=tmp_path)
    assert not [n for n in fake_storage.names() if n.startswith("returns/")]


def test_returns_reference_recent_delivered_orders(tmp_path, fake_storage):
    s = load_settings(ENV)
    batch.run(s, once=True, storage=fake_storage, seed=1, state_dir=tmp_path)
    (tmp_path / "recent_orders.txt").write_text("O-a P0001\nO-b P0002\n")
    batch.run(s, once=True, storage=fake_storage, seed=2, state_dir=tmp_path)
    rows = [json.loads(l) for k, v in fake_storage.objects.items() if k.startswith("returns/") for l in v.splitlines()]
    assert rows and {(r["order_id"], r["product_id"]) for r in rows} <= {("O-a", "P0001"), ("O-b", "P0002")}


def test_stream_publishes_orders_and_clicks_and_records_delivered(tmp_path):
    pub = FakePublisher()
    stream.run(load_settings(ENV), rate=1000, seed=3, publisher=pub, state_dir=tmp_path, max_events=1500,
               time_scale=1000)
    topics = {t for t, _ in pub.messages}
    assert topics == {"projects/tbd-2026z-stud07-data/topics/orders-events", "projects/tbd-2026z-stud07-data/topics/clickstream-events"}
    orders = [json.loads(d) for t, d in pub.messages if t.endswith("orders-events")]
    clicks = [d for t, d in pub.messages if t.endswith("clickstream-events")]
    assert len(clicks) > len(orders) > 0
    assert 2 <= len(clicks) / len(orders) <= 4.5  # ~1 order event per 3 clicks
    assert any(o["event_type"] == "delivered" for o in orders)
    lines = (tmp_path / "recent_orders.txt").read_text().split("\n")
    assert all(re.fullmatch(r"\S+ P\d{4}", l) for l in lines if l)


class FakeStorageView:
    def __init__(self, objects):
        self.objects = objects


def test_generator_state_is_per_environment(tmp_path, monkeypatch, fake_storage):
    """A new team (or a rebuild under a new team_id) starts with a full load again."""
    from tbd_lakehouse.generators import _io

    monkeypatch.setattr(_io, "STATE_DIR", tmp_path)
    batch.run(load_settings(ENV), once=True, storage=fake_storage, seed=1)
    other = FakeStorage()
    batch.run(load_settings({**ENV, "TF_VAR_team_id": "08"}), once=True, storage=other, seed=1)
    assert count_lines(other, "customers/") == 2000
    assert _io.state_dir_for(load_settings(ENV)) != _io.state_dir_for(load_settings({**ENV, "TF_VAR_team_id": "08"}))
    assert _io.state_dir_for(load_settings(ENV)).parent.parent == tmp_path
