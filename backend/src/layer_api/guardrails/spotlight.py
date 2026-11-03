import re


TAG = re.compile(r"<(/?)\s*untrusted_evidence", re.IGNORECASE)


def neutralize(text: str) -> str:
    """Stop source text from closing or reopening the untrusted wrapper."""
    return TAG.sub(r"&lt;\1untrusted_evidence", text)


def wrap_evidence(number: int, source_type: str, title: str, text: str) -> str:
    return (f"[source {number}] {source_type}\n<untrusted_evidence>\n"
            f"Title: {neutralize(title)}\n{neutralize(text)}\n</untrusted_evidence>")


def plain_evidence(number: int, source_type: str, title: str, text: str) -> str:
    return f"[source {number}] {source_type} — {title}\n{text}"
