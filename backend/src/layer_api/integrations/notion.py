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


async def evidence(tools: ComposioToolSession, config: dict, terms: str) -> list[dict]:
    async def database_pages(database_id: str) -> list[str]:
        ids = []
        cursor = None
        while True:
            args = {"database_id": database_id, "page_size": 100}
            if cursor:
                args["start_cursor"] = cursor
            data = await tools.call("NOTION_QUERY_DATABASE", args)
            ids.extend(item["id"] for item in data.get("results", []) if item.get("object") == "page" and item.get("id"))
            cursor = data.get("next_cursor") if data.get("has_more") else None
            if not cursor:
                break
        return ids

    page_ids = list(dict.fromkeys(config.get("page_ids", [])))
    seen_databases = set()
    for database_id in config.get("database_ids", []):
        seen_databases.add(database_id)
        page_ids.extend(await database_pages(database_id))

    found = []
    seen = set()
    queue = page_ids
    while queue:
        page_id = queue.pop(0)
        if page_id in seen:
            continue
        seen.add(page_id)
        details = await tools.call("NOTION_RETRIEVE_PAGE", {"page_id": page_id})
        page = await tools.call("NOTION_GET_PAGE_MARKDOWN", {"page_id": page_id})
        markdown = str(page.get("markdown") or page.get("content") or page.get("text") or "")
        title = title_of(details)
        url = details.get("url") or f"https://www.notion.so/{page_id.replace('-', '')}"
        for index, paragraph in enumerate(markdown.split("\n\n")):
            paragraph = paragraph.strip()
            if paragraph and paragraph != "<empty-block/>":
                found.append({"id": f"notion:{page_id}:{index}", "source_type": "notion", "title": str(title),
                              "text": paragraph[:1500], "url": url, "date": details.get("last_edited_time")})
        cursor = None
        while True:
            args = {"block_id": page_id, "page_size": 100}
            if cursor:
                args["start_cursor"] = cursor
            blocks = await tools.call("NOTION_FETCH_BLOCK_CONTENTS", args)
            for block in blocks.get("results", []):
                if not block.get("id"):
                    continue
                if block.get("type") == "child_page":
                    queue.append(block["id"])
                if block.get("type") == "child_database" and block["id"] not in seen_databases:
                    seen_databases.add(block["id"])
                    queue.extend(await database_pages(block["id"]))
            cursor = blocks.get("next_cursor") if blocks.get("has_more") else None
            if not cursor:
                break
    words = [word.lower() for word in terms.split() if len(word) > 2]
    found.sort(key=lambda item: sum(word in item["text"].lower() for word in words), reverse=True)
    return found[:30]
