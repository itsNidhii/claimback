"""Strip obvious personal identifiers from pasted text before it goes to any AI model.

This is a safety net, not a guarantee. Names and addresses are NOT removed.
Photos and PDFs cannot be redacted here, so the UI warns the user.
"""
import re

_PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    ("aadhaar", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[ID NUMBER]"),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),
    (
        "policy_or_claim_no",
        re.compile(
            r"(?i)\b((?:policy|claim|member|card|uhid|tpa|ref(?:erence)?)\s*(?:no\.?|number|id|#)?\s*[:\-]?\s*)([A-Z0-9][A-Z0-9/\-]{3,})"
        ),
        r"\1[NUMBER]",
    ),
]


def redact(text: str):
    counts = {}
    out = text
    for name, pat, repl in _PATTERNS:
        out, n = pat.subn(repl, out)
        if n:
            counts[name] = n
    return out, counts
