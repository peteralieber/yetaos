from pathlib import Path
from typing import Any


def check_lxd_socket(socket_path: str) -> None:
    if not Path(socket_path).exists():
        raise FileNotFoundError(f"LXD socket not found at {socket_path}")


def get_pylxd_client(socket_path: str) -> Any:
    from pylxd import Client

    return Client(endpoint=f"unix://{socket_path}")
