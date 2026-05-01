from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CreateContainerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=63)
    profile_string: str
    ephemeral: bool = False
    cpu_limit: int = Field(default=2, ge=1, le=64)
    memory_limit_gb: int = Field(default=4, ge=1, le=256)
    enable_gpu: bool = False
    secrets: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[a-z][a-z0-9-]*", value):
            raise ValueError("name must match [a-z][a-z0-9-]*")
        return value


class UpdateSecretsRequest(BaseModel):
    secrets: dict[str, str] = Field(default_factory=dict)


class CreateSnapshotRequest(BaseModel):
    snapshot_name: str = Field(min_length=1, max_length=64)


class ContainerResponse(BaseModel):
    name: str
    profile_string: str
    resolved_profiles: list[str]
    ephemeral: bool
    status: str
    created_at: datetime
    last_used: datetime | None
    shell_url: str | None = None
    code_url: str | None = None


class ResolveProfilesResponse(BaseModel):
    requested: str
    resolved_profiles: list[str]
