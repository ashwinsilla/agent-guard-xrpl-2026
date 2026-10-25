"""Put everything back to the START of the demo so it can be run again and again.

What it does:
  1. clears strikes, the revoked flag, held purchases and the event log (the voucher running
     total is KEPT, because AP4M vouchers must continue from the on-chain total);
  2. makes sure the agent has an ACTIVE passport (re-issues + accepts it if needed);
  3. re-opens the (simulated) channel if the last kill switch closed it.
Run:  .venv/bin/python scripts/reset_demo.py
"""
import _path  # noqa: F401  (makes `agentguard` importable)
from agentguard.demo import reset_demo

if __name__ == "__main__":
    s = reset_demo()
    print(f"Ready. Passport: {s['status']} (level {s['level']}), expires {s['expires']}")
