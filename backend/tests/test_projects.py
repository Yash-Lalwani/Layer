from conftest import headers, register


def test_project_lifecycle_keeps_collection_id_on_rename(client):
    http, engine = client
    token = register(http)["token"]
    auth = headers(token)

    created = http.post("/projects", json={"name": "Phoenix", "description": "Launch"}, headers=auth)
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["name"] == "Phoenix"
    assert project["connected_sources"] == []
    collection_id = next(iter(engine.collections))
    assert engine.collections[collection_id] == "Phoenix"
    assert http.get("/projects", headers=auth).json()[0]["id"] == project["id"]
    assert http.get(f"/projects/{project['id']}", headers=auth).json()["id"] == project["id"]

    renamed = http.patch(f"/projects/{project['id']}", json={"name": "Phoenix 2"}, headers=auth)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Phoenix 2"
    assert engine.collections == {collection_id: "Phoenix"}

    deleted = http.delete(f"/projects/{project['id']}", headers=auth)
    assert deleted.json() == {"ok": True}
    assert engine.collections == {}
    assert http.get("/projects", headers=auth).json() == []


def test_projects_are_owned_by_the_user(client):
    http, _ = client
    first = headers(register(http, "first@example.com")["token"])
    second = headers(register(http, "second@example.com")["token"])
    project = http.post("/projects", json={"name": "Private"}, headers=first).json()

    assert http.get("/projects", headers=second).json() == []
    for response in (
        http.get(f"/projects/{project['id']}", headers=second),
        http.patch(f"/projects/{project['id']}", json={"name": "Other"}, headers=second),
        http.delete(f"/projects/{project['id']}", headers=second),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_engine_failure_does_not_create_or_delete_project(client):
    http, engine = client
    auth = headers(register(http)["token"])
    engine.fail_create = True
    failed = http.post("/projects", json={"name": "Phoenix"}, headers=auth)
    assert failed.status_code == 503
    assert http.get("/projects", headers=auth).json() == []

    engine.fail_create = False
    project = http.post("/projects", json={"name": "Phoenix"}, headers=auth).json()
    engine.fail_delete = True
    failed = http.delete(f"/projects/{project['id']}", headers=auth)
    assert failed.status_code == 503
    assert http.get("/projects", headers=auth).json()[0]["id"] == project["id"]

