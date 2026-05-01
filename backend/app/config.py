from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    lxd_socket: str = Field(default="/var/snap/lxd/common/lxd/unix.socket", alias="YETAOS_LXD_SOCKET")
    store_path: Path = Field(default=Path("/tmp/yetaos/containers.json"), alias="YETAOS_STORE_PATH")
    profiles_dir: Path = Field(default=Path("../lxc/profiles"), alias="YETAOS_PROFILES_DIR")
    cloud_init_dir: Path = Field(default=Path("../lxc/cloud-init"), alias="YETAOS_CLOUD_INIT_DIR")
    workspaces_dir: Path = Field(default=Path("/tmp/yetaos/workspaces"), alias="YETAOS_WORKSPACES_DIR")
    secrets_dir: Path = Field(default=Path("/tmp/yetaos/secrets"), alias="YETAOS_SECRETS_DIR")
    models_dir: Path = Field(default=Path("/tmp/yetaos/models"), alias="YETAOS_MODELS_DIR")
    api_key: str | None = Field(default=None, alias="YETAOS_API_KEY")
    host: str = Field(default="0.0.0.0", alias="YETAOS_HOST")
    port: int = Field(default=8000, alias="YETAOS_PORT")
    log_level: str = Field(default="info", alias="YETAOS_LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
