import json
import threading
from pathlib import Path

from app.store.models import ContainerRecord


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, ContainerRecord]:
        with self._lock:
            if not self.path.exists():
                return {}
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return {name: ContainerRecord(**value) for name, value in payload.items()}

    def save(self, records: dict[str, ContainerRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {name: record.model_dump(mode="json") for name, record in records.items()}
        with self._lock:
            tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self.path)

    def get(self, name: str) -> ContainerRecord | None:
        return self.load().get(name)

    def upsert(self, record: ContainerRecord) -> None:
        records = self.load()
        records[record.name] = record
        self.save(records)

    def delete(self, name: str) -> None:
        records = self.load()
        records.pop(name, None)
        self.save(records)
