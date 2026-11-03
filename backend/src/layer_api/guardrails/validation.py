import re


INJECTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|your|system)\b.{0,20}\b(instructions?|rules|prompts?|messages?)\b",
    r"\b(reveal|show|print|repeat|leak)\b.{0,30}\b(system|hidden|developer)\s+(prompt|instructions?|message)\b",
    r"\bact as (an? )?(unrestricted|jailbroken)\b|\bdeveloper mode\b",
    r"</?\s*(system|untrusted_evidence)\s*>",
]
INJECTION = re.compile("|".join(f"(?:{pattern})" for pattern in INJECTION_PATTERNS), re.IGNORECASE | re.DOTALL)


def looks_like_injection(text: str) -> bool:
    return INJECTION.search(text) is not None
