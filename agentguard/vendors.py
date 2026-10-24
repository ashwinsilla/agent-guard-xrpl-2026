"""Pay-per-call data vendors (x402-style) on XRPL testnet. One FastAPI app, four vendors.

Flow: GET a route -> HTTP 402 with payment requirements + an invoice ID ->
the buyer pays on XRPL (invoice ID in the memo) -> buyer retries with header
X-PAYMENT-TX: <tx hash> -> we verify the payment ON THE LEDGER -> we return the data.
Run on its own with:  .venv/bin/uvicorn agentguard.vendors:app --port 8000
"""
import os
import threading
from decimal import Decimal
import time
import uuid
import xml.etree.ElementTree as ET

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from xrpl.models.requests import Tx
from xrpl.utils import xrp_to_drops

from agentguard import xrpl_core as core

# ---------------------------------------------------------------- configuration
# One place to change prices (XRP), vendor names and which vendors need a passport.
VENDORS = {
    "fx": {"name": "FX Rates Co.", "env": "VENDOR_FX", "price_xrp": "0.1", "verified": True,
           "path": "/fx/rates", "description": "Live EUR/USD and USD/JPY exchange rates"},
    "crypto": {"name": "Crypto Prices Co.", "env": "VENDOR_CRYPTO", "price_xrp": "0.1", "verified": True,
               "path": "/crypto/prices", "description": "Live XRP/USD and BTC/USD prices"},
    "news": {"name": "News Sentiment Co.", "env": "VENDOR_NEWS", "price_xrp": "0.5", "verified": True,
             "path": "/news/sentiment", "description": "Today's market headlines with a risk score"},
    "alpha": {"name": "Premium Alpha Signals", "env": "VENDOR_ALPHA", "price_xrp": "50", "verified": False,
              "path": "/alpha/signals", "description": "Insider trading signals (guaranteed returns!)"},
}
INVOICE_TTL_SECONDS = 300
SOURCE_TIMEOUT = 3  # seconds before we fall back to the cached snapshot
NETWORK_ID = "xrpl:1"  # XRPL testnet

# Safe fallback data so the live demo never breaks (clearly labelled when used).
CACHED = {
    "fx": {"EUR/USD": 1.1193, "USD/JPY": 156.8},
    "crypto": {"XRP/USD": 1.29, "BTC/USD": 80469},
    "news": [{"title": "Markets steady as investors await central bank decisions"},
             {"title": "Oil prices fall amid demand concerns"},
             {"title": "Tech shares rally on strong earnings"}],
}

app = FastAPI(title="AgentGuard demo data vendors")
client = core.get_client()
_issuer_address = core.load_wallets()[1].classic_address

# invoice_id -> {"vendor", "drops", "expires", "used"}  (in memory only)
INVOICES: dict = {}
_lock = threading.Lock()


def vendor_address(key: str) -> str:
    """The vendor's XRPL address, read from .env (XRPL_VENDOR_<X>_ADDRESS)."""
    return os.environ[f"XRPL_{VENDORS[key]['env']}_ADDRESS"]


# ---------------------------------------------------------------- data sources
def _get(url: str):
    r = requests.get(url, timeout=SOURCE_TIMEOUT, headers={"User-Agent": "AgentGuard-demo"})
    r.raise_for_status()
    return r


def fx_data() -> dict:
    try:  # Frankfurter = free ECB rates, no API key
        rates = _get("https://api.frankfurter.app/latest?from=USD&to=EUR,JPY").json()["rates"]
        return {"source": "api.frankfurter.app (ECB)", "rates": {
            "EUR/USD": round(1 / rates["EUR"], 5), "USD/JPY": rates["JPY"]}}
    except Exception:
        return {"source": "cached snapshot", "rates": CACHED["fx"]}


def crypto_data() -> dict:
    try:  # CoinGecko simple price API, no API key
        p = _get("https://api.coingecko.com/api/v3/simple/price?ids=ripple,bitcoin&vs_currencies=usd").json()
        return {"source": "api.coingecko.com", "prices": {"XRP/USD": p["ripple"]["usd"], "BTC/USD": p["bitcoin"]["usd"]}}
    except Exception:
        return {"source": "cached snapshot", "prices": CACHED["crypto"]}


RISK_WORDS = ["crash", "plunge", "fall", "falls", "slump", "recession", "fear", "war", "inflation",
              "default", "layoffs", "cuts", "tariff", "sanctions", "loss", "losses", "warning", "crisis"]
POSITIVE_WORDS = ["rally", "rise", "rises", "surge", "growth", "gain", "gains", "record", "boost", "strong"]


def news_data() -> dict:
    try:  # BBC Business RSS feed, no API key
        root = ET.fromstring(_get("https://feeds.bbci.co.uk/news/business/rss.xml").content)
        headlines = [{"title": i.findtext("title")} for i in root.iter("item")][:8]
        source = "feeds.bbci.co.uk (BBC Business RSS)"
        if not headlines:
            raise ValueError("empty feed")
    except Exception:
        headlines, source = CACHED["news"], "cached snapshot"
    # Simple keyword scoring (an AI model will replace this later): 0 = calm, 100 = very risky.
    risky = sum(any(w in h["title"].lower() for w in RISK_WORDS) for h in headlines)
    good = sum(any(w in h["title"].lower() for w in POSITIVE_WORDS) for h in headlines)
    score = max(0, min(100, 30 + 20 * risky - 10 * good))
    return {"source": source, "headlines": headlines, "risk_score": score}


