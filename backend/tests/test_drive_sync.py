from urllib.parse import urlparse

from conftest import headers, register


def test_selected_drive_file_ingests_then_skips_unchanged_and_deletes(client, monkeypatch):
    http, engine = client
    auth = register(http)
    token = auth["token"]
    project = http.post("/projects", json={"name": "Phoenix"}, headers=headers(token)).json()["id"]
    http.post(f"/projects/{project}/sources/drive/connect", headers=headers(token))
    callback = urlparse(http.app.state.fake_composio.callback_url)
    http.get(callback.path + "?" + callback.query, follow_redirects=False)
    config = {"file_ids": ["file-1"], "folder_ids": []}
    assert http.put(f"/projects/{project}/sources/drive/config", json=config, headers=headers(token)).status_code == 200

    class Response:
        content = b"Sample document"
        def raise_for_status(self): pass

    class Http:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url):
            assert url == "https://download.example/notes.txt"
            return Response()

    monkeypatch.setattr("layer_api.integrations.drive_sync.httpx.AsyncClient", Http)
    assert http.post(f"/projects/{project}/sources/drive/sync", headers=headers(token)).json() == {"started": True}
    assert "drive:file-1" in engine.documents
    assert http.get(f"/projects/{project}/sources/drive/files", headers=headers(token)).json()[0]["status"] == "ingested"
    assert http.post(f"/projects/{project}/sources/drive/sync", headers=headers(token)).status_code == 200
    assert http.get(f"/projects/{project}/sources/drive/files", headers=headers(token)).json()[0]["status"] == "unchanged"
    assert http.put(f"/projects/{project}/sources/drive/config", json={"file_ids": [], "folder_ids": []}, headers=headers(token)).status_code == 200
    assert "drive:file-1" not in engine.documents
    assert http.put(f"/projects/{project}/sources/drive/config", json=config, headers=headers(token)).status_code == 200
    assert http.post(f"/projects/{project}/sources/drive/sync", headers=headers(token)).status_code == 200
    assert "drive:file-1" in engine.documents
    assert http.delete(f"/projects/{project}/sources/drive/files/file-1", headers=headers(token)).status_code == 200
    assert "drive:file-1" not in engine.documents
