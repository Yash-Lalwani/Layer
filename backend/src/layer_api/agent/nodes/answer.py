import time

from langchain_core.messages import AIMessage
from langgraph.config import get_stream_writer

from layer_api.agent.citations import VerificationUnavailable, checked_answer, citation_request, parse_statements
from layer_api.agent.prompts import ANSWER_SYSTEM
from layer_api.agent.state import AgentState


async def synthesize(state: AgentState, model) -> dict:
    get_stream_writer()({"step": "writing", "label": "Writing answer"})
    evidence = state.get("evidence", [])
    if not evidence:
        return {"answer_text": "I couldn't find enough information in this project's configured sources to answer that."}
    lines = []
    for number, item in enumerate(evidence, 1):
        lines.append(f"[source {number}] {item['source_type']} — {item['title']}\n<untrusted_evidence>\n{item['text']}\n</untrusted_evidence>")
    prompt = f"Question: {state['question']}\n\nEvidence:\n" + "\n\n".join(lines)
    response = await model.ainvoke([("system", ANSWER_SYSTEM), ("human", prompt)])
    return {"answer_text": str(response.content)}


async def verify_citations(state: AgentState, engine) -> dict:
    get_stream_writer()({"step": "verifying", "label": "Checking citations"})
    evidence = state.get("evidence", [])
    if not evidence:
        return {"statements": [], "sources": [], "verification": {"checked": 0, "supported": 0, "removed": 0, "succeeded": False}}
    statements = parse_statements(state["answer_text"])
    claims, passages = citation_request(statements, evidence)
    if not any(claim["chunk_ids"] for claim in claims):
        return {"answer_text": "I couldn't verify an answer from the available evidence.", "statements": [], "sources": [],
                "verification": {"checked": 0, "supported": 0, "removed": len(statements), "succeeded": False}, "insufficient_context": True}
    try:
        result = await engine.verify_citations(claims, passages)
    except Exception as exc:
        raise VerificationUnavailable("Citation verification failed; the draft answer was not saved.") from exc
    checks = result.get("checks", [])
    if result.get("warnings") or any(not any(check.get("index") == index and check.get("supported") is not None for check in checks) for index, claim in enumerate(claims) if claim["chunk_ids"]):
        raise VerificationUnavailable("Citation verification did not complete; the draft answer was not saved.")
    text, final_statements, sources, verification = checked_answer(statements, evidence, checks)
    if not text:
        text = "I couldn't verify an answer from the available evidence."
    return {"answer_text": text, "statements": final_statements, "sources": sources,
            "verification": verification, "insufficient_context": state.get("insufficient_context", False) or verification["removed"] > 0 or not final_statements}


def guard_output(state: AgentState) -> dict:
    blocked = state.get("blocked_reason")
    evidence = state.get("evidence", [])
    plan = [{"sub_question": task["sub_question"], "source": task["source"],
             "status": "answered" if any(item["step_index"] == index for item in evidence) else "no_evidence"}
            for index, task in enumerate(state.get("plan", []))]
    payload = {
        "status": "blocked" if blocked else "completed", "blocked_reason": blocked,
        "text": "" if blocked else state.get("answer_text", ""),
        "statements": state.get("statements", []), "sources": state.get("sources", []),
        "plan": plan, "verification": state.get("verification", {"checked": 0, "supported": 0, "removed": 0, "succeeded": False}),
        "insufficient_context": state.get("insufficient_context", False), "pending_memory": None,
        "metadata": {"latency_ms": round((time.perf_counter() - state["started_at"]) * 1000)},
    }
    return {"answer_payload": payload, "messages": [AIMessage(content=payload["text"] or blocked or "")]}
