"""The agent PASSPORT on the XRP Ledger (an XRPL "Credential").

Think of it as an employee ID badge:
  * the ISSUER (Acme) creates it for the AGENT      -> issue_passport()
  * the AGENT accepts it (badge activated)          -> accept_passport()
  * the ISSUER can take it back at any time         -> revoke_passport()   (the KILL SWITCH)
  * anyone can check it by reading the ledger       -> get_passport_status()
  * the agent shows it when paying a merchant       -> pay_with_passport()

The passport "level" is encoded in the credential type, e.g. AGENTGUARD_PASSPORT_SMALL,
so a merchant can say "I trust SMALL and up" and the ledger itself enforces it.

Who signs what (see multisig.py):
  * issue / revoke: Acme's APPROVER key, set as the issuer's regular key (a Ledger device in production);
  * accept / pay:   the agent's account, co-signed by the agent-signer key AND AgentGuard (master key is disabled).

This builds on the proven Layer 1 helpers in xrpl_core.py (which are left unchanged).
"""
from datetime import datetime, timedelta, timezone

from xrpl.models.requests import LedgerEntry
from xrpl.models.requests.ledger_entry import Credential as LedgerCredential
from xrpl.models.transactions import CredentialAccept, CredentialCreate, CredentialDelete, Memo, Payment
from xrpl.utils import datetime_to_ripple_time, ripple_time_to_datetime, str_to_hex, xrp_to_drops

from agentguard import config, events, multisig, state, xrpl_core as core
from agentguard.config import xrpl_tx_link

LEVELS = ("SMALL", "MEDIUM", "LARGE")  # how much the issuer trusts the agent
DEFAULT_LEVEL = "SMALL"
TYPE_PREFIX = "AGENTGUARD_PASSPORT_"


def credential_type(level: str = DEFAULT_LEVEL) -> str:
    """Hex credential type for a level. SMALL equals the Layer 1 type (so old passports still work)."""
    if level not in LEVELS:
        raise ValueError(f"unknown passport level {level!r}; use one of {LEVELS}")
    return str_to_hex(TYPE_PREFIX + level)


BIND_PREFIX = "evm:"  # the credential's URI field holds "evm:<agent EVM address>"


def _binding_uri() -> str | None:
    """Link the XRPL passport to the agent's EVM (AP4M) wallet, so merchants know the voucher signer IS the badge holder."""
    addr = config.env("AGENT_EVM_ADDRESS")
    return str_to_hex(BIND_PREFIX + addr) if addr else None


def _wallets():
    return core.load_wallets()  # (agent, issuer, merchant)


def _approver_or_issuer(issuer):
    """Acme signs with its approver key when set up (scripts/setup_agent_wallet.py), else its master key."""
    try:
        return multisig.approver()
    except RuntimeError:
        return issuer


def _log_tx(kind: str, title: str, result: dict, **extra) -> dict:
    ok = result["code"] == "tesSUCCESS"
    # tef* results never reach a ledger, so there is no explorer page to link to.
    link = xrpl_tx_link(result["hash"]) if result.get("on_ledger", True) else None
    events.emit(kind, f"{title}: {result['code']}", "good" if ok else "bad",
                tx_hash=result["hash"], link=link, mode="LIVE", **extra)
    return result


def end_of_today(now: datetime | None = None) -> datetime:
    """'Valid for today's task': midnight UTC tonight (or tomorrow night if less than an hour is left)."""
    now = now or datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight if midnight - now >= timedelta(hours=1) else midnight + timedelta(days=1)


def issue_passport(level: str = DEFAULT_LEVEL, expires_at: datetime | None = None) -> dict:
    """ISSUER creates a passport for the agent. Default expiry: the end of today (UTC)."""
    agent, issuer, _ = _wallets()
    expires_at = expires_at or end_of_today()
    extra = {"uri": _binding_uri()} if _binding_uri() else {}
    tx = CredentialCreate(
        account=issuer.classic_address, subject=agent.classic_address,
        credential_type=credential_type(level), expiration=datetime_to_ripple_time(expires_at), **extra,
    )
    result = core._submit(_approver_or_issuer(issuer), tx)  # Acme approves with its approver key
    if result["code"] == "tesSUCCESS":
        state.update(agent_revoked=False)
    return _log_tx("passport", f"Passport ISSUED ({level}, expires {expires_at:%Y-%m-%d %H:%M} UTC)", result, level=level)


def accept_passport(level: str = DEFAULT_LEVEL) -> dict:
    """AGENT accepts the passport (co-signed by AgentGuard). Until then merchants treat it as not valid."""
    agent, issuer, _ = _wallets()
    tx = CredentialAccept(account=agent.classic_address, issuer=issuer.classic_address,
                          credential_type=credential_type(level))
    result = multisig.sign_and_submit(tx, [multisig.agent_signer(), multisig.agentguard_key()])
    return _log_tx("passport", "Passport ACCEPTED by agent (co-signed by AgentGuard)", result, level=level)


