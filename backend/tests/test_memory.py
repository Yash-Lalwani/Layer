import asyncio
import time
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from conftest import FakeEngine
from test_agent import SmallModel, StrongModel
from layer_api.agent.graph import build_graph
from layer_api.config import Settings
from layer_api.memory.store import list_facts


def inputs(chat_id: str, question: str) -> dict:
    return {"messages": [HumanMessage(content=question)], "question": question,
            "chat_id": chat_id, "user_id": "user", "project_id": "project",
            "collection_id": "collection", "source_configs": {"drive": {"file_ids": ["file-1"]}},
            "source_accounts": {}, "started_at": time.perf_counter()}


def test_memory_requires_approval_and_is_available_in_new_chat(monkeypatch):
    async def extract(*args):
        return ["Phoenix launches in November"]
    monkeypatch.setattr("layer_api.agent.graph.propose_facts", extract)
    store = InMemoryStore()
    small = SmallModel()
    graph = build_graph(Settings(_env_file=None, oauth_state_secret="test", database_url="sqlite+aiosqlite://"),
                        FakeEngine(), None, InMemorySaver(), small, StrongModel(), store=store)

    async def run():
        rejected = str(uuid4())
        config = {"configurable": {"thread_id": rejected}}
        await graph.ainvoke(inputs(rejected, "When is launch?"), config=config)
        assert "approve_memory" in (await graph.aget_state(config)).next
        assert await list_facts(store, "project") == []
        await graph.ainvoke(Command(resume={"decision": "rejected", "facts": []}), config=config)
        assert await list_facts(store, "project") == []

        approved = str(uuid4())
        config = {"configurable": {"thread_id": approved}}
        await graph.ainvoke(inputs(approved, "What should we remember?"), config=config)
        await graph.ainvoke(Command(resume={"decision": "approved", "facts": ["Phoenix launches in November"]}), config=config)
        facts = await list_facts(store, "project")
        assert len(facts) == 1 and facts[0]["source_chat_id"] == approved

        new_chat = str(uuid4())
        await graph.ainvoke(inputs(new_chat, "What changed?"), config={"configurable": {"thread_id": new_chat}})
        assert "Approved project facts:\nPhoenix launches in November" in small.prompts[-1]

        skipped = str(uuid4())
        config = {"configurable": {"thread_id": skipped}}
        await graph.ainvoke(inputs(skipped, "Another question"), config=config)
        await graph.ainvoke(Command(resume={"decision": "skipped", "facts": []}), config=config)
        assert len(await list_facts(store, "project")) == 1

    asyncio.run(run())
