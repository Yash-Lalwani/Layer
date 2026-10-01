from urllib.parse import urlparse

from conftest import headers, register


def make_project(client, email="yash@example.com"):
    auth = register(client, email)
    token = auth["token"]
    response = client.post("/projects", json={"name": "Phoenix"}, headers=headers(token))
    assert response.status_code == 201
    return token, response.json()["id"]


def connect(client, project_id, token, source_type):
    response = client.post(f"/projects/{project_id}/sources/{source_type}/connect", headers=headers(token))
    assert response.status_code == 200, response.text
    callback = client.app.state.fake_composio.callback_url
    result = client.get(urlparse(callback).path + "?" + urlparse(callback).query, follow_redirects=False)
    assert result.status_code == 307, result.text
    assert f"connected={source_type}" in result.headers["location"]


def test_sources_are_project_scoped_and_callback_requires_matching_account(client):
    http, _ = client
    token, first = make_project(http)
    second = http.post("/projects", json={"name": "Other"}, headers=headers(token)).json()["id"]
    assert len(http.get(f"/projects/{first}/sources", headers=headers(token)).json()) == 4
    connect(http, first, token, "gmail")
    first_sources = http.get(f"/projects/{first}/sources", headers=headers(token)).json()
    second_sources = http.get(f"/projects/{second}/sources", headers=headers(token)).json()
    assert next(source for source in first_sources if source["type"] == "gmail")["status"] == "connected"
    assert next(source for source in second_sources if source["type"] == "gmail")["status"] == "not_connected"
    outsider = register(http, "other@example.com")["token"]
    assert http.get(f"/projects/{first}/sources", headers=headers(outsider)).status_code == 404
    assert http.put(f"/projects/{first}/sources/gmail/config", json={"labels": ["INBOX"], "senders": [], "keywords": [], "query": ""}, headers=headers(outsider)).status_code == 404


def test_gmail_config_preview_and_disconnect(client):
    http, _ = client
    token, project = make_project(http)
    connect(http, project, token, "gmail")
    config = {"labels": ["INBOX"], "senders": ["team@example.com"], "keywords": ["Phoenix"], "query": ""}
    saved = http.put(f"/projects/{project}/sources/gmail/config", json=config, headers=headers(token))
    assert saved.status_code == 200, saved.text
    assert saved.json()["config"]["query"] == "label:INBOX from:team@example.com Phoenix"
    assert http.get(f"/projects/{project}/sources/gmail/labels", headers=headers(token)).json() == ["INBOX"]
    preview = http.post(f"/projects/{project}/sources/gmail/preview", json=config, headers=headers(token))
    assert preview.status_code == 200, preview.text
    assert preview.json()[0]["snippet"] == "Ready"
    assert http.delete(f"/projects/{project}/sources/gmail", headers=headers(token)).status_code == 200
    assert http.app.state.fake_composio.accounts
    assert http.post(f"/projects/{project}/sources/gmail/preview", json=config, headers=headers(token)).status_code == 422


def test_jira_notion_and_drive_browse(client):
    http, _ = client
    token, project = make_project(http)
    for source in ("jira", "notion", "drive"):
        connect(http, project, token, source)
    assert http.get(f"/projects/{project}/sources/jira/projects", headers=headers(token)).json() == [{"key": "KAN", "name": "Phoenix"}]
    assert http.get(f"/projects/{project}/sources/notion/search?q=Plan", headers=headers(token)).json()[0]["title"] == "Plan"
    assert http.get(f"/projects/{project}/sources/drive/browse", headers=headers(token)).json()["items"][0]["id"] == "file-1"
