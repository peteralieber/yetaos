from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_lxd_service, get_registry, get_store
from app.config import get_settings
from app.main import app
from app.profiles.registry import ProfileRegistry
from app.store.json_store import JsonStore


class FakeSnapshot:
    def __init__(self, name: str) -> None:
        self.name = name

    def restore(self, wait: bool = True) -> None:
        _ = wait


class FakeSnapshots:
    def __init__(self) -> None:
        self._snaps: dict[str, FakeSnapshot] = {}

    def create(self, name: str, stateful: bool = False, wait: bool = True) -> None:
        _ = (stateful, wait)
        self._snaps[name] = FakeSnapshot(name)

    def all(self) -> list[FakeSnapshot]:
        return list(self._snaps.values())

    def get(self, name: str) -> FakeSnapshot:
        return self._snaps[name]


class FakeContainer:
    def __init__(self, name: str, config: dict[str, str]) -> None:
        self.name = name
        self.config = config
        self.status = "stopped"
        self.snapshots = FakeSnapshots()

    def start(self, wait: bool = True) -> None:
        _ = wait
        self.status = "running"

    def stop(self, wait: bool = True) -> None:
        _ = wait
        self.status = "stopped"

    def delete(self, wait: bool = True) -> None:
        _ = wait


class FakeContainersCollection:
    def __init__(self) -> None:
        self._containers: dict[str, FakeContainer] = {}

    def create(self, definition: dict, wait: bool = True) -> FakeContainer:
        _ = wait
        name = definition["name"]
        container = FakeContainer(name=name, config=definition.get("config", {}))
        self._containers[name] = container
        return container

    def get(self, name: str) -> FakeContainer:
        return self._containers[name]


class FakeClient:
    def __init__(self) -> None:
        self.containers = FakeContainersCollection()


@pytest.fixture
def temp_paths(tmp_path: Path) -> dict[str, Path]:
    profiles_dir = tmp_path / "lxc" / "profiles"
    cloud_init_dir = tmp_path / "lxc" / "cloud-init"
    store_path = tmp_path / "containers.json"

    (profiles_dir / "service").mkdir(parents=True)
    (profiles_dir / "tool").mkdir(parents=True)
    (profiles_dir / "use-case").mkdir(parents=True)
    (cloud_init_dir / "service").mkdir(parents=True)
    (cloud_init_dir / "tool").mkdir(parents=True)

    (profiles_dir / "service" / "base.yaml").write_text(
        """
name: service/base
description: Base
category: service
depends: []
cloud_init: lxc/cloud-init/service/base.sh
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (profiles_dir / "tool" / "python.yaml").write_text(
        """
name: tool/python
description: Python
category: tool
depends:
  - service/base
cloud_init: lxc/cloud-init/tool/python.sh
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (profiles_dir / "use-case" / "dev.yaml").write_text(
        """
name: use-case/dev
description: Dev
category: use-case
depends:
  - service/base
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (cloud_init_dir / "service" / "base.sh").write_text(
        "mkdir -p /workspace\n",
        encoding="utf-8",
    )
    (cloud_init_dir / "tool" / "python.sh").write_text(
        "apt-get install -y python3\n",
        encoding="utf-8",
    )

    return {
        "profiles_dir": profiles_dir,
        "cloud_init_dir": cloud_init_dir,
        "store_path": store_path,
        "workspace": tmp_path,
    }


@pytest.fixture
def client(temp_paths: dict[str, Path]) -> Generator[TestClient, None, None]:
    settings = get_settings()
    settings.api_key = None
    settings.store_path = temp_paths["store_path"]
    settings.profiles_dir = temp_paths["profiles_dir"]
    settings.cloud_init_dir = temp_paths["cloud_init_dir"]
    settings.workspaces_dir = temp_paths["workspace"] / "workspaces"
    settings.secrets_dir = temp_paths["workspace"] / "secrets"

    fake_client = FakeClient()

    from app.lxd.containers import LXDContainerService

    app.dependency_overrides[get_store] = lambda: JsonStore(settings.store_path)
    app.dependency_overrides[get_registry] = lambda: ProfileRegistry(settings.profiles_dir)
    app.dependency_overrides[get_lxd_service] = lambda: LXDContainerService(
        socket_path="/tmp/fake.sock", client_factory=lambda _: fake_client
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
