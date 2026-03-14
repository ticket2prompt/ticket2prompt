"""Tests for health check and app startup."""


def test_health_endpoint_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0"


def test_openapi_schema_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert schema["info"]["title"] == "Ticket to Prompt"


def test_app_includes_all_routers(client):
    response = client.get("/openapi.json")
    schema = response.json()
    paths = list(schema["paths"].keys())
    assert "/projects/{project_id}/ticket" in paths
    assert "/projects/{project_id}/index" in paths
    assert "/projects/{project_id}/prompt/{ticket_id}" in paths
    assert "/health" in paths


def test_cors_headers_present(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers


def test_unknown_route_returns_404(client):
    response = client.get("/nonexistent")
    assert response.status_code == 404
