"""KILL SWITCH: revoke the agent's passport, then show the new status."""
import _path  # noqa: F401
from agentguard.xrpl_core import *

agent, issuer, merchant = load_wallets()
r = revoke_passport(issuer, agent.classic_address)
print("CredentialDelete:", r["code"], "https://testnet.xrpl.org/transactions/" + str(r["hash"]))
print("Status:", get_passport_status(get_client(), agent.classic_address, issuer.classic_address))
