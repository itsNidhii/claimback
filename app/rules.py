import json
from pathlib import Path

_DATA = Path(__file__).parent / "data"
RULES = json.loads((_DATA / "rules.json").read_text(encoding="utf-8"))
DEMO_CASES = json.loads((_DATA / "demo_cases.json").read_text(encoding="utf-8"))


def match_rules(category: str, cancelled: bool = False):
    """Rules that apply to this rejection category (plus the 'all' rules)."""
    out = []
    for r in RULES:
        cats = r["categories"]
        if "all" in cats or category in cats:
            out.append(r)
        elif cancelled and "policy_lapse_cancellation" in cats:
            out.append(r)
    # general rules last, specific first
    out.sort(key=lambda r: ("all" in r["categories"], r["type"] != "rule"))
    return out


def rules_for_prompt(rules):
    return "\n".join(f"- {r['title']}: {r['text']}" for r in rules)


def keyword_rules(question: str, rules=None, limit=3):
    """Offline helper for chat: rank rules by word overlap with the question."""
    rules = rules or RULES
    words = {w for w in question.lower().replace("?", " ").split() if len(w) > 3}
    scored = []
    for r in rules:
        blob = (r["title"] + " " + r["text"]).lower()
        s = sum(1 for w in words if w in blob)
        if s:
            scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]
