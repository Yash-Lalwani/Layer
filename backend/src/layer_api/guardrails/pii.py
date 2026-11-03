import re


EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b")


def redact(text: str, own_email: str | None = None) -> str:
    """Redact third-party emails, card numbers, SSNs and phone numbers. The user's own email stays."""
    own = (own_email or "").lower()
    text = EMAIL.sub(lambda match: match.group() if match.group().lower() == own else "[email redacted]", text)
    text = CARD.sub("[card redacted]", text)
    text = SSN.sub("[SSN redacted]", text)
    return PHONE.sub("[phone redacted]", text)
