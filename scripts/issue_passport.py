"""Issue the agent a passport and have the agent accept it."""
import _path  # noqa: F401  (makes `agentguard` importable)
from agentguard.xrpl_core import *

EXPLORER = "https://testnet.xrpl.org/transactions/"
agent, issuer, merchant = load_wallets()
client = get_client()

r1 = issue_passport(issuer, agent.classic_address)
print("CredentialCreate:", r1["code"], EXPLORER + str(r1["hash"]))
r2 = accept_passport(agent, issuer.classic_address)
print("CredentialAccept:", r2["code"], EXPLORER + str(r2["hash"]))
print("Status:", get_passport_status(client, agent.classic_address, issuer.classic_address))
