"""Create and fund the four data-vendor wallets (only if missing from .env).

FX, CRYPTO and NEWS become "verified-only": the XRP Ledger refuses payments from
anyone without the ISSUER's passport. ALPHA is the scam vendor and accepts anyone.
Secrets are saved to .env and are NEVER printed.
"""
import os

import _path  # noqa: F401  (makes `agentguard` importable)
from dotenv import load_dotenv, set_key
from xrpl.account import get_balance
from xrpl.wallet import Wallet, generate_faucet_wallet

from agentguard.xrpl_core import get_client, load_wallets, setup_verified_merchant

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_PATH)
client = get_client()
TX = "https://testnet.xrpl.org/transactions/"

VERIFIED_ONLY = {"FX": True, "CRYPTO": True, "NEWS": True, "ALPHA": False}
issuer_address = load_wallets()[1].classic_address

for name, verified in VERIFIED_ONLY.items():
    role = f"VENDOR_{name}"
    secret = os.getenv(f"XRPL_{role}_SECRET")
    if secret:
        wallet = Wallet.from_seed(secret)
        print(f"{role}: already in .env, reusing it")
    else:
        wallet = generate_faucet_wallet(client)  # funded by the testnet faucet
        set_key(ENV_PATH, f"XRPL_{role}_ADDRESS", wallet.classic_address)
        set_key(ENV_PATH, f"XRPL_{role}_SECRET", wallet.seed)
        print(f"{role}: created and saved to .env")
    balance = int(get_balance(wallet.classic_address, client)) / 1_000_000
    print(f"  address: {wallet.classic_address}  balance: {balance} XRP")
    print(f"  explorer: https://testnet.xrpl.org/accounts/{wallet.classic_address}")
    if verified:
        steps = setup_verified_merchant(wallet, issuer_address)
        if not steps:
            print("  verified-only: already set up")
        for s in steps:
            print(f"  {s['step']}: {s['code']} {TX}{s['hash']}")
    else:
        print("  open vendor (scam): no passport required, deposit auth NOT enabled")
