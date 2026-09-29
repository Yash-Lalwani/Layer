import os

import pytest
from fastapi.testclient import TestClient

from layer_api.config import Settings
from layer_api.integrations.engine_client import EngineError

os.environ.setdefault("JWT_SECRET", "phase-one-test-secret-at-least-thirty-two-bytes")

from layer_api.main import create_app


class FakeEngine:
    def __init__(self):
        self.collections: dict[str, str] = {}
        self.fail_create = False
        self.fail_delete = False
        self.healthy = True

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


@pytest.fixture
def client(tmp_path):
    engine = FakeEngine()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'layer.db'}",
        jwt_secret="phase-one-test-secret-at-least-thirty-two-bytes",
        rag_engine_api_key="test-key",
    )
    app = create_app(settings, engine)
    with TestClient(app) as test_client:
        yield test_client, engine


def register(client: TestClient, email: str = "yash@example.com") -> dict:
    response = client.post("/auth/register", json={"name": "Yash", "email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
