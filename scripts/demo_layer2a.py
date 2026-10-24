"""Layer 2a demo: the treasury agent buys data from pay-per-call vendors.

One command runs everything: it starts the vendor server (uvicorn, 127.0.0.1:8000) in a
background thread, makes sure the agent has an active passport, then runs the scenarios.
"""
import threading
import time

import _path  # noqa: F401  (makes `agentguard` importable)
import requests
import uvicorn

from agentguard import xrpl_core as core
from agentguard.agent_client import buy, simple_policy
from agentguard.vendors import app

BASE = "http://127.0.0.1:8000"
agent, issuer, merchant = core.load_wallets()
A, I = agent.classic_address, issuer.classic_address
client = core.get_client()
summary = []  # (step, expected, actual, PASS/FAIL)


def start_server():
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):  # wait up to ~10s for /health
        try:
            if requests.get(BASE + "/health", timeout=1).status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.2)
    raise SystemExit("Vendor server did not start")


def ensure_passport():
    """Make sure the agent has an ACTIVE passport (clearing a half-done one first)."""
    if core.get_passport_status(client, A, I)["status"] == "active":
        return
    if core.get_passport_id(client, A, I):
        core.revoke_passport(issuer, A)
    core.issue_passport(issuer, A)
    core.accept_passport(agent, I)


def report(step, label, expected, result, ok):
    """Print one scenario's result and remember it for the summary table."""
    actual = result["status"] + (f" ({result.get('code') or result.get('reason')})" if result["status"] not in ("paid", "blocked") else "")
    print(f"{step}. {label}\n   status: {actual}")
    for name, link in result.get("links", {}).items():
        print(f"   {name}: {link}")
    summary.append((step, expected, actual, "PASS" if ok else "FAIL"))


start_server()
print("Vendor server is up. Passport status:", core.get_passport_status(client, A, I)["status"])
ensure_passport()
print("Passport ready:", core.get_passport_status(client, A, I)["status"], "\n")

# 1-3: paid purchases from the three verified vendors
bought = {}
for step, key, path, reason in [("1", "fx", "/fx/rates", "FX rates for daily risk report"),
                                ("2", "crypto", "/crypto/prices", "Crypto prices for daily risk report"),
                                ("3", "news", "/news/sentiment", "News sentiment for daily risk report")]:
    r = buy(BASE + path, reason, simple_policy, agent=agent)
    bought[key] = r
    ok = r["status"] == "paid"
    report(step, f"Buy {r['purchase']['vendor'] if 'purchase' in r else key}", "paid", r, ok)
    if ok:
        print("   data source:", r["data"]["source"], "| amount (drops):", r["receipt"]["amount"])

# 4: scam vendor, blocked by the policy with no payment made
r = buy(BASE + "/alpha/signals", "insider signals", simple_policy, agent=agent)
report("4", "Premium Alpha Signals (scam, 50 XRP)", "blocked", r, r["status"] == "blocked" and "payment_tx" not in r["links"])

# 5: KILL SWITCH then try again
print("5. KILL SWITCH: revoking passport")
rv = core.revoke_passport(issuer, A)
print("   CredentialDelete:", rv["code"], "https://testnet.xrpl.org/transactions/" + str(rv["hash"]))
r = buy(BASE + "/fx/rates", "FX rates for daily risk report", simple_policy, agent=agent)
report("5", "Buy FX rates after revoke", "refused (ledger or vendor)", r,
       r["status"] in ("refused_by_ledger", "refused_by_vendor"))

# 6: re-issue
ensure_passport()
st = core.get_passport_status(client, A, I)["status"]
print(f"6. Passport re-issued: {st}")
summary.append(("6", "passport active again", st, "PASS" if st == "active" else "FAIL"))

# 7: replay test: pay for a NEW invoice's resource but present the OLD (step 1) tx hash
old_hash = bought["fx"]["tx_hash"]
requests.get(BASE + "/fx/rates")  # a fresh 402 / invoice we deliberately don't pay
replay = requests.get(BASE + "/fx/rates", headers={"X-PAYMENT-TX": old_hash})
reason = replay.json().get("reason")
print(f"7. Replay of step-1 tx hash: HTTP {replay.status_code} - {reason}")
summary.append(("7", "replay rejected", f"HTTP {replay.status_code} ({reason})",
                "PASS" if replay.status_code == 402 and "already used" in str(reason) else "FAIL"))

print("\nSummary")
print(f"{'Step':<5}{'Expected':<28}{'Actual':<62}Result")
for s in summary:
    print(f"{s[0]:<5}{s[1]:<28}{s[2]:<62}{s[3]}")

fx, cr, nw = (bought[k].get("data") for k in ("fx", "crypto", "news"))
if fx and cr and nw:
    print("\nRisk report preview")
    print("  EUR/USD:", fx["rates"]["EUR/USD"], "| USD/JPY:", fx["rates"]["USD/JPY"])
    print("  XRP/USD:", cr["prices"]["XRP/USD"], "| BTC/USD:", cr["prices"]["BTC/USD"])
    print("  News risk score:", nw["risk_score"], "/ 100 from", len(nw["headlines"]), "headlines")
