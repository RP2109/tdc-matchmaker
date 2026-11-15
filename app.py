"""The Date Crew: matchmaker pre-screener with a rejection-feedback loop (prototype)."""

import copy
import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

try:  # Streamlit Cloud secrets -> env
    if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

from feedback import classify, classify_keywords, gemini_available, suggest_rules, violated_stated  # noqa: E402
from matching import cm_to_ft, shortlist, stated_rules  # noqa: E402

DATA = Path(__file__).parent / "data"
st.set_page_config(page_title="TDC Matchmaker Assistant", layout="wide")


@st.cache_data
def load():
    clients = json.loads((DATA / "clients.json").read_text())
    candidates = json.loads((DATA / "candidates.json").read_text())
    history = json.loads((DATA / "history.json").read_text())
    return clients, candidates, history


CLIENTS, CANDIDATES, SEED_HISTORY = load()
CAND = {c["id"]: c for c in CANDIDATES}
CLIENT = {c["id"]: c for c in CLIENTS}


def reset_state():
    hist = copy.deepcopy(SEED_HISTORY)
    for h in hist:
        if h["outcome"] == "rejected":
            h["reasons"], h["engine"] = classify_keywords(h["feedback"]), "keyword (seed)"
    st.session_state.history = hist
    st.session_state.learned = {c["id"]: [] for c in CLIENTS}
    st.session_state.dismissed = {c["id"]: set() for c in CLIENTS}
    st.session_state.last = None


if "history" not in st.session_state:
    reset_state()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Matchmaker assistant")
    cid = st.selectbox("Client", [c["id"] for c in CLIENTS],
                       format_func=lambda i: f"{CLIENT[i]['name']} (Matchmaker {CLIENT[i]['matchmaker']})")
    st.divider()
    if gemini_available():
        st.success("Gemini connected")
    else:
        key = st.text_input("Gemini API key (optional)", type="password",
                            help="Without a key, a keyword classifier is used so the demo still works.")
        if key:
            os.environ["GEMINI_API_KEY"] = key
            st.rerun()
        st.info("Using keyword fallback classifier")
    if st.button("Reset demo"):
        reset_state()
        st.rerun()

client = CLIENT[cid]
learned = st.session_state.learned[cid]
history = st.session_state.history

tab1, tab2, tab3 = st.tabs(["Shortlist", "Rejection insights", "How it works"])

# ---------------- Tab 1: shortlist + feedback loop ----------------
with tab1:
    left, right = st.columns([1, 2.2])

    with left:
        st.subheader(client["name"])
        st.caption(f"{client['age']} · {client['city']} · {client['religion']} · Matchmaker {client['matchmaker']}")
        st.markdown("**Stated preferences (hard filters)**")
        for r in stated_rules(client):
            st.markdown(f"- {r['label']}")
        s = client["soft"]
        soft = []
        if s.get("min_education"): soft.append(f"Education ≥ {s['min_education']}")
        if s.get("professions"): soft.append("Profession: " + ", ".join(s["professions"]))
        if s.get("drinking_ok"): soft.append("Drinking: " + "/".join(s["drinking_ok"]))
        if s.get("min_income_lpa"): soft.append(f"Income ≥ ₹{s['min_income_lpa']}L")
        st.markdown("**Soft preferences (used for ranking)**")
        for x in soft:
            st.markdown(f"- {x}")

        st.markdown("**Learned from feedback**")
        if not learned:
            st.caption("None yet")
        for i, r in enumerate(learned):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"- {r['label']}")
            if c2.button("✕", key=f"rm{cid}{i}", help="Remove"):
                learned.pop(i)
                st.rerun()

        # Suggestions
        sugg = suggest_rules(client, history, CAND, learned, st.session_state.dismissed[cid])
        if sugg:
            st.markdown("---")
            st.markdown("### Suggested preference updates")
        for i, sg in enumerate(sugg):
            with st.container(border=True):
                st.markdown(f"**{sg['rule']['label']}**")
                st.caption(f"Based on {len(sg['evidence'])} rejections:")
                for e in sg["evidence"]:
                    st.caption(f"“{e}”")
                for c in sg["conflicts"]:
                    st.warning(f"Conflict: client previously **accepted** {c['name']} "
                               f"({c['age']}, {cm_to_ft(c['height_cm'])}, {c['profession']}), who fails this rule. "
                               "Their real preference may be softer. Confirm with the client before adding.")
                b1, b2 = st.columns(2)
                if b1.button("Confirm", key=f"ok{cid}{i}", type="primary"):
                    learned.append(sg["rule"])
                    st.rerun()
                if b2.button("Dismiss", key=f"no{cid}{i}"):
                    st.session_state.dismissed[cid].add(sg["rule"]["label"])
                    st.rerun()

    with right:
        if st.session_state.last:
            msg = st.session_state.last
            if msg.startswith("Accepted"):
                st.success(msg)
            else:
                st.info(msg)
            st.session_state.last = None

        seen = {h["candidate_id"] for h in history if h["client_id"] == cid}
        top, n_pass, blocked = shortlist(CANDIDATES, client, learned, seen, k=10)
        pool = sum(1 for c in CANDIDATES if c["gender"] != client["gender"] and c["id"] not in seen)
        m1, m2, m3 = st.columns(3)
        m1.metric("Candidates screened", pool)
        m2.metric("Blocked by filters", pool - n_pass)
        m3.metric("Eligible", n_pass)
        if blocked:
            with st.expander("Why profiles were blocked"):
                st.dataframe(pd.DataFrame(sorted(blocked.items(), key=lambda x: -x[1]), columns=["Rule failed", "Profiles"]),
                             hide_index=True, width="stretch")

        st.subheader(f"Top {len(top)} for {client['name'].split()[0]}")
        for c in top:
            with st.container(border=True):
                a, b = st.columns([3, 1])
                a.markdown(f"**{c['name']}** · {c['age']} · {c['city']} · {cm_to_ft(c['height_cm'])} · {c['religion']}")
                a.caption(f"{c['profession']} · {c['education']} · ₹{c['income_lpa']}L · diet: {c['diet']} · "
                          f"drinks: {c['drinking']} · kids: {c['wants_children']}")
                why = ("✓ " + ", ".join(c["plus"])) if c["plus"] else ""
                gap = ("  ✗ " + ", ".join(c["minus"])) if c["minus"] else ""
                a.caption(why + gap)
                b.metric("Match", f"{c['score']}%")
                with st.form(f"f{cid}{c['id']}", clear_on_submit=True, border=False):
                    fb = st.text_input("Client's feedback (if rejected)", key=f"t{cid}{c['id']}",
                                       placeholder="e.g. too short, and he smokes", label_visibility="collapsed")
                    x, y = st.columns(2)
                    acc = x.form_submit_button("Client accepted", width="stretch")
                    rej = y.form_submit_button("Client rejected", width="stretch")
                if acc:
                    history.append({"client_id": cid, "candidate_id": c["id"], "outcome": "accepted", "feedback": ""})
                    st.session_state.last = f"Accepted {c['name']}."
                    st.rerun()
                if rej:
                    text = fb.strip() or "No reason given"
                    with st.spinner("Classifying feedback..."):
                        reasons, engine = classify(text, c)
                    history.append({"client_id": cid, "candidate_id": c["id"], "outcome": "rejected",
                                    "feedback": text, "reasons": reasons, "engine": engine})
                    tags = "; ".join(f"{r['category']} → {r['attribute']} ({r['direction']})" for r in reasons)
                    st.session_state.last = f"Rejected {c['name']}. Structured as: {tags}  ·  via {engine}"
                    st.rerun()

