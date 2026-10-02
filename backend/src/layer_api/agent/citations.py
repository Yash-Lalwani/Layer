import re

from layer_api.agent.state import Evidence


MARKER = re.compile(r"\[(\d+)\]")


class VerificationUnavailable(Exception):
    pass


def parse_statements(text: str) -> list[dict]:
    statements = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        numbers = list(dict.fromkeys(int(value) for value in MARKER.findall(line)))
        clean = MARKER.sub("", line).strip()
        clean = re.sub(r"\s+([.,;:!?])", r"\1", clean)
        if clean:
            statements.append({"text": clean, "citation_numbers": numbers})
    return statements


def citation_request(statements: list[dict], evidence: list[Evidence]) -> tuple[list[dict], list[dict]]:
    claims = []
    for statement in statements:
        ids = [evidence[number - 1]["id"] for number in statement["citation_numbers"] if 1 <= number <= len(evidence)]
        claims.append({"text": statement["text"], "chunk_ids": ids})
    passages = [{"id": item["id"], "text": item["text"]} for item in evidence]
    return claims, passages


def checked_answer(statements: list[dict], evidence: list[Evidence], checks: list[dict]) -> tuple[str, list[dict], list[dict], dict]:
    by_index = {check["index"]: check for check in checks}
    kept = []
    used_numbers = []
    for index, statement in enumerate(statements):
        check = by_index.get(index)
        if not statement["citation_numbers"] or not check or check.get("supported") is not True:
            continue
        valid = [number for number in statement["citation_numbers"] if 1 <= number <= len(evidence)]
        if len(valid) != len(statement["citation_numbers"]):
            continue
        kept.append((statement["text"], valid))
        for number in valid:
            if number not in used_numbers:
                used_numbers.append(number)

    renumber = {old: new for new, old in enumerate(used_numbers, 1)}
    final_statements = [{"text": text, "citation_numbers": [renumber[n] for n in numbers]} for text, numbers in kept]
    lines = [f'{item["text"]} ' + " ".join(f'[{n}]' for n in item["citation_numbers"]) for item in final_statements]
    sources = []
    for old in used_numbers:
        item = evidence[old - 1]
        sources.append({
            "number": renumber[old], "type": item["source_type"], "title": item["title"],
            "snippet": item["text"][:300], "url": item["url"], "date": item["date"],
        })
    checked = len([statement for statement in statements if statement["citation_numbers"]])
    verification = {"checked": checked, "supported": len(kept), "removed": len(statements) - len(kept), "succeeded": bool(kept)}
    return "\n".join(lines), final_statements, sources, verification
