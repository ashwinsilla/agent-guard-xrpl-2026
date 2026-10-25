"""Tiny Amazon Bedrock helper used by the news scorer and the checker AI.

If Bedrock can't be used (no AWS credentials, no BEDROCK_MODEL_ID, call fails) every function
returns None and the caller falls back to rules, clearly labelled "LLM OFFLINE".
The model ID comes from .env (BEDROCK_MODEL_ID); it is never hardcoded.
"""
import json
import re

from agentguard import config

_client = None
_status = {"online": None, "why": ""}


def model_id() -> str:
    return config.env("BEDROCK_MODEL_ID")


def available() -> bool:
    """True if we can plausibly call Bedrock (checked once; a failed call flips it off)."""
    global _client
    if _status["online"] is not None:
        return _status["online"]
    try:
        import boto3
        session = boto3.Session(region_name=config.env("AWS_REGION", "us-east-1"))
        if session.get_credentials() is None:
            raise RuntimeError("no AWS credentials found")
        if not model_id():
            raise RuntimeError("BEDROCK_MODEL_ID is not set")
        _client = session.client("bedrock-runtime")
        _status.update(online=True, why="")
    except Exception as exc:
        _status.update(online=False, why=str(exc))
    return _status["online"]


def offline_reason() -> str:
    available()
    return _status["why"]


def ask(prompt: str, system: str = "", max_tokens: int = 600) -> str | None:
    """One-shot question. Returns the model's text, or None if Bedrock is unavailable."""
    if not available():
        return None
    try:
        kwargs = {"modelId": model_id(), "messages": [{"role": "user", "content": [{"text": prompt}]}],
                  "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0}}
        if system:
            kwargs["system"] = [{"text": system}]
        out = _client.converse(**kwargs)
        return out["output"]["message"]["content"][0]["text"]
    except Exception as exc:
        _status.update(online=False, why=str(exc)[:200])
        return None


def ask_json(prompt: str, system: str = "") -> dict | None:
    """Like ask(), but parses the first {...} JSON object in the reply (None if absent)."""
    text = ask(prompt, system)
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
