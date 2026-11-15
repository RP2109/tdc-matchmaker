# The Date Crew: Matchmaker Pre-screener with Feedback Loop

Prototype for the Product Growth Assessment (Part 3).

**Problem:** 69% of shared profiles are rejected, and about 35% of those rejections break preferences the client had already given.

**What it does**
1. **Pre-screen.** Filters out candidates who fail a client's stated hard preferences and deal-breakers, then ranks the rest on soft preferences. The matchmaker gets a top-10 shortlist with reasons, so they don't have to search by hand.
2. **Structure feedback.** Free-text rejection feedback is classified by Gemini (structured JSON output) into fixed categories and profile attributes. If no key is set, a keyword classifier takes over so the demo always works.
3. **Learn.** When the same reason repeats for a client (2+ times), the app suggests a new filter. The matchmaker confirms or dismisses it. If the client previously accepted someone who would fail the new rule, the app flags the conflict.
4. **Insights.** Shows every rejection with its structured reasons, the share that broke stated preferences (screening misses), and that share broken down by matchmaker.

All data is mocked (`data/generate.py`, seeded).

## Run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...        # optional; GEMINI_MODELS sets the fallback order (default gemini-3.5-flash → 3.5-flash-lite → 3.8-flash)
streamlit run app.py
```

On Streamlit Cloud, add `GEMINI_API_KEY` under app secrets.

## Demo path
1. Select **Priya Sharma**. She has rejected three men for height but once accepted someone at 5'8". The app suggests `Height ≥ 175 cm` and flags the conflict.
2. Click **Confirm**. The shortlist drops the profiles that fail the new rule.
3. Reject any profile with your own words, e.g. *"he smokes and lives too far"*, and see the structured output.
4. Open **Rejection insights** to see the breakdown.

## Files
- `matching.py`: hard filters and weighted soft-preference ranking
- `feedback.py`: Gemini / keyword classifier and rule suggestions from repeated reasons
- `app.py`: Streamlit UI
- `data/`: mocked clients, candidates and 30-day share history
