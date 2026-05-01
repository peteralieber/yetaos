from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.profiles.registry import ProfileRegistry


def _fragment_to_commands(path: Path) -> list[str]:
    commands: list[str] = []
    if not path.exists():
        return commands
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        commands.append(line)
    return commands


def build_user_data(profile_string: str, resolved_profiles: list[str], registry: ProfileRegistry) -> str:
    profile_map = registry.load_all()
    merged_commands: list[str] = []
    seen: set[str] = set()

    for profile_name in resolved_profiles:
        profile = profile_map.get(profile_name)
        if not profile or not profile.cloud_init:
            continue
        if profile_name in seen:
            continue
        seen.add(profile_name)
        fragment_path = registry.root.parent.parent / profile.cloud_init
        merged_commands.extend(_fragment_to_commands(fragment_path))

    payload = {
        "package_update": True,
        "package_upgrade": False,
        "write_files": [
            {
                "path": "/etc/dev-orchestrator/metadata.json",
                "content": yaml.safe_dump(
                    {
                        "profile_string": profile_string,
                        "resolved_profiles": resolved_profiles,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    sort_keys=False,
                ),
            }
        ],
        "runcmd": merged_commands,
    }
    rendered = yaml.safe_dump(payload, sort_keys=False)
    return "#cloud-config\n" + rendered
