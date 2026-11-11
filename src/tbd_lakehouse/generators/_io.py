"""Thin GCS / Pub/Sub clients (injectable fakes in tests) and local state paths."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

STATE_DIR = Path(__file__).resolve().parents[3] / ".state"


def state_dir_for(settings) -> Path:
    """Generator state is per environment: a new team_id starts with a full load again."""
    return STATE_DIR / "generators" / settings.data_project_id


class Storage(Protocol):
    def upload(self, name: str, data: str) -> None: ...


class Publisher(Protocol):
    def publish(self, topic: str, data: bytes) -> None: ...


class GcsStorage:
    def __init__(self, project: str, bucket: str):
        from google.cloud import storage

        self._bucket = storage.Client(project=project).bucket(bucket)

    def upload(self, name: str, data: str) -> None:
        self._bucket.blob(name).upload_from_string(data, content_type="application/x-ndjson")


class PubSubPublisher:
    def __init__(self):
        from google.cloud import pubsub_v1

        self._client = pubsub_v1.PublisherClient()
        self._futures = []

    def publish(self, topic: str, data: bytes) -> None:
        self._futures.append(self._client.publish(topic, data))
        if len(self._futures) >= 100:
            self.flush()

    def flush(self) -> None:
        for f in self._futures:
            f.result(timeout=60)
        self._futures.clear()
