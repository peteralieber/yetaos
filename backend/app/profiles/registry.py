from pathlib import Path

import yaml
from pydantic import BaseModel


class ProfileDefinition(BaseModel):
    name: str
    description: str
    category: str
    depends: list[str] = []
    lxd: dict[str, object] = {}
    cloud_init: str | None = None


class ProfileRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load_all(self) -> dict[str, ProfileDefinition]:
        profiles: dict[str, ProfileDefinition] = {}
        for path in sorted(self.root.rglob("*.yaml")):
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
            profile = ProfileDefinition(**parsed)
            profiles[profile.name] = profile
        return profiles
