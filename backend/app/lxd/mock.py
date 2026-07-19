from functools import lru_cache
from typing import Any

from app.lxd.containers import LXDContainerService


class MockSnapshot:
    def __init__(self, name: str) -> None:
        self.name = name

    def restore(self, wait: bool = True) -> None:
        _ = wait


class MockSnapshots:
    def __init__(self) -> None:
        self._snapshots: dict[str, MockSnapshot] = {}

    def create(self, name: str, stateful: bool = False, wait: bool = True) -> None:
        _ = (stateful, wait)
        self._snapshots[name] = MockSnapshot(name)

    def all(self) -> list[MockSnapshot]:
        return list(self._snapshots.values())

    def get(self, name: str) -> MockSnapshot:
        return self._snapshots[name]


class MockFiles:
    def get(self, path: str) -> bytes:
        _ = path
        return b"mock-workspace-archive"


class MockContainer:
    def __init__(self, name: str, config: dict[str, str], collection: "MockContainersCollection") -> None:
        self.name = name
        self.config = config
        self.status = "stopped"
        self.snapshots = MockSnapshots()
        self.files = MockFiles()
        self._collection = collection

    def start(self, wait: bool = True) -> None:
        _ = wait
        self.status = "running"

    def stop(self, wait: bool = True) -> None:
        _ = wait
        self.status = "stopped"

    def delete(self, wait: bool = True) -> None:
        _ = wait
        self._collection.remove(self.name)

    def execute(self, cmd: list[str], environment: dict[str, str] | None = None) -> tuple[int, str, str]:
        _ = (cmd, environment)
        return (0, "", "")


class MockContainersCollection:
    def __init__(self) -> None:
        self._containers: dict[str, MockContainer] = {}

    def create(self, definition: dict[str, Any], wait: bool = True) -> MockContainer:
        _ = wait
        name = str(definition["name"])
        container = MockContainer(name=name, config=definition.get("config", {}), collection=self)
        self._containers[name] = container
        return container

    def get(self, name: str) -> MockContainer:
        return self._containers[name]

    def remove(self, name: str) -> None:
        self._containers.pop(name, None)


class MockLXDClient:
    def __init__(self) -> None:
        self.containers = MockContainersCollection()


@lru_cache(maxsize=1)
def get_mock_lxd_service() -> LXDContainerService:
    client = MockLXDClient()
    return LXDContainerService(socket_path="/tmp/mock-lxd.sock", client_factory=lambda _: client)
