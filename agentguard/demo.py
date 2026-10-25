"""Demo helpers shared by scripts and the dashboard buttons (reset, re-issue)."""
from xrpl.models.transactions import Payment
from xrpl.utils import xrp_to_drops

from agentguard import ap4m, config, events, multisig, passport, state, xrpl_core

FLOAT_XRP = 10  # the agent's small daily float (what it may spend today)


def reopen_channel_if_closed() -> None:
    """After a kill switch closed (or simulated closing) the channel, the demo needs a usable one again."""
    s = state.load()
    if ap4m.mode() == "mock" and s["channel_id"]:
        ch = s["mock_ledger"].get("channels", {}).get(s["channel_id"])
        if ch and int(ch["status"]) != 1:
            ch["status"] = 1  # MOCK only: re-open the simulated channel
            state.mutate(lambda st: st["mock_ledger"]["channels"].__setitem__(s["channel_id"], ch))


def refill_float() -> dict | None:
    """Acme's treasury tops the agent back up to its daily float (signed with Acme's approver key)."""
    agent, treasury, _ = xrpl_core.load_wallets()
    missing = round(FLOAT_XRP - multisig.spendable_xrp(agent.classic_address), 6)
    if missing < 0.05:
        return None
    tx = Payment(account=treasury.classic_address, destination=agent.classic_address, amount=xrp_to_drops(missing))
    result = xrpl_core._submit(multisig.approver(), tx)  # approver = the treasury's regular key
    events.emit("treasury", f"Acme's treasury sent the agent its {FLOAT_XRP} XRP daily float (+{missing} XRP): "
                f"{result['code']}", "good" if result["code"] == "tesSUCCESS" else "bad",
                tx_hash=result["hash"], link=config.xrpl_tx_link(result["hash"]))
    return result


def reset_demo() -> dict:
    """Back to the START of the demo: unfrozen, strikes cleared, passport active, float topped up.

    The AP4M voucher running total is kept on purpose (vouchers continue from the channel's total).
    """
    events.clear()
    state.reset(keep_channel=True)
    refill_float()  # first: accepting a passport needs a little XRP for the ledger reserve
    status = passport.ensure_active_passport()
    reopen_channel_if_closed()
    ok = status["status"] == "active"
    events.emit("reset", f"Demo reset: passport {status['status']}, AgentGuard co-signing, float topped up",
                "good" if ok else "bad", passport=status["status"])
    return status


def reissue_passport() -> dict:
    """Acme re-issues the passport with one approval (dashboard button), then unfreezes AgentGuard."""
    state.update(frozen=False, pending_revoke=False, agent_revoked=False, strikes=0)
    refill_float()  # first: accepting a passport needs a little XRP for the ledger reserve
    status = passport.ensure_active_passport()
    reopen_channel_if_closed()
    events.emit("passport", "Acme RE-ISSUED the passport: agent is trusted again, AgentGuard co-signs again", "good",
                passport=status["status"])
    return status
