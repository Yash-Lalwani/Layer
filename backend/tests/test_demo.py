import asyncio
from datetime import timedelta, timezone

from sqlalchemy import select

from conftest import headers, register
from layer_api.db import ChatSession, Message, Project, ProjectSource, User, now
from layer_api.memory.store import list_facts, save_facts


def seed_template(http):
    async def seed():
        async with http.app.state.session_factory() as db:
            owner = User(name="Layer Demo", email=None, is_guest=False)
            db.add(owner)
            await db.flush()
            template = Project(user_id=owner.id, name="Phoenix Demo", collection_id="layer-demo-phoenix", is_demo=True)
            db.add(template)
            await db.flush()
            for source, config in {
                "drive": {"folder_ids": ["folder-1"], "file_ids": []},
                "gmail": {"labels": ["phoenix"], "senders": [], "keywords": [], "query": "label:phoenix"},
                "jira": {"project_key": "PHX", "jql": None},
                "notion": {"page_ids": ["page-1"], "database_ids": []},
            }.items():
                db.add(ProjectSource(project_id=template.id, source_type=source, status="connected",
                                     composio_account_id=f"demo-{source}", config=config))
            await db.commit()
    asyncio.run(seed())


class SimpleGraph:
    async def astream(self, inputs, **kwargs):
        answer = {"status": "completed", "blocked_reason": None, "text": "Demo answer", "statements": [],
                  "sources": [], "plan": [], "verification": {"checked": 0, "supported": 0, "removed": 0, "succeeded": False},
                  "insufficient_context": True, "pending_memory": None, "metadata": {"latency_ms": 1}}
        yield {"type": "updates", "data": {"guard_output": {"answer_payload": answer}}}


def test_guest_is_isolated_read_only_and_limited_to_seven_questions(client):
    http, engine = client
    seed_template(http)
    engine.collections["layer-demo-phoenix"] = "Phoenix Demo"
    response = http.post("/auth/demo")
    assert response.status_code == 201, response.text
    data = response.json()
    auth = headers(data["token"])
    project_id = data["project_id"]
    assert http.get("/auth/me", headers=auth).json()["is_guest"] is True
    assert http.get("/projects", headers=auth).json()[0]["id"] == project_id
    assert len(http.get(f"/projects/{project_id}/sources", headers=auth).json()) == 4
    other = http.post("/auth/demo").json()
    other_auth = headers(other["token"])
    registered = register(http)
    assert http.get(f"/projects/{other['project_id']}", headers=auth).status_code == 404
    assert http.get(f"/projects/{project_id}", headers=other_auth).status_code == 404
    assert http.get(f"/projects/{project_id}", headers=headers(registered["token"])).status_code == 404
    assert http.get("/projects", headers=headers(registered["token"])).json() == []
    assert http.get("/projects", headers=other_auth).json()[0]["id"] == other["project_id"]
    assert http.post("/projects", json={"name": "No"}, headers=auth).status_code == 403
    assert http.patch(f"/projects/{project_id}", json={"name": "No"}, headers=auth).status_code == 403
    assert http.delete(f"/projects/{project_id}/sources/drive", headers=auth).status_code == 403
    assert http.put(f"/projects/{project_id}/sources/gmail/config", json={}, headers=auth).status_code == 403
    assert http.post(f"/projects/{project_id}/sources/gmail/connect", headers=auth).status_code == 403
    assert http.get(f"/projects/{project_id}/sources/drive/browse", headers=auth).status_code == 403
    assert http.get(f"/projects/{project_id}/sources/notion/search?q=other", headers=auth).status_code == 403

    chat_id = http.post(f"/projects/{project_id}/chats", json={}, headers=auth).json()["id"]
    http.app.state.agent_graph = SimpleGraph()
    for number in range(7):
        answer = http.post(f"/chats/{chat_id}/messages/stream", json={"content": f"Question {number}"}, headers=auth)
        assert answer.status_code == 200 and "event: final" in answer.text
    assert http.get("/auth/me", headers=auth).json()["questions_left"] == 0
    eighth = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Question 8"}, headers=auth)
    assert eighth.status_code == 429 and eighth.json()["error"]["code"] == "demo_limit_reached"


def test_expired_guest_cleanup_keeps_shared_collection(client):
    http, engine = client
    seed_template(http)
    engine.collections["layer-demo-phoenix"] = "Phoenix Demo"
    created = http.post("/auth/demo").json()
    auth = headers(created["token"])
    guest_id = http.get("/auth/me", headers=auth).json()["id"]
    project_id = created["project_id"]
    chat_id = http.post(f"/projects/{project_id}/chats", json={}, headers=auth).json()["id"]

    async def expired():
        async with http.app.state.session_factory() as db:
            guest = await db.get(User, guest_id)
            expiry = guest.expires_at.replace(tzinfo=timezone.utc) if guest.expires_at.tzinfo is None else guest.expires_at
            assert timedelta(hours=23, minutes=59) <= expiry - now() <= timedelta(hours=24)
            guest.expires_at = now() - timedelta(hours=1)
            db.add(Message(chat_id=chat_id, role="user", content="Old question"))
            await db.commit()
        await save_facts(http.app.state.memory_store, project_id, chat_id, ["Old demo fact"])
    asyncio.run(expired())
    assert http.get("/auth/me", headers=auth).status_code == 401
    assert http.post("/auth/demo").status_code == 201

    async def check():
        async with http.app.state.session_factory() as db:
            assert await db.get(User, guest_id) is None
            assert await db.get(Project, project_id) is None
            assert await db.get(ChatSession, chat_id) is None
            assert await db.scalar(select(Message).where(Message.chat_id == chat_id)) is None
        assert await list_facts(http.app.state.memory_store, project_id) == []
    asyncio.run(check())
    assert engine.collections == {"layer-demo-phoenix": "Phoenix Demo"}
