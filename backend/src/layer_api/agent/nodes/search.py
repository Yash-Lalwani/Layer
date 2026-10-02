from collections import defaultdict

from langgraph.config import get_stream_writer
from langgraph.types import Overwrite

from layer_api.agent.state import AgentState, Evidence
from layer_api.integrations import gmail, jira, notion


async def search_source(state: AgentState, engine, composio) -> dict:
    task = state["task"]
    source = task["source"]
    get_stream_writer()({"step": "searching", "source": source, "label": f"Searching {source.title() if source != 'drive' else 'Drive'}"})
    if source == "drive":
        result = await engine.search(state["collection_id"], task["search_terms"] or task["sub_question"], top_k=8)
        found = []
        for chunk in result.get("chunks", []):
            if chunk.get("grade") in {"irrelevant", "not_relevant"} or not chunk.get("text"):
                continue
            metadata = chunk.get("metadata") or {}
            found.append({"id": f'drive:{chunk["id"]}', "source_type": "drive",
                          "title": metadata.get("name") or chunk.get("source") or "Drive document",
                          "text": chunk["text"][:4000], "url": chunk.get("url") or metadata.get("url"),
                          "date": metadata.get("modified_time"), "score": chunk.get("rerank_score")})
    else:
        async with composio.tools(state.get("composio_user_id", state["user_id"]), source, state["source_accounts"][source]) as tools:
            if source == "gmail":
                found = await gmail.evidence(tools, state["source_configs"][source], task["search_terms"])
            elif source == "jira":
                found = await jira.evidence(tools, state["source_configs"][source], task["search_terms"])
            else:
                found = await notion.evidence(tools, state["source_configs"][source], task["search_terms"])
    return {"evidence": [{**item, "step_index": state["step_index"], "score": item.get("score")} for item in found]}


async def rerank_and_grade(state: AgentState, engine) -> dict:
    grouped: dict[int, list[Evidence]] = defaultdict(list)
    for item in state.get("evidence", []):
        grouped[item["step_index"]].append(item)
    kept: list[Evidence] = []
    for index, task in enumerate(state["plan"]):
        items = grouped[index]
        if task["source"] == "drive":
            ranked = items[:5]
        elif items:
            result = await engine.rerank(task["sub_question"], [{"id": item["id"], "text": item["text"]} for item in items], top_k=5)
            scores = {item["id"]: item["score"] for item in result.get("result", result.get("passages", []))}
            ranked = [dict(item, score=scores[item["id"]]) for item in items if item["id"] in scores]
            ranked.sort(key=lambda item: item["score"], reverse=True)
        else:
            ranked = []
        kept.extend(ranked)
    unique = list({item["id"]: item for item in kept}.values())
    return {"evidence": Overwrite(unique), "insufficient_context": any(not any(item["step_index"] == index for item in unique) for index in range(len(state["plan"]))) or not unique}
