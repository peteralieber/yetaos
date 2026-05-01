import pytest

from app.profiles.registry import ProfileDefinition
from app.profiles.resolver import ProfileResolver


def test_resolve_with_dependencies() -> None:
    profiles = {
        "service/base": ProfileDefinition(name="service/base", description="", category="service"),
        "use-case/dev": ProfileDefinition(
            name="use-case/dev", description="", category="use-case", depends=["service/base"]
        ),
        "tool/python": ProfileDefinition(
            name="tool/python", description="", category="tool", depends=["service/base"]
        ),
    }
    resolver = ProfileResolver(profiles)
    resolved = resolver.resolve_from_string("/dev/python///")
    assert resolved == ["service/base", "use-case/dev", "tool/python"]


def test_cycle_detection() -> None:
    profiles = {
        "a/x": ProfileDefinition(name="a/x", description="", category="a", depends=["a/y"]),
        "a/y": ProfileDefinition(name="a/y", description="", category="a", depends=["a/x"]),
    }
    resolver = ProfileResolver(profiles)
    with pytest.raises(ValueError, match="cycle"):
        resolver.resolve(["a/x"])
