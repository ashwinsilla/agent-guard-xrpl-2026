"""AgentGuard's CO-SIGNER: the second signature every XRPL payment from the agent needs.

The agent's wallet needs agent (1) + AgentGuard (1) to reach the quorum of 2 (see multisig.py).
The agent prepares and half-signs a payment, then hands it here. AgentGuard adds its signature
ONLY IF:
  * it isn't frozen by the kill switch,
  * the checker approved this exact purchase (single use),
  * the transaction is exactly what was approved: a Payment from the agent, to the approved
    merchant address, for the approved amount, presenting the agent's current passport.
Otherwise it refuses, and without AgentGuard's signature the XRP Ledger rejects the payment.
"""
from xrpl.models.transactions import Payment

from agentguard import events, multisig, passport, state


class CosignRefused(Exception):
    """AgentGuard will not co-sign. `.reason` says why."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def check(purchase_id: str, tx) -> dict:
    """Raise CosignRefused unless co-signing `tx` is allowed. Returns the approval it matched."""
    s = state.load()
    if s["frozen"]:
        raise CosignRefused("AgentGuard is frozen by the kill switch: it co-signs nothing for this agent")
    approval = s["approved_purchases"].get(purchase_id)
    if not approval or approval.get("rail") != "xrpl":
        raise CosignRefused("the checker has not approved this purchase")
    agent_address = passport._wallets()[0].classic_address
    if not isinstance(tx, Payment) or tx.account != agent_address:
        raise CosignRefused("not a payment from the agent's wallet")
    if tx.destination != approval["pay_to"]:
        raise CosignRefused("payment goes to a different address than the checker approved")
    if str(tx.amount) != approval["amount"]:
        raise CosignRefused("amount differs from what the checker approved")
    if approval.get("requires_passport"):
        current = passport.get_passport_status()["credential_id"]
        if not current or current not in (tx.credential_ids or []):
            raise CosignRefused("payment does not present the agent's current passport")
    return approval


def cosign_and_submit(purchase_id: str, prepared_tx, agent_partial) -> dict:
    """Check, add AgentGuard's signature, submit. Returns {"code","hash","on_ledger"}; raises CosignRefused."""
    try:
        approval = check(purchase_id, prepared_tx)
    except CosignRefused as exc:
        events.emit("cosigner", f"AgentGuard REFUSED to co-sign: {exc.reason}", "bad", reason=exc.reason)
        raise
    state.mutate(lambda s: s["approved_purchases"].pop(purchase_id, None))  # an approval is single-use
    ours = multisig.partial_sign(prepared_tx, multisig.agentguard_key())
    result = multisig.submit_signed(prepared_tx, [agent_partial, ours])
    events.emit("cosigner", f"AgentGuard CO-SIGNED {approval['label']}: ledger says {result['code']}",
                "good" if result["code"] == "tesSUCCESS" else "bad", tx_hash=result["hash"],
                link=f"https://testnet.xrpl.org/transactions/{result['hash']}" if result.get("on_ledger") else None,
                mode="LIVE")
    return result
