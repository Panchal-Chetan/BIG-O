# BigO Scope (Streamlit)

Single-process Streamlit rebuild of BigO Scope: paste code, get its Big-O time complexity
plotted on a chart, click any complexity class to have the code rewritten toward it, and
ask a built-in chatbot about the analysis - all in one `streamlit run app.py`.

This trades the two-service React/FastAPI build for speed of setup: one Python process,
one command to run, a plainer but fully functional UI.

## How it's powered

| Feature | Powered by |
|---|---|
| Complexity detection (class + reasoning + hotspot lines) | **GROQ LLM** (structural reasoning over the code) |
| NLP cross-check on the detection | **Hugging Face** zero-shot classification (`facebook/bart-large-mnli`) |
| Code rewrite toward a target complexity | **GROQ LLM** |
| Chat assistant | **GROQ LLM**, grounded in the session's code + analysis |

GROQ does the actual reasoning about loops/recursion - that needs a model that can "read"
code semantically. Hugging Face's zero-shot pipeline is a genuinely independent second
opinion, scored purely from the code's text against the same 8 labels, shown next to the
GROQ verdict so you can see whether they agree. It's optional and non-blocking: skip
`HF_API_KEY` and the app still works fully on GROQ alone.

## Setup

> **Windows + very new Python (3.13/3.14):** if `pip install` fails trying to *build*
> Pillow from source (a matplotlib dependency), it means pip couldn't find a
> prebuilt wheel for your Python version yet. `requirements.txt` uses `>=` rather
> than pinned versions so pip should pick a compatible release automatically - just
> make sure you're on an up-to-date pip (`python -m pip install --upgrade pip`) first.
> If it still fails, the reliable fix is installing Python 3.12 (widely supported by
> all these packages) and creating the venv with that instead.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `GROQ_API_KEY` - required. Free key at https://console.groq.com/keys
- `HF_API_KEY` - optional. Free key at https://huggingface.co/settings/tokens
- `GROQ_MODEL` - defaults to `openai/gpt-oss-120b`; swap for any current GROQ-hosted model
  (check https://console.groq.com/docs/models for the live list — GROQ deprecates and
  swaps out models fairly often, so if you get a 404 "model does not exist" error, that's
  almost always the cause: pick a currently-active model id from that page)

(You can also skip `.env` entirely and paste keys into the sidebar at runtime - handy for
a quick demo, but they won't persist between restarts.)

Run it:
```bash
streamlit run app.py
```

Opens at http://localhost:8501.

## Using it

1. Pick a language in the sidebar, paste code into the editor, click **▶ Analyze**.
2. The detected complexity badge, reasoning, and hotspot lines (the lines actually
   driving the complexity) appear underneath. The scope chart highlights the detected
   curve with a solid, brighter trace and an end-of-curve label.
   - If the code's true complexity is higher than anything in the fixed 8-class chart
     (e.g. `O(n^4)`), the badge still shows a valid bucketed class (rounded up, usually
     to `O(2^n)`), and a separate amber line shows the exact form, e.g.
     *"exact complexity is O(n^4) — rounded up to the nearest offered class, O(2^n)"*.
3. Under the chart, click **Set as target** on any of the 8 classes. The app calls GROQ
   to rewrite the code toward that target. **The rewrite appears in its own read-only
   code block below the source** (with a copy button) — your original editable source
   is never overwritten. The chart shows the target as a dashed trace. If the target
   genuinely isn't reachable for that problem, the model says so honestly in a warning
   instead of faking it. **✕ Clear rewrite** removes that block.
4. The **💬 Ask Assistant** bubble floats at the bottom-right of the screen. Click it to
   open a chat popup grounded in the actual original code, rewritten code, and both
   complexities, so answers reference what's really on screen.

## Notes

- The code editor uses `streamlit-ace` for syntax highlighting/line numbers if installed;
  if that import fails for any reason it silently falls back to a plain text area, so the
  app never breaks over it.
- `prompts.py` holds every system prompt sent to GROQ - tune wording/strictness there.
- The chart's input-size domain is capped at n = 12 (`complexity.py`) so factorial/
  exponential curves stay renderable on the same log-scaled axis as O(1) - a
  visualization choice, not a limitation of the analysis.
- No auth, no rate limiting, no persistence between sessions (chat history and analysis
  live in `st.session_state` only). Add these before putting it anywhere public, since
  every analyze/rewrite/chat action spends GROQ (and optionally HF) API quota.
