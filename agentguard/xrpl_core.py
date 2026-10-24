"""Shared XRPL helpers for AgentGuard (testnet only).

Big picture:
- The ISSUER (Acme) gives the AGENT a "passport" = an XRPL Credential.
- The MERCHANT turns on Deposit Authorization and only pre-approves that passport type,
  so the ledger itself rejects payments from agents without a valid passport.
- Revoking the passport (CredentialDelete) is the KILL SWITCH.

Every transaction helper returns a dict: {"code": <result code>, "hash": <tx hash>}.
"""
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, AccountObjects, LedgerEntry
from xrpl.models.requests.ledger_entry import Credential as LedgerCredential
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    CredentialAccept,
    CredentialCreate,
    CredentialDelete,
    DepositPreauth,
    Memo,
    Payment,
)
from xrpl.models.transactions.deposit_preauth import Credential as PreauthCredential
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.utils import datetime_to_ripple_time, ripple_time_to_datetime, str_to_hex, xrp_to_drops
from xrpl.wallet import Wallet

# Read the .env file in the project root (not the current folder) so scripts work from anywhere.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

TESTNET_URL = "https://s.altnet.rippletest.net:51234/"

# The passport "type" (hex-encoded, as the ledger requires).
PASSPORT_TYPE = str_to_hex("AGENTGUARD_PASSPORT_SMALL")

# Flag the ledger sets on a credential once the subject has accepted it.
LSF_ACCEPTED = 0x00010000


def get_client() -> JsonRpcClient:
    """Connect to the XRPL testnet (URL can be overridden with XRPL_RPC_URL)."""
    return JsonRpcClient(os.getenv("XRPL_RPC_URL", TESTNET_URL))


def load_wallets() -> tuple[Wallet, Wallet, Wallet]:
    """Return (agent, issuer, merchant) wallets built from the secrets in .env."""
    return tuple(  # type: ignore[return-value]
        Wallet.from_seed(os.environ[f"XRPL_{role}_SECRET"]) for role in ("AGENT", "ISSUER", "MERCHANT")
    )


def _submit(wallet: Wallet, tx) -> dict:
    """Sign + submit a transaction, wait for validation, return code and hash.

    submit_and_wait raises an error when a transaction fails on-ledger (e.g. tecNO_PERMISSION).
    We catch that so refusals come back as normal results instead of crashing.
    """
    client = get_client()
    signed = autofill_and_sign(tx, client, wallet)  # fills fee/sequence, then signs
    tx_hash = signed.get_hash()  # known before submitting, so we have it even on failure
    try:
        result = submit_and_wait(signed, client).result
        return {"code": result["meta"]["TransactionResult"], "hash": tx_hash}
    except XRPLReliableSubmissionException as exc:
        # The message looks like "Transaction failed: tecNO_PERMISSION"
        return {"code": str(exc).split(":")[-1].strip(), "hash": tx_hash}


def issue_passport(issuer: Wallet, agent_address: str, hours_valid: int = 24) -> dict:
    """ISSUER creates a passport (Credential) for the agent, valid for `hours_valid` hours."""
    expires = datetime.now(timezone.utc) + timedelta(hours=hours_valid)
    tx = CredentialCreate(
        account=issuer.classic_address,
        subject=agent_address,
        credential_type=PASSPORT_TYPE,
        expiration=datetime_to_ripple_time(expires),
    )
    return _submit(issuer, tx)


def accept_passport(agent: Wallet, issuer_address: str) -> dict:
    """AGENT accepts the passport; it isn't usable until this happens."""
    tx = CredentialAccept(
        account=agent.classic_address,
        issuer=issuer_address,
        credential_type=PASSPORT_TYPE,
    )
    return _submit(agent, tx)


def revoke_passport(issuer: Wallet, agent_address: str) -> dict:
    """KILL SWITCH: the issuer deletes the agent's passport."""
    tx = CredentialDelete(
        account=issuer.classic_address,
        subject=agent_address,
        issuer=issuer.classic_address,
        credential_type=PASSPORT_TYPE,
    )
    return _submit(issuer, tx)


def _get_passport_node(client, agent_address: str, issuer_address: str):
    """Fetch the Credential ledger entry, or None if it doesn't exist."""
    response = client.request(
        LedgerEntry(
            credential=LedgerCredential(
                subject=agent_address, issuer=issuer_address, credential_type=PASSPORT_TYPE
            ),
            ledger_index="validated",
        )
    )
    if not response.is_successful():  # e.g. entryNotFound
        return None
    return response.result


def get_passport_id(client, agent_address: str, issuer_address: str):
    """Return the passport's ledger index (its ID, used in payments), or None if not found."""
    node = _get_passport_node(client, agent_address, issuer_address)
    return node["index"] if node else None


def get_passport_status(client, agent_address: str, issuer_address: str) -> dict:
    """Return {"status": "not found" | "issued-not-accepted" | "active" | "expired", "expires": datetime|None}."""
    result = _get_passport_node(client, agent_address, issuer_address)
    if result is None:
        return {"status": "not found", "expires": None}
    node = result["node"]
    expiration = node.get("Expiration")
    expires = ripple_time_to_datetime(expiration) if expiration is not None else None
    if not node.get("Flags", 0) & LSF_ACCEPTED:
        status = "issued-not-accepted"
    elif expires is not None and expires <= datetime.now(timezone.utc):
        status = "expired"
    else:
        status = "active"
    return {"status": status, "expires": expires}


def setup_verified_merchant(merchant: Wallet, issuer_address: str) -> list[dict]:
    """Make the merchant accept payments ONLY from holders of the issuer's passport.

    Step 1: turn on Deposit Authorization. Step 2: preauthorize the passport type.
    Each step is skipped if already in place. Returns one dict per step performed.
    """
    client = get_client()
    results = []

    info = client.request(AccountInfo(account=merchant.classic_address, ledger_index="validated"))
    lsf_deposit_auth = 0x01000000
    if not info.result["account_data"].get("Flags", 0) & lsf_deposit_auth:
        results.append({"step": "enable deposit auth", **_submit(
            merchant,
            AccountSet(account=merchant.classic_address, set_flag=AccountSetAsfFlag.ASF_DEPOSIT_AUTH),
        )})

    # Is the credential preauthorization already there? Check the account's DepositPreauth objects.
    objects = client.request(
        AccountObjects(account=merchant.classic_address, type="deposit_preauth", ledger_index="validated")
    ).result.get("account_objects", [])
    already = any(
        any(
            c["Credential"]["Issuer"] == issuer_address and c["Credential"]["CredentialType"].upper() == PASSPORT_TYPE.upper()
            for c in obj.get("AuthorizeCredentials", [])
        )
        for obj in objects
    )
    if not already:
        results.append({"step": "preauthorize passport type", **_submit(
            merchant,
            DepositPreauth(
                account=merchant.classic_address,
                authorize_credentials=[PreauthCredential(issuer=issuer_address, credential_type=PASSPORT_TYPE)],
            ),
        )})
    return results


def pay(agent: Wallet, merchant_address: str, xrp_amount, passport_id=None, memo=None) -> dict:
    """AGENT pays the merchant in XRP, optionally showing its passport and a reason (memo).

    Never raises on a refused payment: the result code is returned so callers can show it.
    """
    kwargs = {}
    if passport_id:
        kwargs["credential_ids"] = [passport_id]
    if memo:
        kwargs["memos"] = [Memo(memo_data=str_to_hex(memo))]
    tx = Payment(
        account=agent.classic_address,
        destination=merchant_address,
        amount=xrp_to_drops(xrp_amount),
        **kwargs,
    )
    return _submit(agent, tx)
