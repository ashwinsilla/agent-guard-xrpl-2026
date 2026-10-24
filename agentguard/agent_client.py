"""The treasury agent's purchase client (x402-style).

buy(): GET -> 402 -> ask the approver -> pay on XRPL with passport + memo -> retry with the tx hash.
The payment step is the function `pay_invoice`, kept separate so Mastercard AP4M can replace it later.
"""
import json

import requests
from xrpl.utils import drops_to_xrp

from agentguard import xrpl_core as core

TX_LINK = "https://testnet.xrpl.org/transactions/"
ACCT_LINK = "https://testnet.xrpl.org/accounts/"


def simple_policy(purchase: dict) -> bool:
    """TEMPORARY placeholder for the AI checker (Layer 2b): block anything over 1 XRP."""
    return float(purchase["price_xrp"]) <= 1


def pay_invoice(agent, requirement: dict, reason: str, issuer_address: str) -> dict:
    """Swappable payment step. Today: XRP on XRPL with the passport attached.

    Returns {"code", "hash"}. A later layer can provide an AP4M version with the same shape.
    """
    price_xrp = drops_to_xrp(requirement["amount"])
    passport_id = core.get_passport_id(core.get_client(), agent.classic_address, issuer_address)
    memo = json.dumps({"invoiceId": requirement["extra"]["invoiceId"], "reason": reason})
    return core.pay(agent, requirement["payTo"], price_xrp, passport_id=passport_id, memo=memo)


def buy(url: str, reason: str, approve_fn, agent=None, pay_fn=pay_invoice) -> dict:
    """Buy from one vendor URL. Always returns a dict with a "status" and explorer links."""
    agent = agent or core.load_wallets()[0]
    first = requests.get(url, timeout=30)
    if first.status_code != 402:
        return {"status": "error", "http_status": first.status_code, "body": first.text[:200], "links": {}}
    req = first.json()["accepts"][0]
    extra = req["extra"]
    purchase = {
        "vendor": extra["vendor"], "url": url, "price_xrp": str(drops_to_xrp(req["amount"])),
        "reason": reason, "requires_passport": extra["requiresPassport"], "payTo": req["payTo"],
    }
    links = {"vendor_account": ACCT_LINK + req["payTo"]}

    if not approve_fn(purchase):  # the checker plugs in here
        return {"status": "blocked", "purchase": purchase, "links": links}

    paid = pay_fn(agent, req, reason, extra["passportIssuer"])
    if paid["hash"]:
        links["payment_tx"] = TX_LINK + paid["hash"]
    if paid["code"] != "tesSUCCESS":
        return {"status": "refused_by_ledger", "code": paid["code"], "purchase": purchase, "links": links}

    second = requests.get(url, headers={"X-PAYMENT-TX": paid["hash"]}, timeout=30)
    body = second.json()
    if second.status_code != 200:
        return {"status": "refused_by_vendor", "http_status": second.status_code, "reason": body.get("reason"),
                "tx_hash": paid["hash"], "purchase": purchase, "links": links}
    return {"status": "paid", "data": body["data"], "receipt": body["receipt"], "tx_hash": paid["hash"],
            "purchase": purchase, "links": links}
