from layer_api.integrations.composio_client import ComposioToolSession
import re


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


def _body(message: dict) -> str:
    for key in ("body", "textBody", "text_body", "plainTextBody", "snippet"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    preview_data = message.get("preview")
    if isinstance(preview_data, dict):
        return str(preview_data.get("body") or "")
    payload = message.get("payload") or {}
    if isinstance(payload, dict):
        return _body(payload)
    return ""


async def evidence(tools: ComposioToolSession, config: dict, terms: str) -> list[dict]:
    keywords = " ".join(re.findall(r"[\w-]+", terms)[:8])
    query = " ".join(part for part in (gmail_query(config), keywords) if part) or "in:anywhere"
    data = await tools.call("GMAIL_FETCH_EMAILS", {"query": query, "max_results": 10, "include_payload": True, "verbose": False, "user_id": "me"})
    found = []
    for message in data.get("messages", [])[:10]:
        message_id = message.get("messageId") or message.get("id")
        if not message_id:
            continue
        detail = message
        if not _body(detail):
            detail = await tools.call("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": message_id, "user_id": "me", "format": "full"})
        subject = detail.get("subject") or message.get("subject") or "(no subject)"
        sender = detail.get("sender") or message.get("sender") or ""
        date = detail.get("messageTimestamp") or message.get("messageTimestamp") or ""
        found.append({"id": f"gmail:{message_id}", "source_type": "gmail", "title": subject,
                      "text": f"Subject: {subject}\nFrom: {sender}\nDate: {date}\n{_body(detail)}"[:4000],
                      "url": f"https://mail.google.com/mail/u/0/#all/{message_id}", "date": str(date) or None})
    return found
