from app.profiles.registry import ProfileDefinition


class ProfileResolver:
    def __init__(self, profiles: dict[str, ProfileDefinition]) -> None:
        self.profiles = profiles

    def parse_profile_string(self, profile_string: str) -> list[str]:
        if not profile_string.startswith("/") or not profile_string.endswith("/"):
            raise ValueError("profile string must start and end with '/'")

        parts = profile_string[1:-1].split("/")
        if len(parts) != 4:
            raise ValueError("profile string must have 4 segments")

        categories = ["use-case", "tool", "agent", "service"]
        requested: list[str] = []
        for category, segment in zip(categories, parts, strict=True):
            if not segment:
                continue
            for token in segment.split("+"):
                requested.append(f"{category}/{token}")
        return requested

    def resolve_from_string(self, profile_string: str) -> list[str]:
        requested = self.parse_profile_string(profile_string)
        return self.resolve(requested)

    def resolve(self, requested: list[str]) -> list[str]:
        ordered: list[str] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(name: str) -> None:
            if name in permanent:
                return
            if name in temporary:
                raise ValueError(f"dependency cycle detected at {name}")
            profile = self.profiles.get(name)
            if profile is None:
                raise ValueError(f"profile not found: {name}")
            temporary.add(name)
            for dependency in profile.depends:
                visit(dependency)
            temporary.remove(name)
            permanent.add(name)
            if name not in ordered:
                ordered.append(name)

        for item in requested:
            visit(item)
        return ordered
