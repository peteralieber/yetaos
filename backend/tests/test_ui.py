def test_dashboard_page_renders(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Containers" in response.text


def test_create_page_renders(client) -> None:
    response = client.get("/create")
    assert response.status_code == 200
    assert "Create Environment" in response.text


def test_htmx_create_redirects_to_detail(client) -> None:
    response = client.post(
        "/fragments/containers/create",
        data={
            "name": "devbox",
            "profile_string": "/dev/python///",
            "cpu_limit": "2",
            "memory_limit_gb": "4",
            "secrets_text": "TOKEN=x",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 201
    assert response.headers["HX-Redirect"] == "/containers/devbox"


def test_detail_page_and_actions(client) -> None:
    create_response = client.post(
        "/api/v1/containers",
        json={
            "name": "devbox",
            "profile_string": "/dev/python///",
            "cpu_limit": 2,
            "memory_limit_gb": 4,
            "secrets": {},
        },
    )
    assert create_response.status_code == 201

    detail = client.get("/containers/devbox")
    assert detail.status_code == 200
    assert "devbox" in detail.text

    start = client.post("/fragments/containers/devbox/start")
    assert start.status_code == 200
    assert "running" in start.text

    stop = client.post("/fragments/containers/devbox/stop")
    assert stop.status_code == 200
    assert "stopped" in stop.text


def test_snapshot_fragment_flow(client) -> None:
    create_response = client.post(
        "/api/v1/containers",
        json={
            "name": "snapbox",
            "profile_string": "/dev/python///",
            "cpu_limit": 2,
            "memory_limit_gb": 4,
            "secrets": {},
        },
    )
    assert create_response.status_code == 201

    create_snapshot = client.post(
        "/fragments/containers/snapbox/snapshots",
        data={"snapshot_name": "baseline"},
    )
    assert create_snapshot.status_code == 200
    assert "baseline" in create_snapshot.text

    restore = client.post(
        "/fragments/containers/snapbox/snapshots/baseline/restore",
        headers={"HX-Request": "true"},
    )
    assert restore.status_code == 200
    assert restore.headers["HX-Trigger"] == "snapshot-restored"
