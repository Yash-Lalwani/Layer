def test_health_checks_database_and_engine(client):
    http, engine = client
    assert http.get("/health").json() == {"status": "ok"}

    engine.healthy = False
    response = http.get("/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "server_error"


def test_cors_allows_frontend(client):
    http, _ = client
    response = http.options(
        "/projects",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

