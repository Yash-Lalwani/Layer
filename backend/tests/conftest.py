import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from layer_api.config import Settings
from layer_api.integrations.engine_client import EngineError
from layer_api.schemas import ApiError

os.environ.setdefault("OAUTH_STATE_SECRET", "source-state-test-secret-at-least-thirty-two-bytes")

from layer_api.main import create_app


class FakeEngine:
    def __init__(self):
        self.collections: dict[str, str] = {}
        self.fail_create = False
        self.fail_delete = False
        self.healthy = True
        self.documents: dict[str, dict] = {}

    async def health(self):
        return {"status": "ok" if self.healthy else "degraded"}

    async def create_collection(self, collection_id: str, name: str):
        if self.fail_create:
            raise EngineError("Collection creation failed")
        self.collections[collection_id] = name
        return {"id": collection_id, "name": name}

    async def delete_collection(self, collection_id: str):
        if self.fail_delete:
            raise EngineError("Collection deletion failed")
        del self.collections[collection_id]
        return {"ok": True}

    async def ingest_document(self, collection_id, content_base64, filename, doc_id, metadata):
        self.documents[doc_id] = {"doc_id": doc_id, "collection_id": collection_id, "filename": filename, "metadata": metadata}
        return {"status": "ingested"}

    async def delete_document(self, collection_id, doc_id):
        self.documents.pop(doc_id, None)
        return {"ok": True}

    async def list_documents(self, collection_id):
        return {"result": [doc for doc in self.documents.values() if doc["collection_id"] == collection_id]}

    async def search(self, collection_id, query, top_k=5):
        return {"chunks": [{"id": "chunk-1", "text": "Phoenix launches in November.", "source": "plan.md", "url": "https://drive.example/plan", "grade": "relevant", "metadata": {}}]}

    async def rerank(self, query, passages, top_k=5):
        return {"result": [{**passage, "score": 1.0} for passage in passages[:top_k]]}

    async def verify_citations(self, statements, passages):
        return {"checks": [{"index": index, "supported": bool(statement["chunk_ids"])} for index, statement in enumerate(statements)], "warnings": []}


class FakeTools:
    async def call(self, name, arguments=None):
        arguments = arguments or {}
        if name == "GOOGLEDRIVE_FIND_FILE":
            return {"files": [{"id": "file-1", "name": "notes.txt", "mimeType": "text/plain", "modifiedTime": "2026-09-30T12:00:00Z", "webViewLink": "https://drive.google.com/file-1"}]}
        if name == "GOOGLEDRIVE_GET_FILE_METADATA":
            return {"id": arguments["fileId"], "name": "notes.txt", "mimeType": "text/plain", "modifiedTime": "2026-09-30T12:00:00Z", "webViewLink": "https://drive.google.com/file-1"}
        if name == "GOOGLEDRIVE_DOWNLOAD_FILE":
            return {"file": {"s3url": "https://download.example/notes.txt"}}
        if name == "GMAIL_LIST_LABELS":
            return {"labels": [{"name": "INBOX"}]}
        if name == "GMAIL_FETCH_EMAILS":
            return {"messages": [{"messageId": "mail-1", "subject": "Update", "sender": "team@example.com", "messageTimestamp": "2026-09-30", "preview": {"body": "Ready"}}]}
        if name == "JIRA_GET_ALL_PROJECTS":
            return {"data": {"values": [{"key": "KAN", "name": "Phoenix"}]}}
        if name == "NOTION_SEARCH_NOTION_PAGE":
            return {"results": [{"object": "page", "id": "page-1", "url": "https://notion.so/page-1", "properties": {"title": {"type": "title", "title": [{"plain_text": "Plan"}]}}}]}
        raise AssertionError(name)


class FakeComposio:
    def __init__(self):
        self.accounts = {}

    async def authorize(self, user_id, source_type, callback_url):
        account_id = f"account-{source_type}-{user_id}"
        self.accounts[account_id] = {"status": "ACTIVE", "user_id": f"layer-user-{user_id}", "toolkit": {"slug": "googledrive" if source_type == "drive" else source_type}, "data": {"displayName": "Test account", "scope": "https://www.googleapis.com/auth/drive https://mail.google.com/"}}
        self.callback_url = callback_url
        return account_id, "https://connect.example/auth"

    async def account(self, account_id):
        return self.accounts[account_id]

    @asynccontextmanager
    async def tools(self, user_id, source_type, account_id):
        assert self.accounts[account_id]["user_id"] == f"layer-user-{user_id}"
        yield FakeTools()


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = FakeEngine()
    composio = FakeComposio()
    identities: dict[str, tuple[str, str, str]] = {}

    def fake_verify_session(request, settings):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token not in identities:
            raise ApiError(401, "unauthorized", "Please sign in")
        return identities[token][0]

    async def fake_profile(clerk_user_id, settings):
        return next((name, email) for subject, name, email in identities.values() if subject == clerk_user_id)

    monkeypatch.setattr("layer_api.auth.dependencies.verify_session", fake_verify_session)
    monkeypatch.setattr("layer_api.auth.dependencies.clerk_profile", fake_profile)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'layer.db'}",
        oauth_state_secret="source-state-test-secret-at-least-thirty-two-bytes",
        clerk_secret_key="test-clerk-secret",
        clerk_jwt_key="test-clerk-public-key",
        rag_engine_api_key="test-key",
        demo_token_secret="test-demo-secret-at-least-thirty-two-bytes",
    )
    app = create_app(settings, engine, composio)
    app.state.fake_composio = composio
    app.state.test_identities = identities
    with TestClient(app) as test_client:
        yield test_client, engine


def register(client: TestClient, email: str = "yash@example.com") -> dict:
    token = f"test-session-{uuid4()}"
    client.app.state.test_identities[token] = (f"clerk-{uuid4()}", "Yash", email.lower())
    response = client.get("/auth/me", headers=headers(token))
    assert response.status_code == 200, response.text
    return {"token": token, "user": response.json()}


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
