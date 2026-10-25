"""Turn the agent's wallet into a CO-SIGNED wallet (run once; safe to run again).

What it does, step by step (each step is skipped if already done):
  1. Creates three signer keys if they're not in .env yet: AGENT_SIGNER, AGENTGUARD and APPROVER.
     (Keys only: signers don't need funded accounts. Secrets go to .env and are NEVER printed.)
  2. Makes the APPROVER the issuer's (Acme's) "regular key", so Acme issues and revokes passports
     with its approver key. In production that key lives on a Ledger device.
  3. Sends everything above a 10 XRP float from the agent back to Acme's treasury (the issuer),
     so the agent only ever holds a small daily float.
  4. Puts a signer list on the agent wallet: agent-signer 1, AgentGuard 1, approver 2, quorum 2.
  5. Disables the agent's master key, so from now on the agent can't sign anything alone.
     (Reversible only with Acme's approver key, which stays in .env.)
Run from the project root:  .venv/bin/python scripts/setup_agent_wallet.py
"""
import os

import _path  # noqa: F401  (makes `agentguard` importable)
from dotenv import set_key
from xrpl.models.transactions import (
    AccountSet, AccountSetAsfFlag, Payment, SetRegularKey, SignerEntry, SignerListSet,
)
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet

from agentguard import multisig, xrpl_core as core
from agentguard.config import ROOT, xrpl_tx_link

ENV_PATH = os.path.join(ROOT, ".env")
FLOAT_XRP = 10


def show(label: str, r: dict) -> None:
    print(f"  {label}: {r['code']}  {xrpl_tx_link(r['hash'])}")


# 1. signer keys ------------------------------------------------------------------------
for role in multisig.WEIGHTS:
    if os.getenv(f"XRPL_{role}_SECRET"):
        print(f"1. {role}: already in .env")
        continue
    w = Wallet.create()
    set_key(ENV_PATH, f"XRPL_{role}_ADDRESS", w.classic_address)  # adds new lines only
    set_key(ENV_PATH, f"XRPL_{role}_SECRET", w.seed)
    os.environ[f"XRPL_{role}_ADDRESS"], os.environ[f"XRPL_{role}_SECRET"] = w.classic_address, w.seed
    print(f"1. {role}: created {w.classic_address} (secret saved to .env)")

agent, issuer, _ = core.load_wallets()
approver = multisig.approver()

# 2. approver = issuer's regular key ------------------------------------------------------
if multisig.account_info(issuer.classic_address).get("RegularKey") == approver.classic_address:
    print("2. Approver is already Acme's regular key")
else:
    print("2. Setting the approver as Acme's regular key")
    show("SetRegularKey", core._submit(issuer, SetRegularKey(account=issuer.classic_address,
                                                             regular_key=approver.classic_address)))

info = multisig.account_info(agent.classic_address)
master_disabled = bool(info.get("Flags", 0) & multisig.LSF_DISABLE_MASTER)

# 3. keep only a small float on the agent ----------------------------------------------------
spendable = multisig.spendable_xrp(agent.classic_address)
if master_disabled:
    print(f"3. Master key already disabled; agent can spend {spendable:.2f} XRP (top up via reset_demo)")
elif spendable > FLOAT_XRP + 0.5:
    excess = round(spendable - FLOAT_XRP - 0.1, 6)  # 0.1 XRP margin for fees
    print(f"3. Returning {excess} XRP to Acme's treasury (agent keeps a {FLOAT_XRP} XRP float)")
    show("Payment", core._submit(agent, Payment(account=agent.classic_address,
                                                destination=issuer.classic_address, amount=xrp_to_drops(excess))))
else:
    print(f"3. Agent already holds a small float ({spendable:.2f} XRP)")

# 4. signer list -------------------------------------------------------------------------------
wanted = {os.environ[f"XRPL_{r}_ADDRESS"]: wgt for r, wgt in multisig.WEIGHTS.items()}
current = info.get("_signer_list")
have = {e["SignerEntry"]["Account"]: e["SignerEntry"]["SignerWeight"] for e in (current or {}).get("SignerEntries", [])}
if current and have == wanted and current.get("SignerQuorum") == multisig.QUORUM:
    print("4. Signer list already in place")
else:
    print("4. Setting the signer list: agent-signer 1, AgentGuard 1, approver 2, quorum 2")
    tx = SignerListSet(account=agent.classic_address, signer_quorum=multisig.QUORUM,
                       signer_entries=[SignerEntry(account=a, signer_weight=w) for a, w in wanted.items()])
    if master_disabled:  # changing it later needs Acme's approval
        show("SignerListSet", multisig.sign_and_submit(tx, [approver]))
    else:
        show("SignerListSet", core._submit(agent, tx))

# 5. disable the master key ------------------------------------------------------------------
if master_disabled:
    print("5. Master key already disabled: the agent can't sign alone")
else:
    print("5. Disabling the agent's master key")
    show("AccountSet asfDisableMaster", core._submit(agent, AccountSet(
        account=agent.classic_address, set_flag=AccountSetAsfFlag.ASF_DISABLE_MASTER)))

final = multisig.account_info(agent.classic_address)
print(f"\nAgent {agent.classic_address}: master disabled = {bool(final.get('Flags', 0) & multisig.LSF_DISABLE_MASTER)}, "
      f"spendable = {multisig.spendable_xrp(agent.classic_address):.2f} XRP")
