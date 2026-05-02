from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.api.deps import get_lxd_service, get_registry, get_store
from app.api.containers import _write_secrets
from app.config import get_settings
from app.lxd.container_init import build_user_data
from app.lxd.containers import LXDContainerService
from app.profiles.registry import ProfileRegistry
from app.profiles.resolver import ProfileResolver
from app.schemas import CreateContainerRequest
from app.store.json_store import JsonStore
from app.store.models import ContainerRecord

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _form_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {"1", "true", "on", "yes"}


def _parse_secrets(raw: str) -> dict[str, str]:
    secrets: dict[str, str] = {}
    for line in raw.splitlines():
        entry = line.strip()
        if not entry or "=" not in entry:
            continue
        key, value = entry.split("=", maxsplit=1)
        key = key.strip()
        if key:
            secrets[key] = value.strip()
    return secrets


def _profile_options(registry: ProfileRegistry, category: str) -> list[dict[str, str]]:
    profiles = registry.load_all().values()
    scoped = [profile for profile in profiles if profile.category == category]
    return [
        {
            "value": profile.name,
            "slug": profile.name.split("/", maxsplit=1)[1],
            "label": profile.name,
        }
        for profile in sorted(scoped, key=lambda item: item.name)
    ]


async def _with_status(record: ContainerRecord, lxd: LXDContainerService, store: JsonStore) -> ContainerRecord:
    try:
        record.status = await lxd.get_status(record.name)
        store.upsert(record)
    except Exception:  # noqa: BLE001
        record.status = "error"
    return record


async def _all_records(store: JsonStore, lxd: LXDContainerService) -> list[ContainerRecord]:
    records = list(store.load().values())
    records.sort(key=lambda item: item.name)
    results: list[ContainerRecord] = []
    for record in records:
        results.append(await _with_status(record, lxd, store))
    return results


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    records = await _all_records(store, lxd)
    return templates.TemplateResponse(request, "index.html", {"records": records})


@router.get("/create", response_class=HTMLResponse)
async def create_page(
    request: Request,
    registry: ProfileRegistry = Depends(get_registry),
) -> HTMLResponse:
    use_cases = _profile_options(registry, "use-case")
    tools = _profile_options(registry, "tool")
    agents = _profile_options(registry, "agent")
    services = _profile_options(registry, "service")

    return templates.TemplateResponse(request, "create.html", {
        "use_cases": use_cases,
        "tools": tools,
        "agents": agents,
        "services": services,
    })


@router.get("/containers/{name}", response_class=HTMLResponse)
async def container_detail_page(
    name: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")

    snapshots = await lxd.list_snapshots(name)
    record = await _with_status(record, lxd, store)

    return templates.TemplateResponse(request, "container.html", {"container": record, "snapshots": snapshots})


@router.get("/fragments/containers", response_class=HTMLResponse)
async def containers_fragment(
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    records = await _all_records(store, lxd)
    return templates.TemplateResponse(request, "fragments/container_list.html", {"records": records})


@router.post("/fragments/containers/create")
async def create_container_from_form(
    request: Request,
    name: str = Form(...),
    profile_string: str = Form(...),
    ephemeral: str | None = Form(default=None),
    cpu_limit: int = Form(default=2),
    memory_limit_gb: int = Form(default=4),
    enable_gpu: str | None = Form(default=None),
    secrets_text: str = Form(default=""),
    store: JsonStore = Depends(get_store),
    registry: ProfileRegistry = Depends(get_registry),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> Response:
    if store.get(name):
        return templates.TemplateResponse(
            request,
            "fragments/create_result.html",
            {"success": False, "message": "Container already exists."},
            status_code=status.HTTP_409_CONFLICT,
        )

    secrets = _parse_secrets(secrets_text)
    try:
        body = CreateContainerRequest(
            name=name,
            profile_string=profile_string,
            ephemeral=_form_bool(ephemeral),
            cpu_limit=cpu_limit,
            memory_limit_gb=memory_limit_gb,
            enable_gpu=_form_bool(enable_gpu),
            secrets=secrets,
        )
    except ValidationError as exc:
        message = "; ".join(err["msg"] for err in exc.errors())
        return templates.TemplateResponse(
            request,
            "fragments/create_result.html",
            {"success": False, "message": message},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    resolver = ProfileResolver(registry.load_all())
    try:
        resolved_profiles = resolver.resolve_from_string(body.profile_string)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "fragments/create_result.html",
            {"success": False, "message": str(exc)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

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

    if request.headers.get("HX-Request") == "true":
        return HTMLResponse(
            "",
            status_code=status.HTTP_201_CREATED,
            headers={"HX-Redirect": f"/containers/{body.name}"},
        )
    return RedirectResponse(url=f"/containers/{body.name}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/fragments/containers/{name}/start", response_class=HTMLResponse)
async def start_container_from_ui(
    name: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")

    await lxd.start_container(name)
    record.status = "running"
    record.last_used = datetime.now(UTC)
    store.upsert(record)

    return templates.TemplateResponse(request, "fragments/container_row.html", {"container": record})


@router.post("/fragments/containers/{name}/stop", response_class=HTMLResponse)
async def stop_container_from_ui(
    name: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")

    await lxd.stop_container(name)
    record.status = "stopped"
    store.upsert(record)

    if record.ephemeral:
        await lxd.delete_container(name)
        store.delete(name)
        return HTMLResponse("")

    return templates.TemplateResponse(request, "fragments/container_row.html", {"container": record})


@router.delete("/fragments/containers/{name}")
async def delete_container_from_ui(
    name: str,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> Response:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")

    await lxd.delete_container(name)
    store.delete(name)
    return HTMLResponse("")


@router.get("/fragments/containers/{name}/status", response_class=HTMLResponse)
async def container_status_fragment(
    name: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    record = store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="container not found")

    record = await _with_status(record, lxd, store)
    return templates.TemplateResponse(request, "fragments/status_badge.html", {"status": record.status})


@router.get("/fragments/containers/{name}/snapshots", response_class=HTMLResponse)
async def snapshots_fragment(
    name: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")

    snapshots = await lxd.list_snapshots(name)
    return templates.TemplateResponse(request, "fragments/snapshot_list.html", {"name": name, "snapshots": snapshots})


@router.post("/fragments/containers/{name}/snapshots", response_class=HTMLResponse)
async def create_snapshot_from_ui(
    name: str,
    request: Request,
    snapshot_name: str = Form(...),
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> HTMLResponse:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")

    await lxd.create_snapshot(name, snapshot_name)
    snapshots = await lxd.list_snapshots(name)
    return templates.TemplateResponse(request, "fragments/snapshot_list.html", {"name": name, "snapshots": snapshots})


@router.post("/fragments/containers/{name}/snapshots/{snapshot}/restore")
async def restore_snapshot_from_ui(
    name: str,
    snapshot: str,
    request: Request,
    store: JsonStore = Depends(get_store),
    lxd: LXDContainerService = Depends(get_lxd_service),
) -> Response:
    if not store.get(name):
        raise HTTPException(status_code=404, detail="container not found")

    await lxd.restore_snapshot(name, snapshot)
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("", headers={"HX-Trigger": "snapshot-restored"})
    return RedirectResponse(url=f"/containers/{name}", status_code=status.HTTP_303_SEE_OTHER)
