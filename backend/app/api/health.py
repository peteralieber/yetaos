from fastapi import APIRouter

from app.config import get_settings
from app.lxd.client import check_lxd_socket
from app.store.json_store import JsonStore

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    lxd_status = "ok"
    db_status = "ok"

    try:
        check_lxd_socket(settings.lxd_socket)
    except Exception as exc:  # noqa: BLE001
        lxd_status = f"error: {exc}"

    try:
        JsonStore(settings.store_path).load()
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    return {"status": "ok", "lxd": lxd_status, "db": db_status, "version": "0.1.0"}
