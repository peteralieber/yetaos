from datetime import datetime

from pydantic import BaseModel


class ContainerRecord(BaseModel):
    name: str
    profile_string: str
    resolved_profiles: list[str]
    ephemeral: bool
    gpu_enabled: bool
    created_at: datetime
    last_used: datetime | None = None
    status: str
    workspace_path: str | None = None
