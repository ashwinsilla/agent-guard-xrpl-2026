"""Make the merchant 'verified-only': deposit auth on + passport type preauthorized."""
import _path  # noqa: F401
from agentguard.xrpl_core import *

agent, issuer, merchant = load_wallets()
steps = setup_verified_merchant(merchant, issuer.classic_address)
if not steps:
    print("Merchant was already verified-only. Nothing to do.")
for s in steps:
    print(f"{s['step']}: {s['code']} https://testnet.xrpl.org/transactions/{s['hash']}")
