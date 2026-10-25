"""The KILL SWITCH: stop a rogue agent everywhere, within seconds. Two stages.

Stage 1, FREEZE (automatic, instant), fired by repeated refusals or (in the demo) by the agent's runtime
reporting an attempt to pay without AgentGuard:
  * AgentGuard stops co-signing  -> the agent can't pay ANYONE on the XRP Ledger, attacker included
                                    (its wallet needs AgentGuard's signature; see multisig.py);
  * the voucher gate stops signing and the Mastercard AP4M channel is closed.

Stage 2, CONFIRM (Acme's approver key; a Ledger device in production, or the dashboard button):
  * CredentialDelete: the passport is revoked, so every verified-only merchant refuses the agent;
  * proof: a payment to FX Rates presenting the old passport is refused by the ledger (tecBAD_CREDENTIALS),
    and an honest merchant answers 403;
  * the remaining float is swept back to Acme's treasury (signed by the approver key alone: weight 2).

AUTO_CONFIRM_KILL=true runs stage 2 straight after stage 1 (handy for unattended runs).
Every step is wrapped so one failure never stops the others, and every step is logged.
"""
import time
from decimal import Decimal

import requests
from xrpl.models.transactions import Payment
from xrpl.utils import xrp_to_drops

from agentguard import ap4m, config, events, multisig, passport, state, xrpl_core


def _safe(label: str, fn):
    """Run one kill-switch step; log (don't raise) if it fails."""
    try:
        return fn()
    except Exception as exc:
        events.emit("killswitch", f"{label} failed: {type(exc).__name__}: {str(exc)[:150]}", "warn")
        return {"error": str(exc)[:150]}


def freeze(reason: str, manual: bool = False) -> dict:
    """Stage 1. Safe to call twice: the second call does nothing."""
    if state.load()["frozen"]:
        return {"already_frozen": True}
    started = time.time()
    state.update(frozen=True, pending_revoke=True)  # from this instant AgentGuard signs nothing
    events.emit("killswitch", f"KILL SWITCH FIRED ({'manual' if manual else 'automatic'}): {reason}. "
                "AgentGuard stopped co-signing: the agent can now pay no one.", "bad", reason=reason)
    events.emit("killswitch", f"Agent frozen in {time.time() - started:.1f}s. Now closing its Mastercard channel "
                "(first settling the merchant's last voucher, so honest merchants still get paid).", "warn")
    channel = _safe("Closing the AP4M channel", ap4m.close_channel)
    events.emit("killswitch", "Waiting for Acme's approver key to revoke the passport and return the float.",
                "warn", pending_revoke=True)
    out = {"frozen": True, "channel": channel}
    if config.flag("AUTO_CONFIRM_KILL", False):
        out["confirm"] = confirm_revoke()
    return out


def confirm_revoke() -> dict:
    """Stage 2: Acme's approver key revokes the passport, proves the refusals, returns the float."""
    if not state.load()["frozen"]:
        freeze("manual kill", manual=True)
    started = time.time()
    events.emit("killswitch", "Acme CONFIRMED with its approver key: revoking the passport", "bad")
    revoked = _safe("CredentialDelete", passport.revoke_passport)
    proof = _safe("Refusal proof", prove_enforcement)
    swept = _safe("Returning the float", sweep_float)
    state.update(pending_revoke=False)
    took = time.time() - started
    events.emit("killswitch", f"Kill switch complete in {took:.1f}s: passport revoked, channel closed, "
                "float returned to the treasury", "bad", seconds=round(took, 1))
    return {"revoked": revoked, "proof": proof, "swept": swept, "seconds": took}


def prove_enforcement() -> dict:
    """Show the agent is now refused by an honest merchant and by the XRP Ledger itself."""
    out = {}
    agent_xrpl = xrpl_core.load_wallets()[0].classic_address
    try:  # (a) an honest merchant (News, on the Mastercard rail) checks the passport and refuses
        r = requests.get(f"{config.MERCHANT_BASE}/news/sentiment", headers={"X-AGENT-XRPL": agent_xrpl}, timeout=20)
        out["merchant"] = {"http_status": r.status_code, "reason": r.json().get("reason")}
        events.emit("enforcement", f"News Sentiment Co. now answers HTTP {r.status_code}: {r.json().get('reason')}", "good")
    except Exception as exc:
        out["merchant"] = {"error": str(exc)[:100]}
        events.emit("enforcement", "Merchant server not reachable for the refusal demo", "warn")
    # (b) the ledger itself: pay FX Rates presenting the deleted passport. Even with a fully valid
    #     signature (Acme's approver, weight 2), the ledger refuses: tecBAD_CREDENTIALS.
    fx = config.env("XRPL_VENDOR_FX_ADDRESS")
    result = passport.pay_with_passport(fx, Decimal("0.05"), memo="post-revoke payment attempt with the old passport")
    out["xrpl"] = result
    events.emit("enforcement", f"Payment to FX Rates with the old passport: {result['code']} (refused by the XRP Ledger)",
                "good" if result["code"] != "tesSUCCESS" else "bad", tx_hash=result["hash"],
                link=config.xrpl_tx_link(result["hash"]) if result.get("on_ledger") else None)
    return out


def sweep_float() -> dict:
    """Send everything the agent can spend back to Acme's treasury (the issuer), approver-signed."""
    agent, treasury, _ = xrpl_core.load_wallets()
    amount = round(multisig.spendable_xrp(agent.classic_address) - 0.01, 6)  # keep a hair for the fee
    if amount <= 0:
        events.emit("killswitch", "No float left to return", "info")
        return {"amount": 0}
    tx = Payment(account=agent.classic_address, destination=treasury.classic_address, amount=xrp_to_drops(amount))
    result = multisig.sign_and_submit(tx, [multisig.approver()])
    events.emit("killswitch", f"Float of {amount} XRP returned to Acme's treasury: {result['code']}",
                "good" if result["code"] == "tesSUCCESS" else "bad", tx_hash=result["hash"],
                link=config.xrpl_tx_link(result["hash"]) if result.get("on_ledger") else None)
    return {"amount": amount, **result}
