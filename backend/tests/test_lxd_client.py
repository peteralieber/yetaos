from app.lxd.client import get_pylxd_client
from app.lxd.containers import LXDContainerService


def test_get_pylxd_client_passes_raw_socket_path(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeClient:
        def __init__(self, endpoint: str) -> None:
            captured["endpoint"] = endpoint

    monkeypatch.setattr("pylxd.Client", FakeClient)

    get_pylxd_client("/var/snap/lxd/common/lxd/unix.socket")

    assert captured["endpoint"] == "/var/snap/lxd/common/lxd/unix.socket"


def test_lxd_service_is_lazy_until_first_operation() -> None:
    calls: list[str] = []

    def fake_factory(socket_path: str) -> object:
        calls.append(socket_path)
        return object()

    service = LXDContainerService("/tmp/missing.sock", client_factory=fake_factory)

    assert calls == []
    service._get_client()
    assert calls == ["/tmp/missing.sock"]
