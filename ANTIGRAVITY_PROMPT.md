# Paste this into the Antigravity agent chat

You are working on ClaimBack, a FastAPI + plain HTML/JS web app that helps Indian policyholders understand a rejected health-insurance claim and draft an appeal. Read `README.md` first, then `app/main.py`, `app/service.py`, `app/llm.py`.

## Rules you must follow
1. Do not delete or weaken the basic-mode fallback (`app/fallback.py`, `app/drafts.py`). The app must work with no AI key.
2. Do not edit legal facts in `app/data/rules.json` unless you can cite an official source URL and set `checked` to today. Never invent rules, clause numbers, court cases or statistics.
3. Do not scrape Reddit, LinkedIn or any site. Web verification stays on Google Search grounding in `service.verify`.
4. Never write API keys or secrets into files. Read them from environment variables.
5. Keep every user-facing sentence plain and honest: guidance, not legal advice.
6. After each change run `python -m pytest tests -q` and fix what you broke.

## Tasks, in order
1. Create a venv, install `requirements.txt`, run the tests, start the app on port 8080 and open it in the browser pane. Confirm the demo cases work end to end (analyse, deadlines, draft, reviewer approve at /reviewer with PIN `claimback`, download).
2. Ask me for my `GEMINI_API_KEY`. Do not print it. Set it in the terminal session only, run `python scripts/check_ai.py`, and show me the output. If any case fails or `engine=basic` appears, read the log lines starting with `generate_json`, find the cause (wrong model id, unsupported config, quota) and fix it in `app/llm.py`. Report the model that worked.
3. Test image upload with a screenshot of one demo letter, and a PDF. Fix any bug.
4. Test Hindi mode (the हिन्दी button) with AI on. Check that explanations are in Devanagari and drafts remain in English.
5. Test "Verify with official sources" with AI on. Check that sources from irdai.gov.in, cioins.co.in or *.gov.in are marked Official.
6. Polish the UI where it looks rough on a 390px wide phone and a 1100px desktop. Keep the Google colours and Inter font. No new dependencies.
7. Only if everything above passes: run `./deploy.sh` (ask me for the values it needs), open the Cloud Run URL, and repeat the step 1 checks on the live site.

## Done means
Tests pass, `check_ai.py` shows 9/9 with `engine=ai` (or tell me which fail and why), live URL works, and you list anything you could not verify.
