from layer_api.integrations.composio_client import ComposioToolSession


def gmail_query(config: dict) -> str:
    def quoted(value: str) -> str:
        clean = value.replace('"', '').strip()
        return f'"{clean}"' if " " in clean else clean

    def any_of(prefix: str, values: list[str]) -> str:
        terms = [f"{prefix}{quoted(value)}" for value in values if value.strip()]
        return "{" + " ".join(terms) + "}" if len(terms) > 1 else (terms[0] if terms else "")

    parts = [any_of("label:", config.get("labels", [])), any_of("from:", config.get("senders", []))]
    parts += [quoted(keyword) for keyword in config.get("keywords", []) if keyword.strip()]
    return " ".join(part for part in parts if part) or config.get("query", "").strip()


async def labels(tools: ComposioToolSession) -> list[str]:
    data = await tools.call("GMAIL_LIST_LABELS", {"user_id": "me"})
    return [item["name"] for item in data.get("labels", []) if item.get("name")]


async def preview(tools: ComposioToolSession, config: dict) -> list[dict]:
    data = await tools.call("GMAIL_FETCH_EMAILS", {
        "query": gmail_query(config) or "in:anywhere",
        "max_results": 10,
        "include_payload": False,
        "verbose": False,
        "user_id": "me",
    })
    messages = data.get("messages", [])
    return [{
        "id": message.get("messageId") or message.get("id") or "",
        "subject": message.get("subject") or "(no subject)",
        "from": message.get("sender") or "",
        "date": message.get("messageTimestamp") or "",
        "snippet": (message.get("preview") or {}).get("body", "") if isinstance(message.get("preview"), dict) else str(message.get("preview") or ""),
    } for message in messages]