# ---------------- Tab 2: insights over all rejections ----------------
with tab2:
    rej = [h for h in history if h["outcome"] == "rejected"]
    rows = []
    for h in rej:
        cl, c = CLIENT[h["client_id"]], CAND[h["candidate_id"]]
        broke = violated_stated(c, cl)
        rows.append({
            "Client": cl["name"], "Matchmaker": cl["matchmaker"], "Profile": c["name"], "Feedback": h["feedback"],
            "Categories": ", ".join(sorted({r["category"] for r in h["reasons"]})),
            "Attributes": ", ".join(sorted({r["attribute"] for r in h["reasons"] if r["attribute"] != "none"})) or "-",
            "Broke stated pref": "; ".join(broke) if broke else "",
            "Engine": h.get("engine", ""),
        })
    df = pd.DataFrame(rows)
    n_broke = int((df["Broke stated pref"] != "").sum()) if len(df) else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Rejections", len(df))
    k2.metric("Broke a stated preference", f"{n_broke} ({n_broke / max(len(df), 1):.0%})",
              help="Profiles that should never have been sent. The pre-screener blocks these.")
    k3.metric("Acceptance rate", f"{sum(h['outcome'] == 'accepted' for h in history) / max(len(history), 1):.0%}")

    cat_counts = Counter(r["category"] for h in rej for r in h["reasons"])
    st.markdown("**Rejection reasons (structured from free text)**")
    st.bar_chart(pd.Series(cat_counts).sort_values(ascending=False), horizontal=True)

    by_mm = df.groupby("Matchmaker").apply(lambda g: (g["Broke stated pref"] != "").mean(), include_groups=False)
    st.markdown("**Share of rejections that broke stated preferences, by matchmaker**")
    st.dataframe(by_mm.rename("Screening-miss rate").map("{:.0%}".format).to_frame(), width="content")

    st.markdown("**All rejections**")
    st.dataframe(df, hide_index=True, width="stretch")

    if gemini_available() and st.button("Re-classify all rejections with Gemini"):
        bar = st.progress(0.0)
        for i, h in enumerate(rej):
            h["reasons"], h["engine"] = classify(h["feedback"], CAND[h["candidate_id"]])
            bar.progress((i + 1) / len(rej))
        st.rerun()

# ---------------- Tab 3 ----------------
with tab3:
    st.markdown("""
**Problem:** 69% of shared profiles are rejected, and about a third of those rejections break preferences the client already gave.

**Step 1: Pre-screen.** Remove candidates who fail stated hard preferences and deal-breakers, then rank the rest on soft preferences.
The matchmaker picks from a top-10 shortlist instead of searching manually.

**Step 2: Learn from feedback.** Free-text rejections are classified (Gemini, structured JSON output) into a fixed set of
categories and profile attributes. When the same reason repeats for a client (2+ times), the app suggests a new filter.
Rejections that broke a stated preference are skipped, because they are screening misses, not new information.

**Human in the loop.** The matchmaker confirms or dismisses every suggestion. If the client previously accepted someone who
would fail the new rule, the app flags it, since some clients reject at first and later accept similar profiles.

**Try it:** pick *Priya Sharma* → see the height suggestion and the conflict → confirm it → watch the shortlist change.
Then reject a profile with your own text, e.g. *"he smokes and lives too far"*.
""")
