from langchain_core.messages import BaseMessage
from langgraph.config import get_stream_writer
from langgraph.types import Overwrite
from pydantic import BaseModel, Field

from layer_api.agent.prompts import PLAN_SYSTEM
from layer_api.agent.state import AgentState, PlanTask, SourceType


class ProposedTask(BaseModel):
    sub_question: str
    source: SourceType
    search_terms: str


class ProposedPlan(BaseModel):
    tasks: list[ProposedTask] = Field(max_length=4)


def guard_input(state: AgentState) -> dict:
    question = state["question"].strip()
    if not question or len(question) > 2000:
        return {"blocked_reason": "Enter a question of at most 2000 characters.", "evidence": Overwrite([])}
    return {"question": question, "blocked_reason": None, "evidence": Overwrite([]),
            "plan": [], "answer_text": "", "statements": [], "sources": [], "verification": {},
            "answer_payload": {}, "insufficient_context": False}


def load_memory(state: AgentState, facts: list[str]) -> dict:
    return {"recent_messages": state.get("messages", [])[-10:], "memory_facts": facts, "memory_candidates": []}


def _history(messages: list[BaseMessage]) -> str:
    return "\n".join(f"{message.type}: {message.content}" for message in messages)


async def plan(state: AgentState, model) -> dict:
    get_stream_writer()({"step": "planning", "label": "Planning"})
    allowed = list(state["source_configs"])
    if not allowed:
        return {"plan": [], "insufficient_context": True}
    prompt = (
        f"Allowed sources: {', '.join(allowed)}\n"
        f"Approved project facts:\n{chr(10).join(state.get('memory_facts', []))}\n"
        f"Recent chat:\n{_history(state['recent_messages'])}\n"
        f"Question: {state['question']}"
    )
    result: ProposedPlan = await model.with_structured_output(ProposedPlan).ainvoke([
        ("system", PLAN_SYSTEM), ("human", prompt)
    ])
    tasks: list[PlanTask] = []
    for task in result.tasks:
        if task.source in allowed and task.sub_question.strip():
            tasks.append({"sub_question": task.sub_question.strip(), "source": task.source, "search_terms": task.search_terms.strip()})
    if not tasks:
        tasks = [{"sub_question": state["question"], "source": allowed[0], "search_terms": state["question"]}]
    return {"plan": tasks[:4]}
