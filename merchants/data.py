"""Where the merchants get their data: real public sources, with a last-good cache.

If a source is down we serve the last good response (or a built-in snapshot) and mark it
`cached: true`, so the demo never breaks AND nobody mistakes old data for live data.
"""
import threading
import xml.etree.ElementTree as ET

import requests

from agentguard import llm

TIMEOUT = 4
_last_good: dict = {}
_lock = threading.Lock()

SNAPSHOT = {  # only used if a source has NEVER answered since startup
    "fx": {"source": "built-in snapshot", "rates": {"EUR/USD": 1.1193, "USD/JPY": 156.8}},
    "crypto": {"source": "built-in snapshot", "prices": {"XRP/USD": 1.29, "BTC/USD": 80469.0}},
    "news": {"source": "built-in snapshot", "headlines": [
        {"title": "Markets steady as investors await central bank decisions"},
        {"title": "Oil prices fall amid demand concerns"},
        {"title": "Tech shares rally on strong earnings"}]},
}


def _get(url: str):
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "AgentGuard-demo"})
    r.raise_for_status()
    return r


def _with_cache(key: str, fetch):
    """Run `fetch`; on failure serve the last good value (or the snapshot) flagged cached."""
    try:
        data = fetch()
        with _lock:
            _last_good[key] = data
        return {**data, "cached": False}
    except Exception:
        with _lock:
            data = _last_good.get(key) or SNAPSHOT[key]
        return {**data, "cached": True}


def fx() -> dict:
    def fetch():  # Frankfurter = free ECB reference rates
        rates = _get("https://api.frankfurter.app/latest?from=USD&to=EUR,JPY").json()["rates"]
        return {"source": "api.frankfurter.app (ECB)",
                "rates": {"EUR/USD": round(1 / rates["EUR"], 5), "USD/JPY": rates["JPY"]}}
    return _with_cache("fx", fetch)


def crypto() -> dict:
    def fetch():  # CoinGecko public price API
        p = _get("https://api.coingecko.com/api/v3/simple/price?ids=ripple,bitcoin&vs_currencies=usd").json()
        return {"source": "api.coingecko.com",
                "prices": {"XRP/USD": p["ripple"]["usd"], "BTC/USD": p["bitcoin"]["usd"]}}
    return _with_cache("crypto", fetch)


RISK_WORDS = ["crash", "plunge", "fall", "falls", "slump", "recession", "fear", "war", "inflation", "default",
              "layoffs", "cuts", "tariff", "sanctions", "loss", "losses", "warning", "crisis", "tumble", "panic"]
GOOD_WORDS = ["rally", "rise", "rises", "surge", "growth", "gain", "gains", "record", "boost", "strong"]


def _news_headlines() -> dict:
    root = ET.fromstring(_get("https://feeds.bbci.co.uk/news/business/rss.xml").content)
    headlines = [{"title": i.findtext("title")} for i in root.iter("item")][:8]
    if not headlines:
        raise ValueError("empty feed")
    return {"source": "feeds.bbci.co.uk (BBC Business RSS)", "headlines": headlines}


def risk_score(headlines: list[dict]) -> dict:
    """0 = calm, 100 = very risky. Bedrock scores it if available, otherwise a keyword count (labelled)."""
    titles = [h["title"] for h in headlines]
    answer = llm.ask_json(
        "Rate the overall market-risk tone of these business headlines from 0 (calm) to 100 (very risky). "
        'Reply ONLY with JSON: {"risk_score": <int>, "summary": "<one sentence>"}\n' + "\n".join(titles),
        system="You are a cautious treasury risk analyst.")
    if answer and isinstance(answer.get("risk_score"), (int, float)):
        return {"risk_score": int(answer["risk_score"]), "summary": answer.get("summary", ""), "scored_by": "Bedrock LLM"}
    risky = sum(any(w in t.lower() for w in RISK_WORDS) for t in titles)
    good = sum(any(w in t.lower() for w in GOOD_WORDS) for t in titles)
    return {"risk_score": max(0, min(100, 30 + 20 * risky - 10 * good)), "summary": "",
            "scored_by": "keyword rules (LLM OFFLINE)"}


def news() -> dict:
    data = _with_cache("news", _news_headlines)
    return {**data, **risk_score(data["headlines"])}


def news_deep() -> dict:
    """The 'deeper data pull': more headlines, descriptions and a per-theme breakdown."""
    try:
        root = ET.fromstring(_get("https://feeds.bbci.co.uk/news/business/rss.xml").content)
        items = [{"title": i.findtext("title"), "summary": i.findtext("description")} for i in root.iter("item")][:20]
        cached = False
    except Exception:
        items, cached = [dict(h, summary="") for h in SNAPSHOT["news"]["headlines"]], True
    base = risk_score(items)
    themes = {w: sum(w in (i["title"] or "").lower() for i in items) for w in RISK_WORDS}
    return {"source": "feeds.bbci.co.uk (BBC Business RSS), extended", "cached": cached, "headlines": items,
            "risk_themes": {k: v for k, v in themes.items() if v}, **base}
