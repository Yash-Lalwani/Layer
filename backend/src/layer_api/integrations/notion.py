from layer_api.integrations.composio_client import ComposioToolSession


def title_of(item: dict) -> str:
    if item.get("object") == "database":
        parts = item.get("title") or []
    else:
        properties = item.get("properties") or {}
        parts = next((value.get("title", []) for value in properties.values() if value.get("type") == "title"), [])
    return "".join(part.get("plain_text") or part.get("text", {}).get("content", "") for part in parts) or "Untitled"


async def search(tools: ComposioToolSession, query: str) -> list[dict]:
    data = await tools.call("NOTION_SEARCH_NOTION_PAGE", {"query": query, "page_size": 100})
    return [{
        "id": item["id"], "title": title_of(item),
        "kind": item["object"], "url": item.get("url") or "",
    } for item in data.get("results", []) if item.get("object") in {"page", "database"}]
