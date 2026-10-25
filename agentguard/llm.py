"""Tiny Amazon Bedrock helper used by the news scorer and the checker AI.

If Bedrock can't be used (no AWS credentials, no BEDROCK_MODEL_ID, call fails) every function
returns None and the caller falls back to rules, clearly labelled "LLM OFFLINE".
The model ID comes from .env (BEDROCK_MODEL_ID); it is never hardcoded.
"""
import json
import re
import time

from agentguard import config

_client = None
_status = {"online": None, "why": "", "checked": 0.0}
RETRY_SECONDS = 300  # while Bedrock is unavailable, try again every 5 minutes (e.g. a new account being verified)


# If BEDROCK_MODEL_ID isn't enabled for the account, the first of these that answers is used.
FALLBACK_MODELS = ["us.anthropic.claude-haiku-4-5-20251001-v1:0", "us.amazon.nova-pro-v1:0"]
_active = {"model": ""}


def model_id() -> str:
    """The model actually in use (the configured one, or a working fallback)."""
    return _active["model"] or config.env("BEDROCK_MODEL_ID")


def available() -> bool:
    """True if Bedrock really answers. Checked with one tiny call, cached; re-checked every 5 min while offline,
    so the AI switches itself on as soon as AWS allows it (no restart needed)."""
    global _client
    if _status["online"] or (_status["online"] is False and time.time() - _status["checked"] < RETRY_SECONDS):
        return bool(_status["online"])
    _status["checked"] = time.time()
    try:
        import boto3
        session = boto3.Session(region_name=config.env("AWS_REGION", "us-east-1"))
        if session.get_credentials() is None:
            raise RuntimeError("no AWS credentials found")
        _client = session.client("bedrock-runtime")
        candidates = [m for m in [config.env("BEDROCK_MODEL_ID")] + FALLBACK_MODELS if m]
        last = None
        for candidate in candidates:  # a probe costs a fraction of a cent
            try:
                _client.converse(modelId=candidate, messages=[{"role": "user", "content": [{"text": "Reply: ok"}]}],
                                 inferenceConfig={"maxTokens": 5})
                _active["model"] = candidate
                break
            except Exception as exc:
                last = exc
        else:
            raise last or RuntimeError("BEDROCK_MODEL_ID is not set")
        _status.update(online=True, why="")
    except Exception as exc:
        why = str(exc)
        if "being verified" in why:
            why = "AWS account still being verified by Amazon (retrying every 5 min)"
        _status.update(online=False, why=why[:200])
    return bool(_status["online"])


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
        _status.update(online=False, why=str(exc)[:200], checked=time.time())
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
