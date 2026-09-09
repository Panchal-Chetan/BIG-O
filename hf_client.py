"""
Hugging Face NLP cross-check.

GROQ's LLM does the real structural reasoning about the code (it can trace
loops, recursion, etc). Hugging Face's zero-shot-classification pipeline
(facebook/bart-large-mnli) is used as an independent, cheap NLP signal that
scores the code's *textual* description against the 8 complexity labels.

It's deliberately a secondary/ensemble signal, not the primary detector -
zero-shot text classification can't actually execute reasoning about loop
nesting the way an LLM can, but it's a genuine, real use of a dedicated NLP
model alongside the LLM, and a useful sanity check.

If no HF key is configured, this degrades gracefully (returns None) so the
app still works end-to-end with GROQ alone.
"""
import os
import requests
import streamlit as st
from prompts import COMPLEXITY_CLASSES

HF_URL_TEMPLATE = "https://api-inference.huggingface.co/models/{model}"


def _get_setting(name: str) -> str:
    val = os.getenv(name, "")
    if val:
        return val
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def zero_shot_complexity(code: str) -> dict | None:
    api_key = _get_setting("HF_API_KEY")
    if not api_key or api_key == "your_huggingface_api_key_here":
        return None

    model = _get_setting("HF_ZERO_SHOT_MODEL") or "facebook/bart-large-mnli"
    url = HF_URL_TEMPLATE.format(model=model)

    # Truncate - zero-shot models have small context windows and we only need
    # a representative slice for this cross-check signal.
    snippet = code[:1500]

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "inputs": snippet,
                "parameters": {
                    "candidate_labels": COMPLEXITY_CLASSES,
                    "multi_label": False,
                },
            },
            timeout=30,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    if "labels" not in data or "scores" not in data:
        return None

    return {
        "top_label": data["labels"][0],
        "top_score": round(data["scores"][0], 3),
        "all_scores": {
            label: round(score, 3)
            for label, score in zip(data["labels"], data["scores"])
        },
    }
