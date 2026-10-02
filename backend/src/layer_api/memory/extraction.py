from pydantic import BaseModel, Field
from langmem import create_memory_manager


class ProjectFact(BaseModel):
    text: str = Field(description="One durable, self-contained project fact")


INSTRUCTIONS = """Extract only durable project facts: decisions, goals, owners, priorities,
deadlines, or stated preferences. Use the verified assistant answer as the source of truth.
Do not extract guesses, temporary status, or duplicates of existing facts. Each fact must
be self-contained. Return no facts when the conversation adds nothing durable."""


async def propose_facts(model, question: str, answer: str, existing: list[str]) -> list[str]:
    if not answer or not model:
        return []
    manager = create_memory_manager(model, schemas=[ProjectFact], instructions=INSTRUCTIONS,
                                    enable_updates=False, enable_deletes=False)
    result = await manager.ainvoke({"messages": [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]})
    seen = {fact.casefold().strip() for fact in existing}
    facts: list[str] = []
    for item in result:
        content = item.content
        text = content.text.strip() if isinstance(content, ProjectFact) else ""
        if text and text.casefold() not in seen:
            facts.append(text)
            seen.add(text.casefold())
    return facts[:3]
