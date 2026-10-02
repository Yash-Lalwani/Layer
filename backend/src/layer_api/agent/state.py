import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


SourceType = Literal["drive", "gmail", "jira", "notion"]


class PlanTask(TypedDict):
    sub_question: str
    source: SourceType
    search_terms: str


class Evidence(TypedDict):
    id: str
    source_type: SourceType
    title: str
    text: str
    url: str | None
    date: str | None
    step_index: int
    score: float | None


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    composio_user_id: str
    chat_id: str
    project_id: str
    collection_id: str
    question: str
    started_at: float
    source_configs: dict[str, dict]
    source_accounts: dict[str, str]
    recent_messages: list[BaseMessage]
    memory_facts: list[str]
    plan: list[PlanTask]
    task: PlanTask
    step_index: int
    evidence: Annotated[list[Evidence], operator.add]
    answer_text: str
    statements: list[dict]
    sources: list[dict]
    verification: dict
    memory_candidates: list[str]
    memory_approval_id: str | None
    memory_decision: str | None
    approved_facts: list[str]
    blocked_reason: str | None
    insufficient_context: bool
    answer_payload: dict
