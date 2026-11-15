"""Step 2: turn free-text rejection feedback into structured reasons, then suggest preference updates."""

import json
import os
import re

from matching import EDU_RANK, cm_to_ft, eval_rule, stated_rules

CATEGORIES = ["deal_breaker", "appearance", "age", "location", "education", "profession",
              "lifestyle", "family_values", "income", "timing_or_fatigue", "other"]
ATTRIBUTES = ["height_cm", "age", "city", "religion", "education", "profession", "smoking",
              "drinking", "diet", "wants_children", "income_lpa", "none"]
DIRECTIONS = ["too_low", "too_high", "mismatch", "none"]

# Tried in order; a busy (503) or retired (404) model falls through to the next one.
GEMINI_MODELS = os.environ.get("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.8-flash").split(",")

PROMPT = """You are helping a matchmaking team understand why a client rejected a profile.

Client feedback (free text): "{text}"

The rejected profile: {profile}

Return every distinct reason in the feedback. For each reason give:
- category: one of {categories}
- attribute: the profile field it is about, one of {attributes} ("none" if it is about looks, chemistry, timing, etc.)
- direction: "too_low" (e.g. too short, too young, earns too little), "too_high" (too old, too tall), "mismatch" (wrong value, e.g. smokes, wrong city), or "none"
- evidence: the exact words from the feedback that show this reason

Use "appearance" for looks, photos, chemistry, "didn't click" or "not my type".
Use "timing_or_fatigue" only when the client is busy, overwhelmed, or not ready right now; it is about the client, not the profile.
Only use what the feedback says. Do not guess reasons that are not there."""


# ---------- Gemini ----------

def _gemini_client():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return None
    from google import genai
    from google.genai import types
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=20000))


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def classify_gemini(text: str, profile: dict) -> list[dict]:
    from google.genai import types

    client = _gemini_client()
    schema = {
        "type": "OBJECT",
        "properties": {
            "reasons": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "category": {"type": "STRING", "enum": CATEGORIES},
                        "attribute": {"type": "STRING", "enum": ATTRIBUTES},
                        "direction": {"type": "STRING", "enum": DIRECTIONS},
                        "evidence": {"type": "STRING"},
                    },
                    "required": ["category", "attribute", "direction", "evidence"],
                },
            }
        },
        "required": ["reasons"],
    }
    visible = {k: profile[k] for k in ("age", "city", "religion", "height_cm", "education", "profession",
                                         "smoking", "drinking", "diet", "wants_children", "income_lpa")}
    last_err = None
    for model in GEMINI_MODELS:
        try:
            resp = client.models.generate_content(
                model=model.strip(),
                contents=PROMPT.format(text=text, profile=json.dumps(visible), categories=CATEGORIES, attributes=ATTRIBUTES),
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0),
            )
            return json.loads(resp.text)["reasons"] or [_other(text)], model.strip()
        except Exception as e:
            last_err = e
    raise last_err


# ---------- Keyword fallback (works offline / without a key) ----------

KEYWORD_RULES = [
    (r"\btoo tall\b", "appearance", "height_cm", "too_high"),
    (r"\bshort\b|\bheight\b", "appearance", "height_cm", "too_low"),
    (r"\bsmok|cigarette", "deal_breaker", "smoking", "mismatch"),
    (r"\bdrink|alcohol|party", "lifestyle", "drinking", "mismatch"),
    (r"non[- ]?veg|\bmeat\b|vegetarian|\bdiet\b", "lifestyle", "diet", "mismatch"),
    (r"\bkids\b|children|\bchild\b", "family_values", "wants_children", "mismatch"),
    (r"too young|younger|immature", "age", "age", "too_low"),
    (r"too old|\bolder\b|age gap", "age", "age", "too_high"),
    (r"relocat|\bfar\b|distance|another city|lives in|long[- ]distance", "location", "city", "mismatch"),
    (r"religio|\bfaith\b", "deal_breaker", "religion", "mismatch"),
    (r"educat|degree|qualified|post ?grad", "education", "education", "too_low"),
    (r"salary|income|earn|financially", "income", "income_lpa", "too_low"),
    (r"startup|business|\bjob\b|career|profession|stable", "profession", "profession", "mismatch"),
    (r"\blooks\b|attractive|not my type|chemistry|vibe|connection", "appearance", "none", "none"),
    (r"busy|not ready|later|travel|too many|overwhelm|break", "timing_or_fatigue", "none", "none"),
]


