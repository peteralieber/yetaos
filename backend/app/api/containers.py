from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_lxd_service, get_registry, get_store, verify_api_key
from app.config import get_settings
from app.lxd.container_init import build_user_data
from app.lxd.containers import LXDContainerService
from app.profiles.registry import ProfileRegistry
from app.profiles.resolver import ProfileResolver
from app.schemas import (
    ContainerResponse,
    CreateContainerRequest,
    CreateSnapshotRequest,
    UpdateSecretsRequest,
)
from app.store.models import ContainerRecord
from app.store.json_store import JsonStore

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


def _to_response(record: ContainerRecord) -> ContainerResponse:
    return ContainerResponse(
        name=record.name,
        profile_string=record.profile_string,
        resolved_profiles=record.resolved_profiles,
        ephemeral=record.ephemeral,
        status=record.status,
        created_at=record.created_at,
        last_used=record.last_used,
        shell_url=f"/containers/{record.name}/shell",
        code_url=f"/containers/{record.name}/code",
    )


def _write_secrets(name: str, secrets: dict[str, str], secrets_dir: Path) -> None:
    secrets_dir.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(f"{k}={v}" for k, v in secrets.items())
    path = secrets_dir / f"{name}.env"
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
    path.chmod(0o600)


@router.get("", response_model=list[ContainerResponse], dependencies=[Depends(verify_api_key)])
async def list_containers(
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> list[ContainerResponse]:
    records = store.load()
    results: list[ContainerResponse] = []
    for record in records.values():
        try:
            record.status = await lxd.get_status(record.name)
        except Exception:  # noqa: BLE001
            record.status = "error"
        results.append(_to_response(record))
    return results


@router.post(
    "",
    response_model=ContainerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def create_container(
    body: CreateContainerRequest,
    store: JsonStore = Depends(get_store),
    registry: ProfileRegistry = Depends(get_registry),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> ContainerResponse:
    if store.get(body.name):
        raise HTTPException(status_code=409, detail="container already exists")

    resolver = ProfileResolver(registry.load_all())
    try:
        resolved_profiles = resolver.resolve_from_string(body.profile_string)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user_data = build_user_data(body.profile_string, resolved_profiles, registry)
    settings = get_settings()
    workspace_path = settings.workspaces_dir / body.name
    workspace_path.mkdir(parents=True, exist_ok=True)
    _write_secrets(body.name, body.secrets, settings.secrets_dir)

    lxd_config = {
        "limits.cpu": str(body.cpu_limit),
        "limits.memory": f"{body.memory_limit_gb}GB",
    }

    await lxd.create_container(body.name, resolved_profiles, user_data, lxd_config)

    record = ContainerRecord(
        name=body.name,
        profile_string=body.profile_string,
        resolved_profiles=resolved_profiles,
        ephemeral=body.ephemeral,
        gpu_enabled=body.enable_gpu,
        created_at=datetime.now(UTC),
        last_used=None,
        status="starting",
        workspace_path=str(workspace_path),
    )
    store.upsert(record)
    return _to_response(record)


@router.get("/{name}", response_model=ContainerResponse, dependencies=[Depends(verify_api_key)])
async def get_container(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> ContainerResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")
    try:
        record.status = await lxd.get_status(name)
        store.upsert(record)
    except Exception:  # noqa: BLE001
        record.status = "error"
    return _to_response(record)


@router.post("/{name}/start", response_model=ContainerResponse, dependencies=[Depends(verify_api_key)])
async def start_container(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> ContainerResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")
    await lxd.start_container(name)
    record.status = "running"
    record.last_used = datetime.now(UTC)
    store.upsert(record)
    return _to_response(record)


@router.post("/{name}/stop", response_model=ContainerResponse, dependencies=[Depends(verify_api_key)])
async def stop_container(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> ContainerResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")
    await lxd.stop_container(name)
    record.status = "stopped"
    store.upsert(record)
    if record.ephemeral:
        await lxd.delete_container(name)
        store.delete(name)
    return _to_response(record)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_api_key)])
async def delete_container(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> Response:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")
    await lxd.delete_container(name)
    if record.workspace_path:
        Path(record.workspace_path).mkdir(parents=True, exist_ok=True)
    store.delete(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{name}/secrets", response_model=ContainerResponse, dependencies=[Depends(verify_api_key)])
async def update_secrets(
    name: str,
    body: UpdateSecretsRequest,
    store: JsonStore = Depends(get_store),
) -> ContainerResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")
    settings = get_settings()
    _write_secrets(name, body.secrets, settings.secrets_dir)
    return _to_response(record)


@router.post("/{name}/snapshot", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_api_key)])
async def create_snapshot(
    name: str,
    body: CreateSnapshotRequest,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> dict[str, str]:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")
    await lxd.create_snapshot(name, body.snapshot_name)
    return {"status": "accepted", "snapshot": body.snapshot_name}


@router.get("/{name}/snapshots", dependencies=[Depends(verify_api_key)])
async def list_snapshots(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> dict[str, list[str]]:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")
    snapshots = await lxd.list_snapshots(name)
    return {"snapshots": snapshots}


@router.post(
    "/{name}/snapshots/{snapshot}/restore",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
)
async def restore_snapshot(
    name: str,
    snapshot: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> dict[str, str]:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")
    await lxd.restore_snapshot(name, snapshot)
    return {"status": "accepted", "snapshot": snapshot}
