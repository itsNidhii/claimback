"""Run the 9 demo letters through the REAL AI path and report accuracy.
  export GEMINI_API_KEY=...            (free key from aistudio.google.com)   -- or USE_VERTEX=1 GOOGLE_CLOUD_PROJECT=...
  python scripts/check_ai.py
Optional: GEMINI_MODEL=<id> to force a model. Without a key it tests basic mode."""
import os, sys
os.environ.setdefault("DB_PATH", "/tmp/claimback_check.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import service
from app.llm import llm
from app.rules import DEMO_CASES

print("backend:", llm.backend, "| candidate models:", llm.candidates() if llm.available else "-")
ok = 0
for d in DEMO_CASES:
    r = service.analyze(d["text"])
    a = r["analysis"]
    hit = a["rejection_category"] == d["expected"] and (a["policy_cancelled_by_insurer"] == d["expect_cancelled"] if "expect_cancelled" in d else True)
    ok += hit
    print("PASS" if hit else "FAIL", f"{d['id']:<26}", a["rejection_category"], f"conf={a['confidence']}", "engine=" + r["engine"], r.get("model") or "")
print(f"\nAccuracy: {ok}/{len(DEMO_CASES)}")
print("engine=basic with a key set means the AI call failed. Start the app and read the log lines starting with generate_json for the reason.")
