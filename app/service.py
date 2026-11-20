"""Business logic: analyse a letter, draft appeals, verify with the web, answer questions."""
import json
import logging
import time
from pathlib import Path

from . import db, deadlines, drafts, fallback
from .llm import llm
from .redact import redact
from .rules import keyword_rules, match_rules, rules_for_prompt
from .schemas import CATEGORY_LABELS, AnalysisOut, DraftOut

log = logging.getLogger("claimback.service")
PROMPTS = Path(__file__).parent / "prompts"


def _prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def _clean_analysis(a: dict) -> dict:
    cat = a.get("rejection_category")
    if cat not in CATEGORY_LABELS:
        cat = "other"
    try:
        conf = float(a.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    amt = a.get("claim_amount_inr")
    try:
        amt = int(amt) if amt not in (None, "") else None
    except (TypeError, ValueError):
        amt = None
    conf = max(0.0, min(1.0, conf))
    return {
        "insurer": a.get("insurer") or None,
        "claim_amount_inr": amt,
        "rejection_category": cat,
        "clause_cited": a.get("clause_cited") or None,
        "policy_cancelled_by_insurer": bool(a.get("policy_cancelled_by_insurer")),
        "plain_explanation": (a.get("plain_explanation") or "").strip() or fallback.EXPLAIN[cat]["en"],
        "missing_info": [str(x) for x in (a.get("missing_info") or [])][:8],
        "confidence": round(conf, 2),
        "needs_human_review": bool(a.get("needs_human_review")) or conf < 0.6 or cat == "other",
    }


def analyze(text: str, file_bytes: bytes = None, mime: str = None, lang: str = "en") -> dict:
    lang = "hi" if lang == "hi" else "en"
    redactions, shown_text = {}, ""
    notes = []
    if text:
        shown_text, redactions = redact(text)
    analysis, engine = None, "basic"

    if llm.available:
        try:
            system = _prompt("analyze.md") + (
                "\nWrite plain_explanation and missing_info in Hindi (Devanagari)." if lang == "hi" else "\nWrite in English."
            )
            parts = []
            if file_bytes:
                from google.genai import types

                parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))
                parts.append("Analyse the attached rejection letter.")
            else:
                parts.append("REJECTION LETTER:\n" + shown_text)
            analysis = _clean_analysis(llm.generate_json(system, parts, AnalysisOut))
            engine = "ai"
        except Exception as e:
            log.warning("AI analysis failed, using basic mode: %s", str(e)[:200])
            notes.append("The AI model was unavailable, so basic mode was used. Results may be less detailed.")

    if analysis is None:
        if not shown_text:
            raise ValueError("Reading photos and PDFs needs the AI model, which is unavailable right now. Please paste the letter text instead.")
        analysis = _clean_analysis(fallback.classify(shown_text, lang))

    rules = match_rules(analysis["rejection_category"], analysis["policy_cancelled_by_insurer"])
    case = {
        "id": db.new_id(),
        "created": time.time(),
        "status": "analysed",
        "lang": lang,
        "engine": engine,
        "model": llm.last_model if engine == "ai" else None,
        "notes": notes,
        "redactions": redactions,
        "letter_text": shown_text,  # redacted text only; uploaded files are never stored
        "analysis": analysis,
        "rule_ids": [r["id"] for r in rules],
        "details": {},
        "deadlines": [],
        "draft": None,
        "review": {"history": []},
        "chat": [],
        "verify": None,
    }
    db.save(case)
    return public(case)


def public(case: dict) -> dict:
    """What the browser sees: the case plus full rule objects."""
    from .rules import RULES

    by_id = {r["id"]: r for r in RULES}
    out = dict(case)
    out["rules"] = [by_id[i] for i in case.get("rule_ids", []) if i in by_id]
    out["category_label"] = CATEGORY_LABELS[case["analysis"]["rejection_category"]]
    out.pop("letter_text", None)
    return out


def set_deadlines(case: dict, rejection_date: str, grievance_date: str):
    case["details"]["rejection_date"] = rejection_date
    case["details"]["grievance_date"] = grievance_date
    case["deadlines"] = deadlines.compute(rejection_date, grievance_date)
    db.save(case)
    return case


