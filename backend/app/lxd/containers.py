import asyncio
from collections.abc import Callable
from functools import partial
from typing import Any

from app.lxd.client import get_pylxd_client


class LXDContainerService:
    def __init__(self, socket_path: str, client_factory: Callable[[str], Any] | None = None) -> None:
        factory = client_factory or get_pylxd_client
        self._client = factory(socket_path)

    async def _run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def create_container(
        self,
        name: str,
        profiles: list[str],
        user_data: str,
        config: dict[str, str],
    ) -> None:
        definition = {
            "name": name,
            "source": {"type": "image", "alias": "ubuntu/24.04"},
            "profiles": [],
            "config": {**config, "user.user-data": user_data},
        }
        container = await self._run(self._client.containers.create, definition, wait=True)
        await self._run(container.start, wait=True)

    async def start_container(self, name: str) -> None:
        container = await self._run(self._client.containers.get, name)
        await self._run(container.start, wait=True)

    async def stop_container(self, name: str) -> None:
        container = await self._run(self._client.containers.get, name)
        await self._run(container.stop, wait=True)

    async def delete_container(self, name: str) -> None:
        container = await self._run(self._client.containers.get, name)
        await self._run(container.delete, wait=True)

    async def get_status(self, name: str) -> str:
        container = await self._run(self._client.containers.get, name)
        return str(container.status).lower()

    async def create_snapshot(self, name: str, snapshot_name: str) -> None:
        container = await self._run(self._client.containers.get, name)
        await self._run(container.snapshots.create, snapshot_name, stateful=False, wait=True)

    async def list_snapshots(self, name: str) -> list[str]:
        container = await self._run(self._client.containers.get, name)
        snapshots = await self._run(lambda: list(container.snapshots.all()))
        return [snap.name for snap in snapshots]

    async def restore_snapshot(self, name: str, snapshot_name: str) -> None:
        container = await self._run(self._client.containers.get, name)
        snapshot = await self._run(container.snapshots.get, snapshot_name)
        await self._run(snapshot.restore, wait=True)

    async def export_workspace(self, name: str) -> bytes:
        container = await self._run(self._client.containers.get, name)
        archive_path = "/tmp/yetaos-export.tar.gz"
        await self._run(container.execute, ["sh", "-lc", f"tar czf {archive_path} -C /workspace ."])
        payload = await self._run(container.files.get, archive_path)
        await self._run(container.execute, ["rm", "-f", archive_path])
        if isinstance(payload, bytes):
            return payload
        return str(payload).encode("utf-8")
