"""Idempotently set up the XRPL merchant accounts so the LEDGER enforces passports.

For each honest merchant account this turns on Deposit Authorization and preauthorizes the
Acme passport type. Safe to run again: steps that are already done are skipped.
The scam merchant (ALPHA) is deliberately NOT set up: it will never ask for passports.
Run:  .venv/bin/python scripts/setup_merchant.py
"""
import os

import _path  # noqa: F401  (makes `agentguard` importable)
from xrpl.wallet import Wallet

from agentguard import xrpl_core as core
from agentguard.config import xrpl_tx_link
from agentguard.passport import credential_type

ACCOUNTS = ["MERCHANT", "VENDOR_FX", "VENDOR_CRYPTO", "VENDOR_NEWS"]

issuer = core.load_wallets()[1].classic_address
for role in ACCOUNTS:
    secret = os.getenv(f"XRPL_{role}_SECRET")
    if not secret:
        print(f"{role}: no secret in .env yet (run scripts/setup_vendors.py first), skipping")
        continue
    wallet = Wallet.from_seed(secret)
    # setup_verified_merchant uses the SMALL passport type, which is what we issue by default.
    assert core.PASSPORT_TYPE == credential_type("SMALL")
    steps = core.setup_verified_merchant(wallet, issuer)
    print(f"{role} ({wallet.classic_address}): " + ("already set up" if not steps else ""))
    for s in steps:
        print(f"  {s['step']}: {s['code']} {xrpl_tx_link(s['hash'])}")
