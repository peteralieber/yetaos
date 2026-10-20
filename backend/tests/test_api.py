def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_create_list_start_stop_delete_container(client) -> None:
    create_response = client.post(
        "/api/v1/containers",
        json={
            "name": "devbox",
            "profile_string": "/dev/python///",
            "ephemeral": False,
            "cpu_limit": 2,
            "memory_limit_gb": 4,
            "enable_gpu": False,
            "secrets": {"TOKEN": "x"},
        },
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/containers")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    start_response = client.post("/api/v1/containers/devbox/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    stop_response = client.post("/api/v1/containers/devbox/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    delete_response = client.delete("/api/v1/containers/devbox")
    assert delete_response.status_code == 204


def test_resolve_profiles_route(client) -> None:
    response = client.get("/api/v1/profiles/resolve", params={"profile_string": "/dev/python///"})
    assert response.status_code == 200
    resolved = response.json()["resolved_profiles"]
    assert "service/base" in resolved
    assert "tool/python" in resolved


def test_export_workspace(client) -> None:
    create_response = client.post(
        "/api/v1/containers",
        json={
            "name": "devbox",
            "profile_string": "/dev/python///",
            "ephemeral": False,
            "cpu_limit": 2,
            "memory_limit_gb": 4,
            "enable_gpu": False,
            "secrets": {},
        },
    )
    assert create_response.status_code == 201

    export_response = client.get("/api/v1/containers/devbox/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/gzip"
    assert "devbox-workspace.tar.gz" in export_response.headers["content-disposition"]
    assert export_response.content == b"fake-archive"


def test_export_workspace_not_found(client) -> None:
    response = client.get("/api/v1/containers/missing/export")
    assert response.status_code == 404
