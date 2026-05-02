def test_dashboard_page_renders(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Containers" in response.text


def test_create_page_renders(client) -> None:
    response = client.get("/create")
    assert response.status_code == 200
    assert "Create Environment" in response.text


def test_container_detail_shows_shell_code_and_export(client) -> None:
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
    assert "Open Shell" in detail.text
    assert "Open VS Code" in detail.text
    assert "/api/v1/containers/devbox/export" in detail.text