def make_draft(case: dict, details: dict) -> dict:
    case["details"].update({k: v for k, v in details.items() if v})
    analysis = case["analysis"]
    rules = [r for r in match_rules(analysis["rejection_category"], analysis["policy_cancelled_by_insurer"])]
    draft, engine = None, "template"
    if llm.available:
        try:
            payload = (
                "CASE ANALYSIS:\n" + json.dumps(analysis, ensure_ascii=False)
                + "\n\nUSER DETAILS:\n" + json.dumps(case["details"], ensure_ascii=False)
                + "\n\nRULE LIBRARY:\n" + rules_for_prompt(rules)
            )
            out = llm.generate_json(_prompt("draft.md"), [payload], DraftOut)
            if out.get("grievance_body") and out.get("ombudsman_complaint"):
                draft = {
                    "grievance_subject": out.get("grievance_subject") or "Request for reconsideration of rejected claim",
                    "grievance_body": out["grievance_body"],
                    "ombudsman_complaint": out["ombudsman_complaint"],
                    "checklist": [str(x) for x in (out.get("checklist") or [])][:12],
                }
                engine = "ai"
        except Exception as e:
            log.warning("AI draft failed, using template: %s", str(e)[:200])
    if draft is None:
        draft = drafts.make(analysis, case["details"])
    draft["engine"] = engine
    case["draft"] = draft
    case["status"] = "pending_review"
    case["review"]["history"].append({"t": time.time(), "event": "Draft generated and sent for human review"})
    if case["details"].get("rejection_date") or case["details"].get("grievance_date"):
        case["deadlines"] = deadlines.compute(case["details"].get("rejection_date", ""), case["details"].get("grievance_date", ""))
    db.save(case)
    return case


def verify(case: dict) -> dict:
    a = case["analysis"]
    rules = match_rules(a["rejection_category"], a["policy_cancelled_by_insurer"])
    base_sources = [{"title": r["source_name"], "url": r["source_url"], "official": True} for r in rules if r["source_url"]]
    seen, lib = set(), []
    for s in base_sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            lib.append(s)
    result = {"mode": "library", "text": "", "sources": lib, "checked": time.time()}
    if llm.supports_search:
        try:
            q = (
                f"Insurer: {a.get('insurer') or 'unknown'}\nRejection category: {CATEGORY_LABELS[a['rejection_category']]}\n"
                f"Clause the insurer relies on: {a.get('clause_cited') or 'not stated'}\n"
                f"Policy cancelled by insurer: {a['policy_cancelled_by_insurer']}\n"
                f"Plain summary: {a['plain_explanation']}\n\nRules already in our library:\n{rules_for_prompt(rules)}"
            )
            text, srcs, used = llm.generate_text(_prompt("verify.md"), q, grounded=True)
            tagged = []
            for s in srcs:
                blob = (s["title"] + " " + s["url"]).lower()
                s["official"] = any(k in blob for k in (".gov.in", "nic.in", "cioins", "irdai", "policyholder.gov"))
                tagged.append(s)
            tagged.sort(key=lambda s: not s["official"])
            result.update(mode="web" if used else "ai-no-search", text=text, sources=tagged + lib)
        except Exception as e:
            log.warning("verify failed: %s", str(e)[:200])
            result["text"] = "Live web check is unavailable right now. These are the official sources behind the rules shown above."
    else:
        result["text"] = "Live web check needs an AI key. These are the official sources behind the rules shown above."
    case["verify"] = result
    db.save(case)
    return result


def chat(case: dict, question: str, lang: str = "en") -> dict:
    a = case["analysis"]
    rules = match_rules(a["rejection_category"], a["policy_cancelled_by_insurer"])
    answer, engine = None, "basic"
    if llm.available:
        try:
            history = "\n".join(f"Q: {m['q']}\nA: {m['a']}" for m in case["chat"][-4:])
            prompt = (
                f"CASE ANALYSIS:\n{json.dumps(a, ensure_ascii=False)}\n\nRULE LIBRARY:\n{rules_for_prompt(rules)}\n\n"
                f"EARLIER:\n{history}\n\nQUESTION: {question}"
            )
            answer, _, _ = llm.generate_text(_prompt("chat.md").replace("{lang}", "Hindi" if lang == "hi" else "English"), prompt)
            engine = "ai"
        except Exception as e:
            log.warning("chat failed: %s", str(e)[:200])
    if answer is None:
        hits = keyword_rules(question, rules, 2) or rules[:2]
        answer = "Basic mode (no AI). The most relevant points from our rule library:\n" + "\n".join(f"- {r['title']}: {r['text']}" for r in hits)
    case["chat"].append({"q": question, "a": answer, "engine": engine})
    db.save(case)
    return {"answer": answer, "engine": engine}
