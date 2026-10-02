import asyncio
import time
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from layer_api.agent.graph import build_graph
from layer_api.agent.nodes.planning import ProposedPlan, ProposedTask
from layer_api.config import Settings


class SmallModel:
    def __init__(self, tasks=None):
        self.prompts = []
        self.tasks = tasks

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        self.prompts.append(messages[-1][1])
        return ProposedPlan(tasks=self.tasks or [ProposedTask(sub_question="Project timeline", source="gmail", search_terms="Phoenix timeline")])


class StrongModel:
    async def ainvoke(self, messages):
        return AIMessage(content="Phoenix launches in November [1].")


def test_plan_only_uses_configured_sources_and_followup_uses_history(client):
    _, engine = client
    small = SmallModel()
    settings = Settings(_env_file=None, oauth_state_secret="test", database_url="sqlite+aiosqlite://")
    graph = build_graph(settings, engine, None, InMemorySaver(), small, StrongModel())
    config = {"configurable": {"thread_id": str(uuid4())}}

    async def run(question):
        inputs = {"messages": [HumanMessage(content=question)], "question": question,
                  "user_id": "user-1", "project_id": "project-1", "collection_id": "collection-1",
                  "source_configs": {"drive": {"file_ids": ["file-1"], "folder_ids": []}},
                  "source_accounts": {}, "started_at": time.perf_counter()}
        async for _ in graph.astream(inputs, config=config, stream_mode=["custom", "updates"], version="v2"):
            pass
        return (await graph.aget_state(config)).values

    first = asyncio.run(run("When does Phoenix launch?"))
    assert first["plan"][0]["source"] == "drive"
    assert first["answer_payload"]["verification"]["succeeded"] is True
    second = asyncio.run(run("And what changed?"))
    assert second["answer_payload"]["sources"][0]["type"] == "drive"
    assert "Phoenix launches in November" in small.prompts[1]


def test_send_runs_parallel_source_tasks(client):
    _, engine = client
    tasks = [
        ProposedTask(sub_question="Timeline", source="drive", search_terms="launch"),
        ProposedTask(sub_question="Deadline", source="drive", search_terms="November"),
    ]
    graph = build_graph(Settings(_env_file=None, oauth_state_secret="test", database_url="sqlite+aiosqlite://"),
                        engine, None, InMemorySaver(), SmallModel(tasks), StrongModel())
    config = {"configurable": {"thread_id": str(uuid4())}}
    inputs = {"messages": [HumanMessage(content="Summarize timeline and deadline")],
              "question": "Summarize timeline and deadline", "user_id": "user", "project_id": "project",
              "collection_id": "collection", "source_configs": {"drive": {"file_ids": ["file-1"]}},
              "source_accounts": {}, "started_at": time.perf_counter()}

    async def run():
        steps = []
        async for part in graph.astream(inputs, config=config, stream_mode=["custom", "updates"], version="v2"):
            if part["type"] == "custom" and part["data"].get("step") == "searching":
                steps.append(part["data"])
        return steps, (await graph.aget_state(config)).values

    steps, state = asyncio.run(run())
    assert len(steps) == 2
    assert len(state["plan"]) == 2
    assert state["answer_payload"]["status"] == "completed"
