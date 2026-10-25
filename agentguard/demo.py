"""Demo helpers shared by scripts and the dashboard buttons (reset, re-issue)."""
from agentguard import ap4m, events, passport, state


def reopen_channel_if_closed() -> None:
    """After a kill switch closed (or simulated closing) the channel, the demo needs a usable one again."""
    s = state.load()
    if ap4m.mode() == "mock" and s["channel_id"]:
        ch = s["mock_ledger"]["channels"].get(s["channel_id"])
        if ch and int(ch["status"]) != 1:
            ch["status"] = 1  # MOCK only: re-open the simulated channel
            state.mutate(lambda st: st["mock_ledger"]["channels"].__setitem__(s["channel_id"], ch))


def reset_demo() -> dict:
    """Back to the START of the demo: strikes cleared, passport active, channel usable.

    The voucher running total is kept on purpose (AP4M vouchers continue from the on-chain total).
    """
    events.clear()
    state.reset(keep_channel=True)
    status = passport.ensure_active_passport()
    reopen_channel_if_closed()
    events.emit("reset", "Demo reset: passport active, strikes cleared", "good", passport=status["status"])
    return status


def reissue_passport() -> dict:
    """Acme re-issues the passport with one approval (dashboard button)."""
    state.update(agent_revoked=False, strikes=0)
    status = passport.ensure_active_passport()
    reopen_channel_if_closed()
    events.emit("passport", "Acme RE-ISSUED the passport: agent is trusted again", "good", passport=status["status"])
    return status
