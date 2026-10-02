import asyncio
from types import SimpleNamespace

from conftest import headers, register
from layer_api.agent.citations import VerificationUnavailable
from layer_api.db import Message


def test_chats_are_owned_and_messages_stream_to_saved_final(client):
    http, _ = client
    first = register(http)
    other = register(http, "other@example.com")
    project = http.post("/projects", json={"name": "Phoenix"}, headers=headers(first["token"])).json()["id"]
    created = http.post(f"/projects/{project}/chats", json={}, headers=headers(first["token"]))
    assert created.status_code == 201
    chat_id = created.json()["id"]
    assert http.get(f"/projects/{project}/chats", headers=headers(other["token"])).status_code == 404
    assert http.get(f"/chats/{chat_id}/messages", headers=headers(other["token"])).status_code == 404
    assert http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Hello"}, headers=headers(other["token"])).status_code == 404

    class FakeGraph:
        async def astream(self, inputs, **kwargs):
            yield {"type": "custom", "data": {"step": "planning", "label": "Planning"}}
            yield {"type": "messages", "data": (type("Token", (), {"content": "Draft"})(), {"langgraph_node": "synthesize"})}
            answer = {"status": "completed", "blocked_reason": None, "text": "Checked [1]", "statements": [], "sources": [],
                      "plan": [], "verification": {"checked": 1, "supported": 1, "removed": 0, "succeeded": True},
                      "insufficient_context": False, "pending_memory": None, "metadata": {"latency_ms": 10}}
            yield {"type": "updates", "data": {"guard_output": {"answer_payload": answer}}}

    http.app.state.agent_graph = FakeGraph()
    response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Summarize Phoenix"}, headers=headers(first["token"]))
    assert response.status_code == 200
    assert "event: step" in response.text and "event: token" in response.text and "event: final" in response.text
    assert response.text.index("event: token") < response.text.index("event: final")
    messages = http.get(f"/chats/{chat_id}/messages", headers=headers(first["token"])).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["answer"]["text"] == "Checked [1]"
    assert http.get(f"/projects/{project}/chats", headers=headers(first["token"])).json()[0]["title"] == "Summarize Phoenix"


def test_failed_verification_reports_error_without_saving_draft(client):
    http, _ = client
    auth = register(http)
    project = http.post("/projects", json={"name": "Phoenix"}, headers=headers(auth["token"])).json()["id"]
    chat_id = http.post(f"/projects/{project}/chats", json={}, headers=headers(auth["token"])).json()["id"]

    class FailedGraph:
        async def astream(self, inputs, **kwargs):
            yield {"type": "messages", "data": (type("Token", (), {"content": "Unverified draft"})(), {"langgraph_node": "synthesize"})}
            raise VerificationUnavailable("Citation verification failed; the draft answer was not saved.")

    http.app.state.agent_graph = FailedGraph()
    response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Summarize"}, headers=headers(auth["token"]))
    assert "event: token" in response.text
    assert "event: error" in response.text
    assert "verification_failed" in response.text
    assert "event: final" not in response.text
    assert http.get(f"/chats/{chat_id}/messages", headers=headers(auth["token"])).json() == []


def test_new_message_skips_pending_memory_approval(client):
    http, _ = client
    auth = register(http)
    bearer = headers(auth["token"])
    project = http.post("/projects", json={"name": "Phoenix"}, headers=bearer).json()["id"]
    chat_id = http.post(f"/projects/{project}/chats", json={}, headers=bearer).json()["id"]

    async def seed_pending():
        async with http.app.state.session_factory() as db:
            db.add(Message(chat_id=chat_id, role="assistant", content="Old answer", answer={
                "text": "Old answer", "pending_memory": {"approval_id": "pending-1", "facts": ["Old fact"]},
            }))
            await db.commit()

    asyncio.run(seed_pending())

    class SkipGraph:
        def __init__(self):
            self.pending = True
            self.resumes = []

        async def aget_state(self, config):
            return SimpleNamespace(next=("approve_memory",) if self.pending else ())

        async def ainvoke(self, command, config):
            self.resumes.append(command.resume)
            self.pending = False

        async def astream(self, inputs, **kwargs):
            answer = {"status": "completed", "blocked_reason": None, "text": "New answer",
                      "statements": [], "sources": [], "plan": [],
                      "verification": {"checked": 0, "supported": 0, "removed": 0, "succeeded": False},
                      "insufficient_context": True, "pending_memory": None, "metadata": {"latency_ms": 1}}
            yield {"type": "updates", "data": {"guard_output": {"answer_payload": answer}}}

    graph = SkipGraph()
    http.app.state.agent_graph = graph
    response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "New question"}, headers=bearer)
    assert response.status_code == 200 and "event: final" in response.text
    assert graph.resumes == [{"decision": "skipped", "facts": []}]
    messages = http.get(f"/chats/{chat_id}/messages", headers=bearer).json()
    assert messages[0]["memory_decision"] == "skipped"
    assert messages[0]["answer"]["pending_memory"] is None
    assert http.get(f"/projects/{project}/memory", headers=bearer).json() == []
