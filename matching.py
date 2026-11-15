"""Step 1: pre-screen candidates against a client's preferences, then rank the ones that pass."""

EDU_RANK = {"Bachelor's": 1, "Master's": 2, "MBA": 2, "CA": 2, "MBBS": 2, "LLB": 1, "PhD": 3}

SOFT_WEIGHTS = {"education": 1.5, "profession": 1.0, "drinking": 1.0, "income": 1.0, "height": 1.0, "age": 0.5}


def cm_to_ft(cm: int) -> str:
    inches = round(cm / 2.54)
    return f"{inches // 12}'{inches % 12}\""


def _get(c: dict, attribute: str):
    if attribute == "education_rank":
        return EDU_RANK.get(c["education"], 1)
    return c[attribute]


def eval_rule(c: dict, rule: dict) -> bool:
    """True if candidate c passes the rule."""
    v, op, target = _get(c, rule["attribute"]), rule["op"], rule["value"]
    if op == ">=":
        return v >= target
    if op == "<=":
        return v <= target
    if op == "==":
        return v == target
    if op == "in":
        return v in target
    if op == "not_in":
        return v not in target
    raise ValueError(op)


def stated_rules(client: dict) -> list[dict]:
    """Turn the client's stated hard preferences / deal-breakers into rules."""
    h = client["hard"]
    rules = [
        {"attribute": "age", "op": ">=", "value": h["age_min"], "label": f"Age ≥ {h['age_min']}"},
        {"attribute": "age", "op": "<=", "value": h["age_max"], "label": f"Age ≤ {h['age_max']}"},
    ]
    if h.get("religions"):
        rules.append({"attribute": "religion", "op": "in", "value": h["religions"], "label": "Religion: " + "/".join(h["religions"])})
    if h.get("cities"):
        rules.append({"attribute": "city", "op": "in", "value": h["cities"], "label": "City: " + "/".join(h["cities"])})
    if h.get("no_smoking"):
        rules.append({"attribute": "smoking", "op": "==", "value": False, "label": "Non-smoker (deal-breaker)"})
    if h.get("diet"):
        rules.append({"attribute": "diet", "op": "in", "value": h["diet"], "label": "Diet: " + "/".join(h["diet"])})
    if h.get("wants_children") == "yes":
        rules.append({"attribute": "wants_children", "op": "in", "value": ["yes", "open"], "label": "Wants children (deal-breaker)"})
    for r in rules:
        r["source"] = "stated"
    return rules


def check(c: dict, client: dict, learned: list[dict] | None = None) -> list[dict]:
    """Return the rules this candidate fails (empty list = passes)."""
    if c["gender"] == client["gender"]:
        return [{"label": "Same gender", "source": "stated"}]
    rules = stated_rules(client) + (learned or [])
    return [r for r in rules if not eval_rule(c, r)]


def score(c: dict, client: dict) -> tuple[int, list[str], list[str]]:
    """Weighted soft-preference match, 0-100, with plain-language strengths and gaps."""
    s, h = client["soft"], client["hard"]
    parts, plus, minus = {}, [], []

    if s.get("min_education"):
        ok = EDU_RANK.get(c["education"], 1) >= EDU_RANK[s["min_education"]]
        parts["education"] = 1.0 if ok else 0.3
        (plus if ok else minus).append(c["education"])
    if s.get("professions"):
        ok = c["profession"] in s["professions"]
        parts["profession"] = 1.0 if ok else 0.4
        (plus if ok else minus).append(c["profession"])
    if s.get("drinking_ok"):
        ok = c["drinking"] in s["drinking_ok"]
        parts["drinking"] = 1.0 if ok else 0.0
        if not ok:
            minus.append(f"drinks {c['drinking']}")
    if s.get("min_income_lpa"):
        ratio = min(1.0, c["income_lpa"] / s["min_income_lpa"])
        parts["income"] = ratio
        (plus if ratio >= 1 else minus).append(f"₹{c['income_lpa']}L")
    if s.get("min_height_cm"):
        gap = s["min_height_cm"] - c["height_cm"]
        parts["height"] = 1.0 if gap <= 0 else max(0.0, 1 - gap / 10)
        (plus if gap <= 0 else minus).append(cm_to_ft(c["height_cm"]))
    mid, half = (h["age_min"] + h["age_max"]) / 2, (h["age_max"] - h["age_min"]) / 2 + 1
    parts["age"] = max(0.0, 1 - 0.5 * abs(c["age"] - mid) / half)

    total_w = sum(SOFT_WEIGHTS[k] for k in parts)
    pct = round(100 * sum(SOFT_WEIGHTS[k] * v for k, v in parts.items()) / total_w)
    return pct, plus, minus


def shortlist(candidates: list[dict], client: dict, learned: list[dict], exclude_ids: set, k: int = 10):
    """Hard-filter, rank, return (top_k, filtered_out_counts_by_rule)."""
    passed, blocked = [], {}
    for c in candidates:
        if c["id"] in exclude_ids:
            continue
        fails = check(c, client, learned)
        if c["gender"] == client["gender"]:
            continue
        if fails:
            for f in fails:
                key = f["label"] + (" (learned)" if f.get("source") == "learned" else "")
                blocked[key] = blocked.get(key, 0) + 1
            continue
        pct, plus, minus = score(c, client)
        passed.append({**c, "score": pct, "plus": plus, "minus": minus})
    passed.sort(key=lambda x: -x["score"])
    return passed[:k], len(passed), blocked
