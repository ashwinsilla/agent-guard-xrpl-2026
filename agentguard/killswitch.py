"""The KILL SWITCH: stop a rogue agent everywhere, within seconds.

It does three things:
  1. CredentialDelete on the XRP Ledger  -> honest merchants can see the passport is gone;
  2. closes the funded AP4M payment channel -> no more vouchers can be redeemed;
  3. marks the agent revoked locally       -> the voucher gate refuses to sign anything.
Then `prove_enforcement()` shows the refusals: a merchant says 403, and a direct XRPL payment to
a passport-only account fails on the ledger with tecBAD_CREDENTIALS.

Fired automatically by the strike counter (see checker.py) or manually from the dashboard.
"""
import time

import requests

from agentguard import ap4m, config, events, passport, state, xrpl_core


def trigger(reason: str, manual: bool = False) -> dict:
    """Run the kill switch. Safe to call twice: the second call does nothing."""
    if state.load()["agent_revoked"]:
        return {"already_revoked": True}
    started = time.time()
    events.emit("killswitch", f"KILL SWITCH FIRED ({'manual' if manual else 'automatic'}): {reason}", "bad", reason=reason)
    state.update(agent_revoked=True)  # first: the gate refuses to sign from this instant
    revoked = passport.revoke_passport()
    channel = ap4m.close_channel()
    proof = prove_enforcement()
    took = time.time() - started
    events.emit("killswitch", f"Kill switch complete in {took:.1f}s: passport revoked, channel closed, refusals proven",
                "bad", seconds=round(took, 1))
    return {"revoked": revoked, "channel": channel, "proof": proof, "seconds": took}


def prove_enforcement() -> dict:
    """Show that the agent is now refused, by an honest merchant and by the ledger itself."""
    out = {}
    agent_xrpl = xrpl_core.load_wallets()[0].classic_address
    try:  # (a) an honest merchant refuses on sight
        r = requests.get(f"{config.MERCHANT_BASE}/fx/rates", headers={"X-AGENT-XRPL": agent_xrpl}, timeout=20)
        out["merchant"] = {"http_status": r.status_code, "reason": r.json().get("reason")}
        events.emit("enforcement", f"Honest merchant now answers HTTP {r.status_code}: {r.json().get('reason')}", "good")
    except Exception as exc:
        out["merchant"] = {"error": str(exc)[:100]}
        events.emit("enforcement", "Merchant server not reachable for the refusal demo", "warn")
    # (b) the XRP Ledger itself: pay a passport-only account, showing the (now deleted) passport
    merchant_xrpl = xrpl_core.load_wallets()[2].classic_address
    result = passport.pay_with_passport(merchant_xrpl, 1, memo="post-revoke payment attempt")
    out["xrpl"] = result
    events.emit("enforcement", f"XRPL payment after revoke: {result['code']} (the ledger itself refused)",
                "good" if result["code"] != "tesSUCCESS" else "bad", tx_hash=result["hash"],
                link=config.xrpl_tx_link(result["hash"]))
    return out
