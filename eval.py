"""Run all test cases, print accuracy. Usage:
  pip install google-genai pydantic
  # Option A: AI Studio key     -> export GEMINI_API_KEY=...
  # Option B: Vertex AI (credits)-> export USE_VERTEX=1 GOOGLE_CLOUD_PROJECT=<id> (and gcloud auth application-default login)
  export MODEL=<model id from the AI Studio dropdown>
  python eval.py
"""
import json, os
from typing import List, Literal, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

Category = Literal["non_disclosure_preexisting","waiting_period","document_deficiency","exclusion",
                   "policy_lapse_cancellation","room_rent_deduction","not_medically_necessary","other"]

class Analysis(BaseModel):
    insurer: Optional[str]
    claim_amount_inr: Optional[int]
    rejection_category: Category
    clause_cited: Optional[str]
    policy_cancelled_by_insurer: bool
    plain_explanation: str
    missing_info: List[str]
    confidence: float
    needs_human_review: bool

def make_client():
    if os.getenv("USE_VERTEX") == "1":
        return genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"))
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def analyse(client, model, system_prompt, letter):
    r = client.models.generate_content(
        model=model, contents=letter,
        config=types.GenerateContentConfig(system_instruction=system_prompt,
            response_mime_type="application/json", response_schema=Analysis, temperature=0.1))
    return Analysis.model_validate_json(r.text)

if __name__ == "__main__":
    here = os.path.dirname(__file__)
    prompt = open(os.path.join(here, "prompt.md")).read()
    cases = json.load(open(os.path.join(here, "cases.json")))
    client, model = make_client(), os.environ["MODEL"]
    os.makedirs(os.path.join(here, "demo_cache"), exist_ok=True)
    ok = 0
    for c in cases:
        a = analyse(client, model, prompt, c["text"])
        hit = a.rejection_category == c["expected"]
        if "expect_cancelled" in c: hit = hit and a.policy_cancelled_by_insurer == c["expect_cancelled"]
        ok += hit
        print(("PASS" if hit else "FAIL"), c["id"], "->", a.rejection_category, f"(conf {a.confidence})")
        json.dump(a.model_dump(), open(os.path.join(here, "demo_cache", c["id"] + ".json"), "w"), indent=2)
    print(f"\nAccuracy: {ok}/{len(cases)}  (outputs saved in demo_cache/)")