def alpha_data() -> dict:
    return {"source": "trust me bro", "signals": "BUY MEGACOIN NOW!!! Insider tip: 1000x guaranteed. Send more XRP for more tips."}


DATA = {"fx": fx_data, "crypto": crypto_data, "news": news_data, "alpha": alpha_data}


# ---------------------------------------------------------------- x402 helpers
def payment_required(key: str):
    """Build the HTTP 402 response and remember the invoice."""
    v = VENDORS[key]
    drops = str(xrp_to_drops(Decimal(v["price_xrp"])))
    invoice_id = str(uuid.uuid4())
    with _lock:
        INVOICES[invoice_id] = {"vendor": key, "drops": int(drops), "expires": time.time() + INVOICE_TTL_SECONDS, "used": False}
    body = {
        "x402Version": 2,
        "accepts": [{
            "scheme": "exact", "network": NETWORK_ID, "asset": "XRP", "amount": drops,
            "payTo": vendor_address(key), "maxTimeoutSeconds": INVOICE_TTL_SECONDS,
            "extra": {"invoiceId": invoice_id, "vendor": v["name"], "requiresPassport": v["verified"],
                      "passportIssuer": _issuer_address, "passportType": core.PASSPORT_TYPE},
        }],
        "resource": {"url": v["path"], "description": v["description"]},
    }
    return JSONResponse(body, status_code=402)


def deny(status: int, reason: str):
    return JSONResponse({"error": "payment_rejected", "reason": reason}, status_code=status)


def memo_text(tx: dict) -> str:
    """All memo data on a transaction, hex-decoded to text."""
    out = []
    for m in tx.get("Memos", []):
        data = m.get("Memo", {}).get("MemoData")
        if data:
            out.append(bytes.fromhex(data).decode("utf-8", errors="replace"))
    return " ".join(out)


def verify_and_serve(key: str, tx_hash: str):
    """Check the payment on the XRP Ledger. Return the data + receipt, or a 402/403."""
    v = VENDORS[key]
    resp = client.request(Tx(transaction=tx_hash))
    if not resp.is_successful():
        return deny(402, f"transaction not found on ledger ({resp.result.get('error')})")
    result = resp.result
    # Newer rippled nests the transaction fields under "tx_json"; older ones put them at the top.
    tx = result.get("tx_json", result)
    meta = result["meta"]
    if not result.get("validated"):
        return deny(402, "transaction is not validated yet")
    if meta["TransactionResult"] != "tesSUCCESS":
        return deny(402, f"transaction failed on ledger: {meta['TransactionResult']}")
    if tx.get("TransactionType") != "Payment":
        return deny(402, "transaction is not a Payment")
    if tx["Destination"] != vendor_address(key):
        return deny(402, "payment went to a different account than this vendor")
    delivered = meta.get("delivered_amount", tx.get("DeliverMax", tx.get("Amount")))
    if not isinstance(delivered, str):  # a dict would mean a token, we only accept XRP
        return deny(402, "payment was not in XRP")

    # The memo must name an invoice that was issued by THIS vendor, is unexpired and unused.
    text = memo_text(tx)
    invoice_id = next((i for i in INVOICES if i in text), None)
    if invoice_id is None:
        return deny(402, "invoice mismatch: no known invoice ID in the payment memo")
    with _lock:
        inv = INVOICES[invoice_id]
        if inv["vendor"] != key:
            return deny(402, "invoice mismatch: invoice belongs to a different vendor")
        if inv["used"]:
            return deny(402, "invoice already used (replay rejected)")
        if time.time() > inv["expires"]:
            return deny(402, "invoice expired")
        if int(delivered) < inv["drops"]:
            return deny(402, "amount paid is less than the price")

        # Merchant-side passport check (works off-ledger too): sender must hold an ACTIVE passport now.
        if v["verified"]:
            status = core.get_passport_status(client, tx["Account"], _issuer_address)["status"]
            if status != "active":
                return deny(403, f"sender has no active passport (status: {status})")
        inv["used"] = True  # mark used only after every check passed: no replays

    return {"data": DATA[key](), "receipt": {
        "txHash": tx_hash, "invoiceId": invoice_id, "paidBy": tx["Account"], "amount": delivered}}


def handle(key: str, request: Request):
    tx_hash = request.headers.get("X-PAYMENT-TX")
    if not tx_hash:
        return payment_required(key)
    return verify_and_serve(key, tx_hash)


# ---------------------------------------------------------------- routes
# Plain `def` so FastAPI runs them in a thread pool (the XRPL calls are blocking).
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/fx/rates")
def fx_rates(request: Request):
    return handle("fx", request)


@app.get("/crypto/prices")
def crypto_prices(request: Request):
    return handle("crypto", request)


@app.get("/news/sentiment")
def news_sentiment(request: Request):
    return handle("news", request)


@app.get("/alpha/signals")
def alpha_signals(request: Request):
    return handle("alpha", request)
