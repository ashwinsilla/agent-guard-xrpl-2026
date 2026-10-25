"""One command for the whole demo: preflight checks, merchants and dashboard.

    .venv/bin/python run_demo.py              # then open http://127.0.0.1:8080
    .venv/bin/python run_demo.py --no-check   # skip the preflight checklist

Merchants (port 8000) and the dashboard (port 8080) run in ONE process, so they share the
same state file safely. Drive the 3-minute demo from the dashboard buttons (see DEMO_SCRIPT.md).
"""
import subprocess
import sys
import threading
import time

import requests
import uvicorn

from agentguard import config, ledger_feed
from dashboard.app import app as dashboard_app
from merchants.app import app as merchants_app


def serve(app, port: int) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()


if __name__ == "__main__":
    if "--no-check" not in sys.argv:
        subprocess.run([sys.executable, "scripts/preflight.py"], cwd=config.ROOT)
    serve(merchants_app, config.MERCHANT_PORT)
    serve(dashboard_app, config.DASHBOARD_PORT)
    ledger_feed.start()  # validated transactions on our accounts, straight from the ledger
    for _ in range(50):  # wait for the merchants to answer
        try:
            if requests.get(f"{config.MERCHANT_BASE}/health", timeout=1).ok:
                break
        except requests.RequestException:
            time.sleep(0.2)
    print(f"\nMerchants:  {config.MERCHANT_BASE}/catalog")
    print(f"Dashboard:  http://127.0.0.1:{config.DASHBOARD_PORT}   (Ctrl+C to stop)\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")
