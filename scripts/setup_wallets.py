"""Set up the three testnet wallets: AGENT, ISSUER and MERCHANT.

- AGENT is created by you beforehand; we only CHECK that its secret matches its address.
- ISSUER and MERCHANT are created and funded from the testnet faucet,
  but only if their secret isn't already saved in .env.
Secrets are saved to .env and are NEVER printed.
Run from the project root:  .venv/bin/python scripts/setup_wallets.py
"""
import os
import sys

from dotenv import load_dotenv, set_key
from xrpl.account import get_balance
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_PATH)

client = JsonRpcClient(os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234/"))


def show(role: str, wallet: Wallet) -> None:
    """Print address, balance and explorer link (never the secret)."""
    balance = int(get_balance(wallet.classic_address, client)) / 1_000_000
    print(f"{role}: {wallet.classic_address}")
    print(f"  balance: {balance} XRP")
    print(f"  explorer: https://testnet.xrpl.org/accounts/{wallet.classic_address}")


# --- AGENT: must already exist in .env ---
agent_secret = os.getenv("XRPL_AGENT_SECRET")
if not agent_secret:
    sys.exit("XRPL_AGENT_SECRET is missing from .env. Please add it yourself, then re-run.")
agent = Wallet.from_seed(agent_secret)
if agent.classic_address != os.getenv("XRPL_AGENT_ADDRESS"):
    sys.exit("XRPL_AGENT_SECRET does not match XRPL_AGENT_ADDRESS in .env. Please check them.")
print("AGENT secret matches address: OK")
show("AGENT", agent)

# --- ISSUER and MERCHANT: create + fund only if missing ---
for role in ("ISSUER", "MERCHANT"):
    secret = os.getenv(f"XRPL_{role}_SECRET")
    if secret:
        wallet = Wallet.from_seed(secret)
        print(f"{role}: already in .env, reusing it")
    else:
        wallet = generate_faucet_wallet(client)  # new wallet funded by the testnet faucet
        set_key(ENV_PATH, f"XRPL_{role}_ADDRESS", wallet.classic_address)
        set_key(ENV_PATH, f"XRPL_{role}_SECRET", wallet.seed)
        print(f"{role}: created and saved to .env")
    show(role, wallet)
