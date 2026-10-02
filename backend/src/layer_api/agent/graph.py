from uuid import uuid4

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from layer_api.agent.nodes import answer, planning, search
from layer_api.agent.state import AgentState
from layer_api.memory.extraction import propose_facts
from layer_api.memory.store import list_facts, save_facts
from layer_api.schemas import ApiError


def build_graph(settings, engine, composio, checkpointer, small_model=None, strong_model=None, store=None):
    small = small_model or (ChatOpenAI(model=settings.llm_model_small, api_key=settings.openai_api_key) if settings.openai_api_key else None)
    strong = strong_model or (ChatOpenAI(model=settings.llm_model_strong, api_key=settings.openai_api_key) if settings.openai_api_key else None)

    async def plan(state: AgentState):
        if small is None:
            raise ApiError(503, "server_error", "Set OPENAI_API_KEY in backend/.env to use chat")
        return await planning.plan(state, small)

    async def load_memory(state: AgentState):
        facts = await list_facts(store, state["project_id"]) if store else []
        return planning.load_memory(state, [fact["text"] for fact in facts])

    async def propose_memory(state: AgentState):
        if store is None or state.get("blocked_reason") or not state.get("verification", {}).get("succeeded"):
            return {"memory_candidates": []}
        facts = await propose_facts(small, state["question"], state["answer_text"], state.get("memory_facts", []))
        return {"memory_candidates": facts, "memory_approval_id": str(uuid4()) if facts else None}

    def approve_memory(state: AgentState):
        decision = interrupt({"approval_id": state["memory_approval_id"], "facts": state["memory_candidates"]})
        return {"memory_decision": decision["decision"], "approved_facts": decision.get("facts", [])}

    async def save_memory(state: AgentState):
        await save_facts(store, state["project_id"], state["chat_id"], state["approved_facts"])
        return {}

    async def search_source(state: AgentState):
        return await search.search_source(state, engine, composio)

    async def rerank(state: AgentState):
        return await search.rerank_and_grade(state, engine)

    async def synthesize(state: AgentState):
        return await answer.synthesize(state, strong)

    async def verify(state: AgentState):
        return await answer.verify_citations(state, engine)

    def after_guard(state: AgentState):
        return "guard_output" if state.get("blocked_reason") else "load_memory"

    def dispatch(state: AgentState):
        if not state["plan"]:
            return "synthesize"
        return [Send(f'search_{task["source"]}', {**state, "task": task, "step_index": index}) for index, task in enumerate(state["plan"])]

    def after_proposal(state: AgentState):
        return "approve_memory" if state.get("memory_candidates") else END

    def after_approval(state: AgentState):
        return "save_memory" if state.get("memory_decision") == "approved" and state.get("approved_facts") else END

    graph = StateGraph(AgentState)
    graph.add_node("guard_input", planning.guard_input)
    graph.add_node("load_memory", load_memory)
    graph.add_node("plan", plan)
    for source in ("drive", "gmail", "jira", "notion"):
        graph.add_node(f"search_{source}", search_source)
        graph.add_edge(f"search_{source}", "rerank_and_grade")
    graph.add_node("rerank_and_grade", rerank)
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify_citations", verify)
    graph.add_node("guard_output", answer.guard_output)
    graph.add_node("propose_memory", propose_memory)
    graph.add_node("approve_memory", approve_memory)
    graph.add_node("save_memory", save_memory)
    graph.add_edge(START, "guard_input")
    graph.add_conditional_edges("guard_input", after_guard)
    graph.add_edge("load_memory", "plan")
    graph.add_conditional_edges("plan", dispatch)
    graph.add_edge("rerank_and_grade", "synthesize")
    graph.add_edge("synthesize", "verify_citations")
    graph.add_edge("verify_citations", "guard_output")
    graph.add_edge("guard_output", "propose_memory")
    graph.add_conditional_edges("propose_memory", after_proposal)
    graph.add_conditional_edges("approve_memory", after_approval)
    graph.add_edge("save_memory", END)
    return graph.compile(checkpointer=checkpointer, store=store)
