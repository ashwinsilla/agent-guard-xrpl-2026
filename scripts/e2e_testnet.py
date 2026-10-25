"""End-to-end run of the whole story against the REAL testnets; writes every hash into PROOF.md.

    .venv/bin/python scripts/e2e_testnet.py

Starts the merchants in-process, then: reset -> agent run (co-signed purchases, attack, freeze)
-> Acme confirms (revoke, refusal proofs, float returned) -> no-passport payment refused
-> re-issue. Each result is compared with what the ledger SHOULD say.
"""
import datetime
import threading
import time
from decimal import Decimal

import _path  # noqa: F401  (makes `agentguard` importable)
import requests
import uvicorn

from agentguard import ap4m, config, demo, events, killswitch, passport, state
from merchants.app import app

rows = []  # (step, expected, actual, link)


def record(step: str, expected: str, actual: str, link: str | None = None) -> None:
    rows.append((step, expected, actual, link or ""))
    print(f"{'PASS' if expected == actual else 'FAIL'}  {step}: expected {expected}, got {actual}")


def first(kind: str, contains: str, since: int) -> dict | None:
    return next((e for e in events.read_since(since) if e["kind"] == kind and contains in e["title"]), None)


server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=config.MERCHANT_PORT, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(50):
    try:
        if requests.get(f"{config.MERCHANT_BASE}/health", timeout=1).ok:
            break
    except requests.RequestException:
        time.sleep(0.2)

def auto_approver() -> None:
    """Stand-in for the human at the dashboard: approves any held purchase (e.g. the deeper news pull)."""
    from agentguard import checker
    while True:
        for pid in list(state.load()["held"]):
            checker.approve_held(pid)
        time.sleep(1)


threading.Thread(target=auto_approver, daemon=True).start()
record("Reset: passport active", "active", demo.reset_demo()["status"])
from agents import treasury_analyst  # noqa: E402  (imported after the server is up)
treasury_analyst.run()

for label, needle in [("FX Rates paid, co-signed by agent + AgentGuard", "FX Rates"),
                      ("Crypto Prices paid, co-signed by agent + AgentGuard", "Crypto Prices")]:
    ev = first("cosigner", needle, 0)
    record(label, "tesSUCCESS", ev["title"].split()[-1] if ev else "missing", ev and ev.get("link"))
ap4m.flush()  # the merchant redeems + settles vouchers in the background
ev = first("voucher_redeemed", "News", 0)
record(f"News voucher redeemed on the AP4M PaymentLedger ({ap4m.mode_label()})", "VoucherRedeemed",
       "VoucherRedeemed" if ev else "missing", ev and ev.get("link"))
ev = first("settlement", "", 0)
record(f"RLUSD settled to the merchant payout wallet ({ap4m.mode_label()})", "settled",
       "settled" if ev else "missing", ev and ev.get("link"))
ev = next((e for e in events.read_since(0) if e["kind"] == "settlement" and "receipt" in e["title"]), None)
if ev:
    record("AP4M verifiable receipt (channel + claim + payout)", "receipt", "receipt", ev.get("link"))
over = ap4m.prove_over_cap()
record(f"Voucher above the channel cap ({ap4m.mode_label()})", "rejected", "rejected" if over["rejected"] else "accepted")
ev = first("checker", "Premium Alpha", 0)
record("Attacker purchase refused by AgentGuard", "BLOCK", ev["decision"] if ev else "missing")
ev = first("enforcement", "agent-only", 0)
record("Agent pays the attacker alone (no AgentGuard signature)", "tefBAD_QUORUM", ev["code"] if ev else "missing")
record("AgentGuard frozen", "True", str(state.load()["frozen"]))

mark = events.read_since(0)[-1]["id"]
killswitch.confirm_revoke()
ev = first("passport", "REVOKED", mark)
record("Acme revokes the passport (CredentialDelete, approver key)", "tesSUCCESS",
       ev["title"].split()[-1] if ev else "missing", ev and ev.get("link"))
ev = first("enforcement", "old passport", mark)
record("Payment to FX Rates with the old passport", "tecBAD_CREDENTIALS",
       ev["title"].split(": ")[1].split()[0] if ev else "missing", ev and ev.get("link"))
ev = first("killswitch", "returned to Acme", mark)
record("Float swept back to Acme's treasury", "tesSUCCESS", ev["title"].split()[-1] if ev else "missing", ev and ev.get("link"))

# Without any passport, even a fully signed payment to a verified-only merchant is refused.
demo.refill_float()
state.update(last_credential_id=None)  # forget the old passport ID: this payment presents none
r = passport.pay_with_passport(config.env("XRPL_VENDOR_FX_ADDRESS"), Decimal("0.05"), memo="no passport at all")
record("Payment to FX Rates with NO passport", "tecNO_PERMISSION", r["code"], config.xrpl_tx_link(r["hash"]))

record("Acme re-issues the passport (one approval)", "active", demo.reissue_passport()["status"])

stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
lines = [f"\n## End-to-end run {stamp} (AP4M {ap4m.mode_label()})\n", "| Step | Expected | Ledger said | Proof |",
         "|---|---|---|---|"]
lines += [f"| {s} | {e} | {a} | {f'[explorer]({link})' if link else '-'} |" for s, e, a, link in rows]
with open(f"{config.ROOT}/PROOF.md", "a") as f:
    f.write("\n".join(lines) + "\n")
print(f"\n{sum(e == a for _, e, a, _ in rows)}/{len(rows)} steps as expected; written to PROOF.md")
