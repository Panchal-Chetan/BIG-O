"""
Thin wrapper around the GROQ chat-completions API (OpenAI-compatible schema).
Uses plain `requests` to keep the dependency footprint small.
"""
import json
import os
import requests
import streamlit as st

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(RuntimeError):
    pass


def _get_setting(name: str) -> str:
    """Env var first (from .env / shell), falls back to st.secrets if present."""
    val = os.getenv(name, "")
    if val:
        return val
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def _api_key() -> str:
    key = _get_setting("GROQ_API_KEY")
    if not key or key == "your_groq_api_key_here":
        raise GroqError(
            "GROQ_API_KEY is not set. Add it to .env (see .env.example) "
            "or paste it in the sidebar."
        )
    return key


def chat_completion(messages: list[dict], temperature: float = 0.2,
                     json_mode: bool = False, max_tokens: int = 2048) -> str:
    """
    Calls GROQ's chat completions endpoint and returns the assistant's raw
    text content. Raises GroqError on any failure.
    """
    model = _get_setting("GROQ_MODEL") or "openai/gpt-oss-120b"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        raise GroqError(f"Could not reach GROQ API: {e}") from e

    if resp.status_code != 200:
        raise GroqError(f"GROQ API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise GroqError(f"Unexpected GROQ response shape: {data}") from e


def chat_completion_json(messages: list[dict], temperature: float = 0.2) -> dict:
    """Calls chat_completion in JSON mode and parses the result."""
    raw = chat_completion(messages, temperature=temperature, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some models occasionally wrap JSON in fences despite instructions - strip and retry.
        cleaned = raw.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        return json.loads(cleaned)
