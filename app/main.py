import logging
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db, deadlines, service
from .llm import llm
from .rules import DEMO_CASES, RULES
from .schemas import ChatIn, Details, ReviewIn

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"
REVIEWER_PIN = os.getenv("REVIEWER_PIN", "claimback")
MAX_UPLOAD = 8 * 1024 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/webp", "application/pdf"}

app = FastAPI(title="ClaimBack", docs_url="/api/docs", redoc_url=None)

# ---- very small per-IP rate limit so the free AI quota is not burned by one visitor ----
_hits = defaultdict(list)
LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "40"))


def _limit(request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "x")).split(",")[0].strip()
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < 3600]
    if len(_hits[ip]) >= LIMIT:
        raise HTTPException(429, "Too many requests from this address. Please try again in a while.")
    _hits[ip].append(now)


def _case(case_id: str) -> dict:
    c = db.get(case_id)
    if not c:
        raise HTTPException(404, "Case not found. It may have been deleted or the server restarted.")
    return c


@app.get("/api/health")
def health():
    d = llm.describe()
    d["mode"] = "ai" if llm.available else "basic"
    d["rules"] = len(RULES)
    return d


@app.get("/api/demo")
def demo_list():
    return [{"id": c["id"], "title": c["title"], "text": c["text"]} for c in DEMO_CASES]


@app.post("/api/analyze")
async def analyze(
    request: Request,
    text: str = Form(""),
    lang: str = Form("en"),
    demo_id: str = Form(""),
    file: UploadFile = File(None),
):
    _limit(request)
    data, mime = None, None
    if demo_id:
        demo = next((c for c in DEMO_CASES if c["id"] == demo_id), None)
        if not demo:
            raise HTTPException(404, "Unknown demo case")
        text = demo["text"]
    elif file is not None and file.filename:
        mime = file.content_type
        if mime not in ALLOWED:
            raise HTTPException(400, "Please upload a PNG, JPG, WEBP image or a PDF.")
        data = await file.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(400, "File is larger than 8 MB.")
        if not llm.supports_files:
            raise HTTPException(400, "Reading photos and PDFs needs the AI model, which is not set up on this server. Please paste the letter text instead.")
        text = ""
    elif len(text.strip()) < 30:
        raise HTTPException(400, "Please paste the rejection letter text (at least a few sentences) or upload a file.")
    try:
        return service.analyze(text.strip(), data, mime, lang)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/case/{case_id}")
def get_case(case_id: str):
    return service.public(_case(case_id))


@app.delete("/api/case/{case_id}")
def delete_case(case_id: str):
    return {"deleted": db.delete(case_id)}


@app.post("/api/case/{case_id}/deadlines")
def set_deadlines(case_id: str, d: Details):
    c = service.set_deadlines(_case(case_id), d.rejection_date, d.grievance_date)
    return {"deadlines": c["deadlines"]}


@app.post("/api/case/{case_id}/draft")
def make_draft(request: Request, case_id: str, d: Details):
    _limit(request)
    c = service.make_draft(_case(case_id), d.model_dump())
    return service.public(c)


@app.post("/api/case/{case_id}/verify")
def verify(request: Request, case_id: str):
    _limit(request)
    return service.verify(_case(case_id))


@app.post("/api/case/{case_id}/chat")
def chat(request: Request, case_id: str, body: ChatIn):
    _limit(request)
    q = body.question.strip()
    if len(q) < 3:
        raise HTTPException(400, "Please type a question.")
    return service.chat(_case(case_id), q[:500], body.lang)


@app.get("/api/case/{case_id}/download", response_class=PlainTextResponse)
def download(case_id: str, kind: str = "grievance"):
    c = _case(case_id)
    if c["status"] != "approved" or not c.get("draft"):
        raise HTTPException(403, "Draft is not approved by the reviewer yet.")
    d = c["draft"]
    if kind == "ombudsman":
        body, name = d["ombudsman_complaint"], "ombudsman-complaint"
    elif kind == "checklist":
        body, name = "\n".join(f"[ ] {i}" for i in d["checklist"]), "document-checklist"
    else:
        body, name = d["grievance_body"], "grievance-email"
    return PlainTextResponse(body, headers={"Content-Disposition": f'attachment; filename="{name}.txt"'})


# ---------------- reviewer (human in the loop) ----------------
def _pin(pin):
    if pin != REVIEWER_PIN:
        raise HTTPException(401, "Wrong reviewer PIN")


@app.get("/api/reviewer/queue")
def queue(x_reviewer_pin: str = Header("")):
    _pin(x_reviewer_pin)
    return [
        {
            "id": c["id"],
            "created": c["created"],
            "category": service.CATEGORY_LABELS[c["analysis"]["rejection_category"]],
            "insurer": c["analysis"].get("insurer"),
            "confidence": c["analysis"]["confidence"],
            "flag": c["analysis"]["needs_human_review"],
        }
        for c in db.pending()
    ]


@app.get("/api/reviewer/{case_id}")
def reviewer_case(case_id: str, x_reviewer_pin: str = Header("")):
    _pin(x_reviewer_pin)
    c = service.public(_case(case_id))
    c["letter_text"] = _case(case_id).get("letter_text", "")
    return c


@app.post("/api/reviewer/{case_id}")
def review(case_id: str, body: ReviewIn, x_reviewer_pin: str = Header("")):
    _pin(x_reviewer_pin)
    c = _case(case_id)
    if not c.get("draft"):
        raise HTTPException(400, "No draft to review")
    if body.grievance_body is not None:
        c["draft"]["grievance_body"] = body.grievance_body
    if body.ombudsman_complaint is not None:
        c["draft"]["ombudsman_complaint"] = body.ombudsman_complaint
    c["status"] = "approved" if body.action == "approve" else "changes_requested"
    c["review"]["note"] = body.note
    c["review"]["history"].append(
        {"t": time.time(), "event": ("Approved by reviewer" if body.action == "approve" else "Reviewer asked for changes") + (f": {body.note}" if body.note else "")}
    )
    db.save(c)
    return {"status": c["status"]}


# ---------------- pages ----------------
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/reviewer")
def reviewer_page():
    return FileResponse(STATIC / "reviewer.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