def _other(text):
    return {"category": "other", "attribute": "none", "direction": "none", "evidence": text}


def classify_keywords(text: str, profile: dict | None = None) -> list[dict]:
    t, out, seen = text.lower(), [], set()
    for pattern, cat, attr, direction in KEYWORD_RULES:
        m = re.search(pattern, t)
        key = attr if attr != "none" else cat
        if m and key not in seen:
            seen.add(key)
            out.append({"category": cat, "attribute": attr, "direction": direction, "evidence": m.group(0)})
    return out or [_other(text)]


def classify(text: str, profile: dict) -> tuple[list[dict], str]:
    """Returns (reasons, engine_used). Falls back to keywords if Gemini is missing or fails."""
    if gemini_available():
        try:
            reasons, model = classify_gemini(text, profile)
            return reasons, f"Gemini ({model})"
        except Exception as e:  # keep the demo alive
            return classify_keywords(text, profile), f"keyword fallback (Gemini error: {type(e).__name__})"
    return classify_keywords(text, profile), "keyword fallback (no GEMINI_API_KEY)"


# ---------- Learning: repeated reasons -> suggested preference rule ----------

def violated_stated(c: dict, client: dict) -> list[str]:
    return [r["label"] for r in stated_rules(client) if not eval_rule(c, r)]


def _build_rule(attr, direction, rejected, client):
    vals = [c[attr] if attr != "education" else c["education"] for c in rejected]
    if attr == "height_cm" and direction == "too_low":
        v = max(vals) + 1
        return {"attribute": "height_cm", "op": ">=", "value": v, "label": f"Height ≥ {v} cm ({cm_to_ft(v)})"}
    if attr == "age" and direction == "too_low":
        v = max(vals) + 1
        return {"attribute": "age", "op": ">=", "value": v, "label": f"Age ≥ {v}"}
    if attr == "age" and direction == "too_high":
        v = min(vals) - 1
        return {"attribute": "age", "op": "<=", "value": v, "label": f"Age ≤ {v}"}
    if attr == "income_lpa":
        v = max(vals) + 1
        return {"attribute": "income_lpa", "op": ">=", "value": v, "label": f"Income ≥ ₹{v}L"}
    if attr == "education":
        v = max(EDU_RANK.get(x, 1) for x in vals) + 1
        return {"attribute": "education_rank", "op": ">=", "value": v, "label": "Education: " + ("Master's or higher" if v == 2 else "PhD")}
    if attr == "smoking":
        return {"attribute": "smoking", "op": "==", "value": False, "label": "Non-smoker"}
    if attr in ("drinking", "diet", "city", "profession", "religion", "wants_children"):
        bad = sorted(set(vals), key=str)
        return {"attribute": attr, "op": "not_in", "value": bad, "label": f"Exclude {attr.replace('_', ' ')}: " + ", ".join(map(str, bad))}
    return None


def suggest_rules(client, history, cand_by_id, learned, dismissed, min_count=2):
    """Find reasons that repeat for this client and turn them into rule suggestions.

    Rejections that broke a stated preference are skipped: those are screening misses,
    not new information about the client.
    """
    groups = {}
    for h in history:
        if h["client_id"] != client["id"] or h["outcome"] != "rejected" or not h.get("reasons"):
            continue
        c = cand_by_id[h["candidate_id"]]
        if violated_stated(c, client):
            continue
        for r in h["reasons"]:
            if r["attribute"] == "none":
                continue
            groups.setdefault((r["attribute"], r["direction"]), []).append((h, c))

    existing = {(r["attribute"], r["op"]) for r in learned}
    accepted = [cand_by_id[h["candidate_id"]] for h in history if h["client_id"] == client["id"] and h["outcome"] == "accepted"]
    out = []
    for (attr, direction), items in groups.items():
        if len(items) < min_count:
            continue
        rule = _build_rule(attr, direction, [c for _, c in items], client)
        if not rule or (rule["attribute"], rule["op"]) in existing or rule["label"] in dismissed:
            continue
        rule["source"] = "learned"
        conflicts = [c for c in accepted if not eval_rule(c, rule)]
        out.append({"rule": rule, "evidence": [h["feedback"] for h, _ in items], "conflicts": conflicts})
    return out
