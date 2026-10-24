"""Layer 1 proof: the XRP Ledger itself blocks agents without a valid passport.

Steps: (1) set up verified merchant, (2) pay with no passport -> refused,
(3) issue passport, pay -> success, (4) KILL SWITCH then pay with old passport ID -> refused,
(5) re-issue passport, pay -> success, (6) summary table.
"""
import _path  # noqa: F401
from agentguard.xrpl_core import *

TX = "https://testnet.xrpl.org/transactions/"
agent, issuer, merchant = load_wallets()
client = get_client()
A, I, M = agent.classic_address, issuer.classic_address, merchant.classic_address
summary = []  # rows of (step, expected, actual)


def show(label, r):
    print(f"   {label}: {r['code']}  {TX}{r['hash']}" if r["hash"] else f"   {label}: {r['code']}")


def record(step, expected, r):
    """Store the result; expected is 'success' or 'fail' (any non-tesSUCCESS code)."""
    ok = (r["code"] == "tesSUCCESS") == (expected == "success")
    summary.append((step, "tesSUCCESS" if expected == "success" else "refused (not tesSUCCESS)", r["code"], "PASS" if ok else "FAIL"))


def issue_and_accept():
    show("CredentialCreate", issue_passport(issuer, A))
    show("CredentialAccept", accept_passport(agent, I))
    return get_passport_id(client, A, I)


print("1. Ensure merchant is verified-only")
steps = setup_verified_merchant(merchant, I)
for s in steps:
    show(s["step"], s)
if not steps:
    print("   already set up")

print("2. Pay 1 XRP WITHOUT a passport (expect refusal)")
if get_passport_id(client, A, I):
    show("Revoke leftover passport", revoke_passport(issuer, A))
r = pay(agent, M, 1)
show("Payment", r)
record("2 pay without passport", "fail", r)

print("3. Issue passport, pay WITH it (expect success)")
old_id = issue_and_accept()
print("   passport ID:", old_id)
r = pay(agent, M, 1, passport_id=old_id, memo="FX rates for daily risk report")
show("Payment", r)
record("3 pay with passport", "success", r)

print("4. KILL SWITCH: revoke, then pay with the OLD passport ID (expect refusal)")
show("CredentialDelete", revoke_passport(issuer, A))
r = pay(agent, M, 1, passport_id=old_id, memo="FX rates for daily risk report")
show("Payment", r)
record("4 pay after revoke", "fail", r)

print("5. Re-issue passport, pay again (expect success)")
new_id = issue_and_accept()
r = pay(agent, M, 1, passport_id=new_id, memo="FX rates for daily risk report")
show("Payment", r)
record("5 pay after re-issue", "success", r)

print("6. Summary")
print(f"{'Step':<24}{'Expected':<28}{'Actual':<22}Result")
for row in summary:
    print(f"{row[0]:<24}{row[1]:<28}{row[2]:<22}{row[3]}")
