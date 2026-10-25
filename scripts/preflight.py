"""Preflight: a green/red checklist to run before the demo. Changes nothing.

    .venv/bin/python scripts/preflight.py

[OK]   = ready    [WARN] = works, but in a fallback mode (MOCK / OFFLINE / public RPC)    [FAIL] = fix this first
Only variable NAMES are printed, never their values.
"""
import os

import _path  # noqa: F401  (makes `agentguard` importable)
from xrpl.models.requests import AccountObjects

from agentguard import ap4m, config, llm, multisig, passport, xrpl_core
from agentguard.passport import credential_type

results = []


def check(label: str, ok: bool | None, detail: str = "") -> None:
    """ok=True -> OK, ok=None -> WARN, ok=False -> FAIL."""
    tag = {True: "\033[32m[OK]  \033[0m", None: "\033[33m[WARN]\033[0m", False: "\033[31m[FAIL]\033[0m"}[ok]
    results.append(ok)
    print(f"{tag} {label}" + (f": {detail}" if detail else ""))


REQUIRED = ["XRPL_AGENT_ADDRESS", "XRPL_ISSUER_SECRET", "XRPL_AGENT_SIGNER_SECRET", "XRPL_AGENTGUARD_SECRET",
            "XRPL_APPROVER_SECRET", "XRPL_VENDOR_FX_SECRET", "XRPL_VENDOR_CRYPTO_SECRET", "XRPL_VENDOR_ALPHA_ADDRESS",
            "AGENT_EVM_PRIVATE_KEY", "MERCHANT_EVM_PRIVATE_KEY"]
missing = [n for n in REQUIRED if not os.getenv(n)]
check("Required .env variables", not missing, ("missing: " + ", ".join(missing)) if missing else f"{len(REQUIRED)} present")

check("XRPL RPC", True if config.using_quicknode() else None,
      "Quicknode endpoint" if config.using_quicknode() else "public testnet server (set XRPL_RPC_URL to your Quicknode URL)")

try:
    agent, issuer, _ = xrpl_core.load_wallets()
    info = multisig.account_info(agent.classic_address)
    sl = info.get("_signer_list") or {}
    weights = sorted(e["SignerEntry"]["SignerWeight"] for e in sl.get("SignerEntries", []))
    check("Agent signer list (agent 1, AgentGuard 1, approver 2; quorum 2)",
          weights == [1, 1, 2] and sl.get("SignerQuorum") == 2, f"weights {weights}, quorum {sl.get('SignerQuorum')}")
    check("Agent master key disabled", bool(info.get("Flags", 0) & multisig.LSF_DISABLE_MASTER),
          "run scripts/setup_agent_wallet.py if not")
    spend = multisig.spendable_xrp(agent.classic_address)
    check("Agent float", True if spend >= 9 else None, f"{spend:.2f} XRP spendable (reset_demo refills to 10)")
    regular = multisig.account_info(issuer.classic_address).get("RegularKey")
    check("Acme approver key = issuer's regular key", regular == os.getenv("XRPL_APPROVER_ADDRESS"))
    tre = int(multisig.account_info(issuer.classic_address).get("Balance", 0)) / 1e6
    check("Acme treasury balance", tre > 15, f"{tre:.2f} XRP")
    pp = passport.get_passport_status()
    check("Agent passport", True if pp["status"] == "active" else None,
          f"{pp['status']} (reset_demo / Re-issue makes it active)")
    for role in ("VENDOR_FX", "VENDOR_CRYPTO"):
        addr = os.getenv(f"XRPL_{role}_ADDRESS")
        flags = multisig.account_info(addr).get("Flags", 0)
        objs = xrpl_core.get_client().request(AccountObjects(account=addr, type="deposit_preauth",
                                                             ledger_index="validated")).result.get("account_objects", [])
        pre = any(c["Credential"]["CredentialType"].upper() == credential_type("SMALL").upper()
                  for o in objs for c in o.get("AuthorizeCredentials", []))
        check(f"{role}: Deposit Authorization + passport preauthorized", bool(flags & 0x01000000) and pre,
              "run scripts/setup_merchant.py if not")
except Exception as exc:
    check("XRP Ledger checks", False, f"{type(exc).__name__}: {str(exc)[:120]}")

m = ap4m.mode()
check("Mastercard AP4M", True if m == "live" else None,
      "LIVE (signed in)" if m == "live" else f"MOCK: {ap4m.mock_reason()[:120]}")
check("Amazon Bedrock (checker AI + agent)", True if llm.available() else None,
      f"model {llm.model_id()}" if llm.available() else f"LLM OFFLINE: {llm.offline_reason()[:100]}")
check("Kill switch closes the real AP4M channel", None if not config.CLOSE_REAL_CHANNEL else True,
      "KILL_SWITCH_CLOSE_REAL_CHANNEL=" + str(config.CLOSE_REAL_CHANNEL).lower() + " (false = rehearsal)")

fails = results.count(False)
print(f"\n{'READY' if not fails else 'NOT READY'}: {results.count(True)} ok, {results.count(None)} warnings, {fails} failures")
