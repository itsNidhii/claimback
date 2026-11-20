"""One place that talks to AI models. Backends (LLM_BACKEND=auto picks the first that is set up):
  vertex  : USE_VERTEX=1 + GOOGLE_CLOUD_PROJECT  (uses Google Cloud credits)
  gemini  : GEMINI_API_KEY from Google AI Studio (free tier, no billing account needed)
  ollama  : OLLAMA_URL (e.g. http://localhost:11434) running an open model such as Gemma, 100% free, text only
  none    : app runs in basic mode (keyword rules), still fully usable
Model names are discovered automatically (cheapest Flash-Lite first) unless GEMINI_MODEL is set.
Every call tries the next model if one fails (quota, not found, unsupported feature).
"""
import json
import logging
import os
import re

log = logging.getLogger("claimback.llm")
_BAD = re.compile(r"image|tts|audio|live|embed|robot|computer|imagen|veo|aqa|learnlm|native|vision|banana|omni", re.I)


def parse_json(text: str):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s : e + 1])
        raise


class LLM:
    def __init__(self):
        self.backend = "none"
        self.client = None
        self.last_model = None
        self._cands = None
        self.error = None
        want = os.getenv("LLM_BACKEND", "auto").lower()
        try:
            if want in ("auto", "vertex") and os.getenv("USE_VERTEX") == "1":
                from google import genai

                self.client = genai.Client(
                    vertexai=True,
                    project=os.environ["GOOGLE_CLOUD_PROJECT"],
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
                )
                self.backend = "vertex"
            elif want in ("auto", "gemini") and os.getenv("GEMINI_API_KEY"):
                from google import genai

                self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                self.backend = "gemini"
            elif want in ("auto", "ollama") and os.getenv("OLLAMA_URL"):
                self.backend = "ollama"
        except Exception as e:  # bad key format, missing project, etc.
            self.error = str(e)
            log.warning("LLM setup failed: %s", e)

    # ---------- info ----------
    @property
    def available(self) -> bool:
        return self.backend != "none"

    @property
    def supports_files(self) -> bool:
        return self.backend in ("gemini", "vertex")

    @property
    def supports_search(self) -> bool:
        return self.backend in ("gemini", "vertex")

    def candidates(self):
        if self._cands:
            return self._cands
        if self.backend == "ollama":
            self._cands = [os.getenv("OLLAMA_MODEL", "gemma3")]
            return self._cands
        env = os.getenv("GEMINI_MODEL")
        if env:
            self._cands = [m.strip() for m in env.split(",") if m.strip()]
            return self._cands
        names = []
        try:
            for m in self.client.models.list():
                n = (m.name or "").split("/")[-1]
                acts = getattr(m, "supported_actions", None) or []
                if acts and "generateContent" not in acts:
                    continue
                if not n or _BAD.search(n):
                    continue
                names.append(n)
        except Exception as e:
            log.warning("model discovery failed: %s", e)

        def tier(n):
            l = n.lower()
            if "flash-lite" in l:
                return 0
            if "flash" in l:
                return 1
            if "pro" in l:
                return 2
            if "gemma" in l:
                return 3
            return 4

        names = sorted(set(names), reverse=True)  # newest-looking names first
        names.sort(key=lambda n: (tier(n), any(k in n.lower() for k in ("preview", "exp"))))
        self._cands = names[:4] or ["gemini-2.5-flash-lite", "gemini-2.5-flash"]
        return self._cands

    def describe(self):
        return {
            "backend": self.backend,
            "model": self.last_model or (self.candidates()[0] if self.available else None),
            "files": self.supports_files,
            "search": self.supports_search,
        }

    # ---------- calls ----------
    def _gemini_call(self, model, system, parts, json_schema=None, grounded=False, plain=False):
        from google.genai import types

        if plain:
            # some open models (Gemma) reject system instructions or JSON mode: put everything in the prompt
            head = system
            if json_schema is not None:
                head += "\n\nReturn ONLY valid JSON (no markdown) matching this JSON schema:\n" + json.dumps(json_schema.model_json_schema())
            contents = [head] + parts
            cfg = types.GenerateContentConfig(temperature=0.1)
        else:
            contents = parts
            kw = dict(system_instruction=system, temperature=0.1)
            if json_schema is not None:
                kw.update(response_mime_type="application/json", response_schema=json_schema)
            if grounded:
                kw["tools"] = [types.Tool(google_search=types.GoogleSearch())]
                kw.pop("temperature")
            cfg = types.GenerateContentConfig(**kw)
        return self.client.models.generate_content(model=model, contents=contents, config=cfg)

    @staticmethod
    def _sources(resp):
        out = []
        try:
            gm = resp.candidates[0].grounding_metadata
            for ch in (gm.grounding_chunks or []):
                if ch.web:
                    out.append({"title": ch.web.title or ch.web.domain or "source", "url": ch.web.uri})
        except Exception:
            pass
        seen, uniq = set(), []
        for s in out:
            if s["url"] not in seen:
                seen.add(s["url"])
                uniq.append(s)
        return uniq

    def _ollama(self, system, prompt, as_json):
        import httpx

        body = {
            "model": self.candidates()[0],
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        if as_json:
            body["format"] = "json"
        r = httpx.post(os.environ["OLLAMA_URL"].rstrip("/") + "/api/chat", json=body, timeout=180)
        r.raise_for_status()
        self.last_model = body["model"]
        return r.json()["message"]["content"]

    def generate_json(self, system, parts, schema):
        """parts: list of str / google.genai types.Part. Returns a dict."""
        if self.backend == "ollama":
            text_parts = [p for p in parts if isinstance(p, str)]
            hint = "\n\nReturn ONLY JSON matching: " + json.dumps(schema.model_json_schema())
            return parse_json(self._ollama(system + hint, "\n\n".join(text_parts), True))
        last = None
        for model in self.candidates():
            for plain in (False, True):
                try:
                    resp = self._gemini_call(model, system, parts, json_schema=schema, plain=plain)
                    data = parse_json(resp.text)
                    self.last_model = model
                    return data
                except Exception as e:
                    last = e
                    log.warning("generate_json %s plain=%s failed: %s", model, plain, str(e)[:200])
        raise RuntimeError(f"all models failed: {last}")

    def generate_text(self, system, prompt, grounded=False):
        """Returns (text, sources, grounded_used)."""
        if self.backend == "ollama":
            return self._ollama(system, prompt, False), [], False
        last = None
        modes = ([True, False] if grounded else [False])
        for g in modes:
            for model in self.candidates():
                for plain in (False, True):
                    try:
                        resp = self._gemini_call(model, system, [prompt], grounded=g, plain=plain)
                        if not resp.text:
                            raise RuntimeError("empty response")
                        self.last_model = model
                        return resp.text, (self._sources(resp) if g else []), g
                    except Exception as e:
                        last = e
                        log.warning("generate_text %s grounded=%s plain=%s failed: %s", model, g, plain, str(e)[:200])
        raise RuntimeError(f"all models failed: {last}")


llm = LLM()
