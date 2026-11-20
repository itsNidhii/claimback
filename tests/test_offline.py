"""Offline tests: run with no AI key. Usage: python -m pytest -q  (or python tests/test_offline.py)"""
import json, os, sys
os.environ.setdefault("DB_PATH", "/tmp/claimback_test.db")
for k in ("GEMINI_API_KEY", "USE_VERTEX", "OLLAMA_URL"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from app.main import app
from app.rules import DEMO_CASES
from app.redact import redact
from app.deadlines import compute, add_months
from datetime import date

c = TestClient(app)


def test_health_basic_mode():
    h = c.get("/api/health").json()
    assert h["mode"] == "basic" and h["rules"] >= 10


def test_all_demo_cases_classified():
    for d in DEMO_CASES:
        r = c.post("/api/analyze", data={"demo_id": d["id"]})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["analysis"]["rejection_category"] == d["expected"], d["id"]
        assert j["rules"], "rules must be attached"
        if d.get("expect_cancelled"):
            assert j["analysis"]["policy_cancelled_by_insurer"]


def test_redaction():
    t, n = redact("Call 9876543210 or mail a.b@x.com. PAN ABCDE1234F. Policy No: HLT/2024/99881. Aadhaar 1234 5678 9012")
    assert "9876543210" not in t and "a.b@x.com" not in t and "ABCDE1234F" not in t and "99881" not in t and "5678" not in t
    assert {"phone", "email", "pan"} <= set(n)


def test_deadlines():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    items = compute("2026-03-01", "2026-03-10", today=date(2026, 3, 20))
    labels = [i["date"] for i in items if i["date"]]
    assert "2026-04-10" in labels and "2027-04-10" in labels


def test_full_flow_with_review():
    j = c.post("/api/analyze", data={"demo_id": "waiting_period"}).json()
    cid = j["id"]
    # input validation
    assert c.post("/api/analyze", data={"text": "short"}).status_code == 400
    # deadlines
    d = c.post(f"/api/case/{cid}/deadlines", json={"rejection_date": "2026-05-01", "grievance_date": "2026-05-10"}).json()
    assert len(d["deadlines"]) == 4
    # draft -> pending review, download locked
    j = c.post(f"/api/case/{cid}/draft", json={"name": "Asha Rao", "policy_no": "P-1", "claim_no": "C-9", "hospital": "City Hospital"}).json()
    assert j["status"] == "pending_review" and "Asha Rao" in j["draft"]["grievance_body"]
    assert c.get(f"/api/case/{cid}/download").status_code == 403
    # reviewer
    assert c.get("/api/reviewer/queue", headers={"X-Reviewer-Pin": "bad"}).status_code == 401
    q = c.get("/api/reviewer/queue", headers={"X-Reviewer-Pin": "claimback"}).json()
    assert any(x["id"] == cid for x in q)
    r = c.post(f"/api/reviewer/{cid}", headers={"X-Reviewer-Pin": "claimback"}, json={"action": "approve", "note": "ok"})
    assert r.json()["status"] == "approved"
    assert c.get(f"/api/case/{cid}/download?kind=ombudsman").status_code == 200
    # verify + chat in basic mode
    v = c.post(f"/api/case/{cid}/verify").json()
    assert v["sources"]
    a = c.post(f"/api/case/{cid}/chat", json={"question": "Is there a time limit to appeal?"}).json()
    assert "Ombudsman" in a["answer"] or "year" in a["answer"]
    # delete
    assert c.delete(f"/api/case/{cid}").json()["deleted"]
    assert c.get(f"/api/case/{cid}").status_code == 404


def test_upload_needs_ai():
    r = c.post("/api/analyze", files={"file": ("a.png", b"\x89PNG", "image/png")})
    assert r.status_code == 400 and "AI" in r.json()["detail"]


def test_pages():
    assert c.get("/").status_code == 200 and c.get("/reviewer").status_code == 200 and c.get("/static/app.js").status_code == 200


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
