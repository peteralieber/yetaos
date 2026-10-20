from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.containers import router as containers_router
from app.api.health import router as health_router
from app.api.profiles import router as profiles_router
from app.api.ui import router as ui_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.workspaces_dir.mkdir(parents=True, exist_ok=True)
    settings.secrets_dir.mkdir(parents=True, exist_ok=True)
    settings.store_path.parent.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="YETAOS", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(profiles_router)
app.include_router(containers_router)
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
