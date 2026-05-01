from datetime import UTC, datetime

from app.store.json_store import JsonStore
from app.store.models import ContainerRecord


def test_store_upsert_and_delete(tmp_path) -> None:
    store = JsonStore(tmp_path / "containers.json")
    record = ContainerRecord(
        name="dev1",
        profile_string="/dev/python///",
        resolved_profiles=["service/base", "tool/python"],
        ephemeral=False,
        gpu_enabled=False,
        created_at=datetime.now(UTC),
        status="running",
    )

    store.upsert(record)
    loaded = store.get("dev1")
    assert loaded is not None
    assert loaded.name == "dev1"

    store.delete("dev1")
    assert store.get("dev1") is None
