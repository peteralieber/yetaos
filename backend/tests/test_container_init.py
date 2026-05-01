from pathlib import Path

from app.lxd.container_init import build_user_data
from app.profiles.registry import ProfileRegistry


def test_cloud_init_merge_orders_fragments(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "lxc" / "profiles"
    (profiles_dir / "service").mkdir(parents=True)
    (profiles_dir / "tool").mkdir(parents=True)

    (profiles_dir / "service" / "base.yaml").write_text(
        """
name: service/base
description: Base
category: service
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
cloud_init: lxc/cloud-init/tool/python.sh
""".strip()
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / "lxc" / "cloud-init" / "service").mkdir(parents=True)
    (tmp_path / "lxc" / "cloud-init" / "tool").mkdir(parents=True)
    (tmp_path / "lxc" / "cloud-init" / "service" / "base.sh").write_text("echo base\n", encoding="utf-8")
    (tmp_path / "lxc" / "cloud-init" / "tool" / "python.sh").write_text("echo python\n", encoding="utf-8")

    registry = ProfileRegistry(profiles_dir)
    user_data = build_user_data("/dev/python///", ["service/base", "tool/python"], registry)
    assert user_data.startswith("#cloud-config")
    assert "echo base" in user_data
    assert "echo python" in user_data
    assert user_data.index("echo base") < user_data.index("echo python")