def revoke_passport(level: str | None = None) -> dict:
    """ISSUER deletes the passport (CredentialDelete). If level is None, whichever level exists is revoked."""
    agent, issuer, _ = _wallets()
    level = level or (get_passport_status()["level"] or DEFAULT_LEVEL)
    tx = CredentialDelete(account=issuer.classic_address, subject=agent.classic_address,
                          issuer=issuer.classic_address, credential_type=credential_type(level))
    result = core._submit(_approver_or_issuer(issuer), tx)  # Acme approves with its approver key
    if result["code"] == "tesSUCCESS":
        state.update(agent_revoked=True)
    return _log_tx("passport", "Passport REVOKED (CredentialDelete)", result, level=level)


def _find_node(client, agent_address: str, issuer_address: str):
    """Look for the credential at every level. Returns (level, ledger_entry_result) or (None, None)."""
    for level in LEVELS:
        response = client.request(LedgerEntry(
            credential=LedgerCredential(subject=agent_address, issuer=issuer_address,
                                        credential_type=credential_type(level)),
            ledger_index="validated"))
        if response.is_successful():
            return level, response.result
    return None, None


def get_passport_status(agent_address: str | None = None, issuer_address: str | None = None) -> dict:
    """Read the passport from the ledger.

    Returns {"status", "level", "expires", "issuer", "credential_id", "evm_address"} where status is:
      active | issued-not-accepted | expired | revoked | not found
    "revoked" = not on the ledger any more AND our kill switch recorded a revocation.
    """
    agent, issuer, _ = _wallets()
    agent_address = agent_address or agent.classic_address
    issuer_address = issuer_address or issuer.classic_address
    level, result = _find_node(core.get_client(), agent_address, issuer_address)
    base = {"level": level, "expires": None, "issuer": issuer_address, "credential_id": None, "evm_address": None}
    if result is None:
        return {**base, "status": "revoked" if state.load()["agent_revoked"] else "not found"}
    node = result["node"]
    expiration = node.get("Expiration")
    expires = ripple_time_to_datetime(expiration) if expiration is not None else None
    if not node.get("Flags", 0) & core.LSF_ACCEPTED:
        status = "issued-not-accepted"
    elif expires is not None and expires <= datetime.now(timezone.utc):
        status = "expired"
    else:
        status = "active"
    if state.load()["last_credential_id"] != result["index"]:  # only write when it changes
        state.update(last_credential_id=result["index"])
    uri = bytes.fromhex(node["URI"]).decode("utf-8", "replace") if node.get("URI") else ""
    evm = uri[len(BIND_PREFIX):] if uri.startswith(BIND_PREFIX) else None
    return {**base, "status": status, "expires": expires, "credential_id": result["index"], "evm_address": evm}


def pay_with_passport(dest: str, amount_xrp, memo: str | None = None, signers: list | None = None) -> dict:
    """The agent's account pays `dest` in XRP, attaching its passport (CredentialIDs).

    `signers` = the wallets that sign (default: Acme's approver, weight 2, used for the kill-switch proof).
    Routine purchases don't use this: they go through buyer.py -> cosigner.py (agent + AgentGuard).

    Merchants with Deposit Authorization accept this only if the passport is valid; a refusal
    comes back as a normal result (e.g. tecBAD_CREDENTIALS after revoke), never an exception.
    """
    agent, _, _ = _wallets()
    # After a revoke there is no live passport, so we show the last one we had: the ledger then
    # answers tecBAD_CREDENTIALS (the proof that the badge was cancelled).
    passport_id = get_passport_status()["credential_id"] or state.load()["last_credential_id"]
    kwargs = {}
    if passport_id:
        kwargs["credential_ids"] = [passport_id]
    if memo:
        kwargs["memos"] = [Memo(memo_data=str_to_hex(memo))]
    tx = Payment(account=agent.classic_address, destination=dest, amount=xrp_to_drops(amount_xrp), **kwargs)
    result = multisig.sign_and_submit(tx, signers or [multisig.approver()])
    return _log_tx("xrpl_payment", f"XRPL payment of {amount_xrp} XRP to {dest[:8]}…", result,
                   with_passport=bool(passport_id))


def ensure_active_passport(level: str = DEFAULT_LEVEL) -> dict:
    """Make sure the agent holds an ACTIVE passport (used by reset_demo and the Re-issue button)."""
    status = get_passport_status()
    wallet = config.env("AGENT_EVM_ADDRESS")
    if status["status"] == "active" and wallet and (status["evm_address"] or "").lower() != wallet.lower():
        # The passport names the agent's Mastercard (EVM) wallet; if that wallet changed, re-issue it.
        events.emit("passport", "Agent's EVM wallet changed: re-issuing the passport so it names the new wallet", "warn")
        revoke_passport(status["level"])
        status = get_passport_status()
    if status["status"] == "active":
        return status
    if status["status"] == "issued-not-accepted":
        accept_passport(status["level"])  # only the agent's acceptance is missing
        return get_passport_status()
    if status["status"] == "expired":
        revoke_passport(status["level"])  # clear the stale one so a fresh one can be created
    issue_passport(level)
    accept_passport(level)
    return get_passport_status()
