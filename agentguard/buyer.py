"""The ONLY way the agent buys anything: quote -> checker -> voucher gate -> merchant.

    1. Ask the merchant (HTTP 402) what it wants.         (honest merchants refuse a revoked agent here)
    2. The CHECKER reviews the purchase.                   (BLOCK = strike, HOLD = wait for a human)
    3. The VOUCHER GATE signs a voucher, or refuses.       (revoked / unapproved -> no signature)
    4. Send the voucher to the merchant, get the data.     (merchant checks the passport, redeems on-chain)

Every step is logged to the event feed. Returns a dict with a "status" so callers never need try/except:
  paid | blocked | not_approved | refused_by_gate | refused_by_merchant | error
"""
import requests

from agentguard import ap4m, checker, config, events, xrpl_core
from agentguard.checker import Purchase


def _agent_xrpl() -> str:
    return xrpl_core.load_wallets()[0].classic_address


def buy(path: str, merchant_key: str, reason: str) -> dict:
    """Buy from one merchant endpoint. `merchant_key` is fx | crypto | news | news_deep | alpha."""
    url = config.MERCHANT_BASE + path
    headers = {"X-AGENT-XRPL": _agent_xrpl()}
    try:
        quote = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {"status": "error", "reason": f"merchant unreachable: {exc}"}
    if quote.status_code == 403:
        return {"status": "refused_by_merchant", "reason": quote.json().get("reason"), "http_status": 403}
    if quote.status_code != 402:
        return {"status": "error", "reason": f"expected 402, got {quote.status_code}"}
    req = quote.json()["accepts"][0]
    extra = req["extra"]
    purchase = Purchase(merchant_key=merchant_key, merchant=extra["merchant"], item=extra["item"],
                        price_rlusd=req["amount_rlusd"], reason=reason,
                        description=quote.json()["resource"]["description"])
    events.emit("agent", f"Agent wants to buy {purchase.item} from {purchase.merchant} for {purchase.price_rlusd} RLUSD "
                f"(reason: {reason})", "info", merchant=purchase.merchant, item=purchase.item)

    decision = checker.review(purchase)
    if decision.decision == "BLOCK":
        return {"status": "blocked", "decision": decision.decision, "reason": decision.reason, "purchase": purchase.__dict__}
    if decision.decision == "HOLD":
        events.emit("checker", f"Waiting for a human to approve {purchase.item}…", "warn", purchase_id=purchase.purchase_id)
        if not checker.wait_for_human(purchase.purchase_id):
            return {"status": "not_approved", "reason": "held purchase was not approved", "purchase": purchase.__dict__}

    try:
        ap4m.ensure_channel()
        voucher = ap4m.sign_voucher(purchase.purchase_id, merchant_key, purchase.price_rlusd)
    except ap4m.GateRefused as exc:
        return {"status": "refused_by_gate", "reason": exc.reason, "purchase": purchase.__dict__}

    paid = requests.get(url, timeout=120, headers={
        **headers, "X-CHANNEL-ID": voucher["channel_id"],
        "X-VOUCHER-CUMULATIVE": str(voucher["cumulative"]), "X-VOUCHER-SIGNATURE": voucher["signature"]})
    body = paid.json()
    if paid.status_code != 200:
        return {"status": "refused_by_merchant", "reason": body.get("reason"), "http_status": paid.status_code,
                "purchase": purchase.__dict__}
    return {"status": "paid", "data": body["data"], "receipt": body["receipt"], "purchase": purchase.__dict__,
            "sponsored_message": body.get("sponsored_message")}
