"""Print the agent's current passport status."""
import _path  # noqa: F401
from agentguard.xrpl_core import *

agent, issuer, merchant = load_wallets()
print("Passport status:", get_passport_status(get_client(), agent.classic_address, issuer.classic_address))
