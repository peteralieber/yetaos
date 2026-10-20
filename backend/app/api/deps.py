from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.lxd.containers import LXDContainerService
from app.lxd.mock import get_mock_lxd_service
from app.profiles.registry import ProfileRegistry
from app.store.json_store import JsonStore


def get_store(settings: Settings = Depends(get_settings)) -> JsonStore:
    return JsonStore(settings.store_path)


def get_registry(settings: Settings = Depends(get_settings)) -> ProfileRegistry:
    return ProfileRegistry(settings.profiles_dir)


def get_lxd_service(settings: Settings = Depends(get_settings)) -> LXDContainerService:
    if settings.mock_lxd:
        return get_mock_lxd_service()
    return LXDContainerService(socket_path=settings.lxd_socket)


def verify_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_key:
        client_host = request.client.host if request.client else ""
        if client_host in {"127.0.0.1", "::1", "testclient"}:
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key is required")

    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
