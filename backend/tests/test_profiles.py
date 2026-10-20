"""Tests for the new environment profiles added in feat/remaining-profiles."""

from pathlib import Path

import pytest

from app.profiles.registry import ProfileRegistry
from app.profiles.resolver import ProfileResolver

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "lxc" / "profiles"
CLOUD_INIT_DIR = REPO_ROOT / "lxc" / "cloud-init"


@pytest.fixture(scope="module")
def registry() -> ProfileRegistry:
    return ProfileRegistry(PROFILES_DIR)


@pytest.fixture(scope="module")
def all_profiles(registry: ProfileRegistry) -> dict:
    return registry.load_all()


@pytest.fixture(scope="module")
def resolver(all_profiles: dict) -> ProfileResolver:
    return ProfileResolver(all_profiles)


# ---------------------------------------------------------------------------
# tool/clang:riscv
# ---------------------------------------------------------------------------


def test_clang_riscv_profile_loads(all_profiles: dict) -> None:
    assert "tool/clang:riscv" in all_profiles


def test_clang_riscv_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["tool/clang:riscv"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_clang_riscv_depends_on_base(all_profiles: dict) -> None:
    assert "service/base" in all_profiles["tool/clang:riscv"].depends


def test_clang_riscv_resolves(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["tool/clang:riscv"])
    assert resolved.index("service/base") < resolved.index("tool/clang:riscv")


# ---------------------------------------------------------------------------
# tool/node
# ---------------------------------------------------------------------------


def test_node_profile_loads(all_profiles: dict) -> None:
    assert "tool/node" in all_profiles


def test_node_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["tool/node"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_node_depends_on_base(all_profiles: dict) -> None:
    assert "service/base" in all_profiles["tool/node"].depends


def test_node_resolves(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["tool/node"])
    assert "service/base" in resolved
    assert "tool/node" in resolved


# ---------------------------------------------------------------------------
# tool/electron
# ---------------------------------------------------------------------------


def test_electron_profile_loads(all_profiles: dict) -> None:
    assert "tool/electron" in all_profiles


def test_electron_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["tool/electron"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_electron_depends_on_node(all_profiles: dict) -> None:
    assert "tool/node" in all_profiles["tool/electron"].depends


def test_electron_resolves_with_full_chain(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["tool/electron"])
    assert "service/base" in resolved
    assert "tool/node" in resolved
    assert "tool/electron" in resolved
    assert resolved.index("tool/node") < resolved.index("tool/electron")


# ---------------------------------------------------------------------------
# use-case/blender
# ---------------------------------------------------------------------------


def test_blender_profile_loads(all_profiles: dict) -> None:
    assert "use-case/blender" in all_profiles


def test_blender_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["use-case/blender"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_blender_depends_on_base(all_profiles: dict) -> None:
    assert "service/base" in all_profiles["use-case/blender"].depends


def test_blender_resolves(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["use-case/blender"])
    assert "service/base" in resolved
    assert "use-case/blender" in resolved


# ---------------------------------------------------------------------------
# use-case/comfyui
# ---------------------------------------------------------------------------


def test_comfyui_profile_loads(all_profiles: dict) -> None:
    assert "use-case/comfyui" in all_profiles


def test_comfyui_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["use-case/comfyui"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_comfyui_depends_on_python_rocm(all_profiles: dict) -> None:
    assert "tool/python:rocm" in all_profiles["use-case/comfyui"].depends


def test_comfyui_resolves_with_full_chain(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["use-case/comfyui"])
    assert "service/base" in resolved
    assert "tool/python" in resolved
    assert "tool/python:rocm" in resolved
    assert "use-case/comfyui" in resolved
    assert resolved.index("tool/python") < resolved.index("tool/python:rocm")
    assert resolved.index("tool/python:rocm") < resolved.index("use-case/comfyui")


# ---------------------------------------------------------------------------
# use-case/agents
# ---------------------------------------------------------------------------


def test_agents_profile_loads(all_profiles: dict) -> None:
    assert "use-case/agents" in all_profiles


def test_agents_has_cloud_init_script(all_profiles: dict) -> None:
    profile = all_profiles["use-case/agents"]
    assert profile.cloud_init is not None
    script = REPO_ROOT / profile.cloud_init
    assert script.exists(), f"cloud-init script not found: {script}"


def test_agents_depends_on_node(all_profiles: dict) -> None:
    assert "tool/node" in all_profiles["use-case/agents"].depends


def test_agents_resolves_with_full_chain(resolver: ProfileResolver) -> None:
    resolved = resolver.resolve(["use-case/agents"])
    assert "service/base" in resolved
    assert "tool/node" in resolved
    assert "use-case/agents" in resolved
    assert resolved.index("tool/node") < resolved.index("use-case/agents")


# ---------------------------------------------------------------------------
# cloud-init script content smoke tests
# ---------------------------------------------------------------------------


def _script(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_clang_riscv_script_mentions_riscv(all_profiles: dict) -> None:
    text = _script(all_profiles["tool/clang:riscv"].cloud_init)
    assert "riscv64" in text


def test_node_script_mentions_nodesource(all_profiles: dict) -> None:
    text = _script(all_profiles["tool/node"].cloud_init)
    assert "nodesource" in text


def test_comfyui_script_clones_repo(all_profiles: dict) -> None:
    text = _script(all_profiles["use-case/comfyui"].cloud_init)
    assert "ComfyUI" in text


def test_agents_script_installs_claude(all_profiles: dict) -> None:
    text = _script(all_profiles["use-case/agents"].cloud_init)
    assert "claude" in text.lower()
