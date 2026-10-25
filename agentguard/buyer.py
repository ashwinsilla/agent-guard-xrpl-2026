"""The ONLY way the agent buys anything: quote -> checker -> AgentGuard's signature -> merchant.

    1. Ask the merchant (HTTP 402) what it wants.          (honest merchants refuse a revoked agent here)
    2. The CHECKER reviews the purchase.                    (BLOCK = strike, HOLD = wait for a human)
    3a. XRPL rail: the agent half-signs the payment, AgentGuard co-signs it (cosigner.py), the ledger
        settles it. Deposit Authorization at the merchant means the ledger also checks the passport.
    3b. AP4M rail: AgentGuard's voucher gate signs a voucher (ap4m.py), or refuses.
    4. Retry the merchant with the proof of payment, get the data.

`pay_direct()` is what a HIJACKED agent would do: pay someone with only its own signature.
The XRP Ledger refuses it (tefBAD_QUORUM: AgentGuard didn't sign). Such a refusal never reaches a ledger,
so AgentGuard can't see it in general: in this demo the agent's runtime REPORTS the attempt, which fires the
kill switch. In production the freeze comes from repeated refusals (strikes); the money is safe either way.

Every step is logged to the event feed. `buy()` returns a dict with a "status" so callers never need try/except:
  paid | blocked | not_approved | refused_by_agentguard | refused_by_ledger | refused_by_merchant | error
"""
import base64
import json
from decimal import Decimal

import requests
from xrpl.models.transactions import Memo, Payment
from xrpl.utils import str_to_hex, xrp_to_drops

from agentguard import ap4m, checker, config, cosigner, events, multisig, passport, xrpl_core
from agentguard.checker import Purchase


def _agent_xrpl() -> str:
    return xrpl_core.load_wallets()[0].classic_address


def _json(resp) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {"reason": f"merchant sent a non-JSON reply (HTTP {resp.status_code})"}


def buy(path: str, merchant_key: str, reason: str) -> dict:
    """Buy from one merchant endpoint. `merchant_key` is fx | crypto | news | news_deep | alpha."""
    url = config.MERCHANT_BASE + path
    headers = {"X-AGENT-XRPL": _agent_xrpl()}
    try:
        quote = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {"status": "error", "reason": f"merchant unreachable: {exc}"}
    body = _json(quote)
    if quote.status_code == 403:
        return {"status": "refused_by_merchant", "reason": body.get("reason"), "http_status": 403}
    if quote.status_code != 402:
        return {"status": "error", "reason": f"expected 402, got {quote.status_code}"}
    req = body["accepts"][0]
    extra = req["extra"]
    purchase = Purchase(merchant_key=merchant_key, merchant=extra["merchant"], item=extra["item"],
                        category=extra["category"], price=req["price"], currency=req["currency"], rail=extra["rail"],
                        pay_to=req["payTo"], requires_passport=extra["requiresPassport"], reason=reason)
    events.emit("agent", f"Agent wants to buy {purchase.label} (agent's reason: {reason})", "info",
                merchant=purchase.merchant, item=purchase.item)

    decision = checker.review(purchase)
    if decision.decision == "BLOCK":
        return {"status": "blocked", "reason": decision.reason, "ai_explanation": decision.ai_explanation,
                "purchase": purchase.__dict__, "sponsored_message": body.get("sponsored_message")}
    if decision.decision == "HOLD":
        events.emit("checker", f"Waiting for a human to approve {purchase.item}…", "warn", purchase_id=purchase.purchase_id)
        if not checker.wait_for_human(purchase.purchase_id):
            return {"status": "not_approved", "reason": "held purchase was not approved", "purchase": purchase.__dict__}

    if purchase.rail == "xrpl":
        proof_headers, failure = _pay_xrpl(purchase, extra["invoiceId"])
    else:
        proof_headers, failure = _pay_ap4m(purchase)
    if failure:
        return {**failure, "purchase": purchase.__dict__}

    paid = requests.get(url, timeout=120, headers={**headers, **proof_headers})
    pbody = _json(paid)
    if paid.status_code != 200:
        return {"status": "refused_by_merchant", "reason": pbody.get("reason"), "http_status": paid.status_code,
                "purchase": purchase.__dict__}
    return {"status": "paid", "data": pbody["data"], "receipt": pbody["receipt"], "purchase": purchase.__dict__,
            "sponsored_message": pbody.get("sponsored_message")}


def _pay_xrpl(p: Purchase, invoice_id: str):
    """Agent half-signs, AgentGuard co-signs, the ledger settles. Returns (proof headers, failure dict)."""
    kwargs = {"memos": [Memo(memo_data=str_to_hex(json.dumps({"invoiceId": invoice_id})))]}
    if p.requires_passport:
        passport_id = passport.get_passport_status()["credential_id"]
        if passport_id:
            kwargs["credential_ids"] = [passport_id]
    tx = Payment(account=_agent_xrpl(), destination=p.pay_to, amount=xrp_to_drops(Decimal(p.price)), **kwargs)
    prepared = multisig.prepare(tx, signers_count=2)
    agent_half = multisig.partial_sign(prepared, multisig.agent_signer())  # the agent's own signature
    try:
        result = cosigner.cosign_and_submit(p.purchase_id, prepared, agent_half)
    except cosigner.CosignRefused as exc:
        return None, {"status": "refused_by_agentguard", "reason": exc.reason}
    if result["code"] != "tesSUCCESS":
        return None, {"status": "refused_by_ledger", "reason": result["code"], "tx_hash": result["hash"]}
    return {"X-PAYMENT-TX": result["hash"]}, None


def _pay_ap4m(p: Purchase):
    """AgentGuard's voucher gate signs a Mastercard AP4M voucher. Returns (proof headers, failure dict)."""
    try:
        ap4m.ensure_channel()
        voucher = ap4m.sign_voucher(p.purchase_id, p.merchant_key, p.price)
    except ap4m.GateRefused as exc:
        return None, {"status": "refused_by_agentguard", "reason": exc.reason}
    payload = {"channelId": voucher["channel_id"], "cumulativeAmount": str(voucher["cumulative"]),
               "signature": voucher["signature"]}
    return {"PAYMENT-SIGNATURE": base64.b64encode(json.dumps(payload).encode()).decode()}, None


def pay_direct(destination: str, amount_xrp: str, why: str = "") -> dict:
    """A hijacked agent tries to pay with ONLY its own key, skipping AgentGuard.

    The ledger refuses it (weight 1 < quorum 2: tefBAD_QUORUM), and the attempt itself is a
    manipulation signal, so AgentGuard fires the kill switch.
    """
    events.emit("agent", f"Agent tries to pay {amount_xrp} XRP DIRECTLY to {destination[:10]}… with only its own "
                f"signature (bypassing AgentGuard){': ' + why if why else ''}", "bad")
    tx = Payment(account=_agent_xrpl(), destination=destination, amount=xrp_to_drops(Decimal(amount_xrp)))
    prepared = multisig.prepare(tx, signers_count=1)
    result = multisig.submit_signed(prepared, [multisig.partial_sign(prepared, multisig.agent_signer())])
    events.emit("enforcement", f"XRP Ledger REFUSED the agent-only payment: {result['code']} "
                "(no AgentGuard signature, quorum not met)", "good" if result["code"] != "tesSUCCESS" else "bad",
                code=result["code"])
    from agentguard import killswitch
    killswitch.freeze("the agent tried to pay without AgentGuard's co-signature: it is being manipulated")
    return {"status": "refused_by_ledger" if result["code"] != "tesSUCCESS" else "paid", **result}
