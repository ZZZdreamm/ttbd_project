"""In-memory stand-ins for GCS and Pub/Sub used by generator tests."""


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, str] = {}

    def upload(self, name: str, data: str) -> None:
        self.objects[name] = data

    def names(self) -> list[str]:
        return sorted(self.objects)


class FakePublisher:
    def __init__(self):
        self.messages: list[tuple[str, bytes]] = []

    def publish(self, topic: str, data: bytes) -> None:
        self.messages.append((topic, data))
