from datetime import datetime, timezone
from uuid import uuid4


def namespace(project_id: str) -> tuple[str, str, str]:
    return ("project", project_id, "facts")


async def list_facts(store, project_id: str) -> list[dict]:
    items = []
    while True:
        page = await store.asearch(namespace(project_id), limit=100, offset=len(items))
        items.extend(page)
        if len(page) < 100:
            break
    return [
        {"id": item.key, "text": item.value["text"],
         "source_chat_id": item.value.get("source_chat_id"),
         "created_at": item.value["created_at"]}
        for item in sorted(items, key=lambda item: item.value.get("created_at", ""), reverse=True)
    ]


async def save_facts(store, project_id: str, chat_id: str, facts: list[str]) -> None:
    for text in facts:
        await store.aput(namespace(project_id), str(uuid4()), {
            "text": text, "source_chat_id": chat_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
