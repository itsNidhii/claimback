# ClaimBack

Understand a rejected Indian health-insurance claim, check it against official rules, and draft the appeal. A human reviewer approves every draft.

## What works with NO key, NO billing (basic mode)
Paste a letter -> keyword classifier -> rules + deadlines + template drafts + reviewer approval + download. Photos/PDF, live web check and AI drafting turn on when an AI backend is set.

## Run it (Antigravity terminal)
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests -q                              # 7 offline tests, no key needed
uvicorn app.main:app --reload --port 8080              # open http://localhost:8080
```

## Turn AI on (free, no billing account)
1. Make a key at https://aistudio.google.com/apikey
2. `export GEMINI_API_KEY=your_key`   (Windows PowerShell: `$env:GEMINI_API_KEY="your_key"`)
3. `python scripts/check_ai.py` -> should print the model it found and PASS lines with `engine=ai`
4. Restart uvicorn. The badge top-right shows "AI on: <model>".

The app finds a model by itself (cheapest Flash-Lite first, then others, including open Gemma) and tries the next one if a model fails or its quota is used up. Force one with `GEMINI_MODEL`.

## When you get Google Cloud credits
```
gcloud auth application-default login
export USE_VERTEX=1 GOOGLE_CLOUD_PROJECT=claimback-515215 GOOGLE_CLOUD_LOCATION=global
```
No code change. Use this for real user data, because the free Gemini tier may use content to improve Google products.

## Fully free and local (open model)
Install Ollama, `ollama pull gemma3`, then `export OLLAMA_URL=http://localhost:11434`. Text only (no photos/PDF, no web search).

## Deploy to Cloud Run
```
gcloud auth login
GEMINI_API_KEY=your_key REVIEWER_PIN=pick_a_pin ./deploy.sh
```
Cloud Run scales to zero, so it costs nothing when idle. It is pinned to 1 instance because cases are kept in a temporary SQLite file: they disappear on restart. That is fine for judging. Pre-warm the app by opening it a minute before a demo.

## Judging after credits expire
Free Gemini key stays valid, so the deployed app keeps working. If the free quota is used up, the app drops to basic mode instead of crashing, and the demo cases always work.

## Files
- `app/main.py` API and pages. `app/service.py` analyse, draft, verify, chat.
- `app/llm.py` model access, auto model discovery, fallbacks. `app/fallback.py` basic mode.
- `app/data/rules.json` rule library. Each rule has a source link and a Verified date. Edit with care: add only rules you can source.
- `app/data/demo_cases.json` 9 synthetic letters. `app/prompts/` all prompts.
- `app/static/` the website (plain HTML/CSS/JS, no build step).

## Honest limits
- Basic-mode classifier was written and tested on the 9 demo letters, so test it on new letters before trusting its accuracy.
- The AI path was written against the Google GenAI SDK and tested here with a mock model, not a live key. Run `scripts/check_ai.py` first.
- Rules marked "Check before relying" or "Practical tip" are not verified law.
- Reddit, LinkedIn and similar sites are not scraped (blocked by their terms and unreliable). The "Verify" button uses Google Search grounding instead and marks government sources.
- Guidance, not legal advice.
