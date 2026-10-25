"""Multi-signing for the agent's wallet: the agent can't move money alone.

The agent's XRPL account has its master key DISABLED and a "signer list" instead:

    agent-signer key   weight 1   (held by the AI agent's runtime)
    AgentGuard key     weight 1   (held by AgentGuard, the checker)
    Acme approver key  weight 2   (Acme's approver; a Ledger device in production, a software key in the demo)
    quorum = 2

So the ledger itself accepts a transaction from the agent's account only when it carries:
  * agent + AgentGuard (1 + 1 = 2)  -> routine purchases, after AgentGuard's checks pass, or
  * Acme's approver alone (2)       -> revocation, returning the float to the treasury.
The agent alone (weight 1) is never enough: the ledger answers tefBAD_QUORUM.

Every function returns {"code": <ledger result code>, "hash": <tx hash>} like xrpl_core does.
"""
import os
import time

from xrpl.models.requests import Tx
from xrpl.transaction import autofill, multisign, sign, submit
from xrpl.wallet import Wallet

from agentguard import xrpl_core as core

QUORUM = 2
WEIGHTS = {"AGENT_SIGNER": 1, "AGENTGUARD": 1, "APPROVER": 2}


def role_wallet(role: str) -> Wallet:
    """The key for one signer role, read from .env (XRPL_<ROLE>_SECRET). Never printed."""
    secret = os.getenv(f"XRPL_{role}_SECRET")
    if not secret:
        raise RuntimeError(f"XRPL_{role}_SECRET is missing from .env: run scripts/setup_agent_wallet.py")
    return Wallet.from_seed(secret)


def agent_signer() -> Wallet:
    return role_wallet("AGENT_SIGNER")


def agentguard_key() -> Wallet:
    return role_wallet("AGENTGUARD")


def approver() -> Wallet:
    return role_wallet("APPROVER")


def prepare(tx, signers_count: int = 2):
    """Fill in fee, sequence and LastLedgerSequence. Multi-signed transactions cost (1 + signers) x base fee."""
    return autofill(tx, core.get_client(), signers_count=signers_count)


def partial_sign(prepared_tx, wallet: Wallet):
    """One signer's signature on the prepared transaction (not valid on its own)."""
    return sign(prepared_tx, wallet, multisign=True)


def submit_signed(prepared_tx, partials: list) -> dict:
    """Combine the signatures, submit, and wait until the ledger has decided.

    tec* codes (e.g. tecBAD_CREDENTIALS) are recorded on the ledger and have an explorer page.
    tef* codes (e.g. tefBAD_QUORUM) are refused before they ever reach a ledger: no explorer page.
    """
    client = core.get_client()
    combined = multisign(prepared_tx, partials)
    tx_hash = combined.get_hash()
    prelim = submit(combined, client).result.get("engine_result", "")
    if prelim.startswith(("tef", "tem", "tel")):  # refused outright: never enters a ledger
        return {"code": prelim, "hash": tx_hash, "on_ledger": False}
    return _wait_for_validation(client, tx_hash, prelim)


def _wait_for_validation(client, tx_hash: str, prelim: str) -> dict:
    """Poll until the transaction is in a validated ledger (about 3-5 seconds on XRPL)."""
    for _ in range(30):
        r = client.request(Tx(transaction=tx_hash)).result
        if r.get("validated"):
            return {"code": r["meta"]["TransactionResult"], "hash": tx_hash, "on_ledger": True}
        time.sleep(1)
    return {"code": f"not validated in 30s (preliminary: {prelim})", "hash": tx_hash, "on_ledger": False}


LSF_DISABLE_MASTER = 0x00100000


def account_info(address: str) -> dict:
    """The account's ledger data (Balance, Flags, OwnerCount, RegularKey...), or {} if it doesn't exist."""
    from xrpl.models.requests import AccountInfo
    r = core.get_client().request(AccountInfo(account=address, ledger_index="validated", signer_lists=True))
    data = r.result.get("account_data", {})
    lists = r.result.get("signer_lists") or data.get("signer_lists") or []
    return {**data, "_signer_list": lists[0] if lists else None}


def spendable_xrp(address: str) -> float:
    """XRP the account can actually spend: balance minus the ledger's reserve for it.

    The XRP Ledger keeps a base reserve per account plus a small reserve per owned object
    (signer list, credential...). That part can't be sent anywhere.
    """
    from xrpl.models.requests import ServerInfo
    info = account_info(address)
    if not info:
        return 0.0
    led = core.get_client().request(ServerInfo()).result["info"]["validated_ledger"]
    reserve = float(led["reserve_base_xrp"]) + float(led["reserve_inc_xrp"]) * int(info.get("OwnerCount", 0))
    return max(0.0, int(info["Balance"]) / 1_000_000 - reserve)


def sign_and_submit(tx, wallets: list[Wallet]) -> dict:
    """Prepare + sign with every given wallet + submit. Used for admin actions (accept, revoke sweep...)."""
    prepared = prepare(tx, signers_count=len(wallets))
    return submit_signed(prepared, [partial_sign(prepared, w) for w in wallets])
