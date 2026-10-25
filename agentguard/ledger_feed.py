"""Live feed straight from the XRP Ledger: every validated transaction touching our accounts.

Subscribes over WebSocket to the agent, Acme (issuer/treasury) and the vendors, and writes one event
per validated transaction to the dashboard feed. This is independent proof: the dashboard shows what
the LEDGER saw, not just what our code says it did.

Uses XRPL_WS_URL (set it to the Quicknode WebSocket endpoint); falls back to the public testnet server.
Started by run_demo.py in a background thread; reconnects if the connection drops.
"""
import os
import threading
import time

from xrpl.clients import WebsocketClient
from xrpl.models.requests import Subscribe

from agentguard import config, events

PUBLIC_WS = "wss://s.altnet.rippletest.net:51233"
ROLES = ["AGENT", "ISSUER", "VENDOR_FX", "VENDOR_CRYPTO", "VENDOR_ALPHA"]


def _names() -> dict:
    return {os.getenv(f"XRPL_{r}_ADDRESS"): r.replace("VENDOR_", "").lower() for r in ROLES if os.getenv(f"XRPL_{r}_ADDRESS")}


def _describe(tx: dict, names: dict) -> str:
    who = names.get(tx.get("Account"), (tx.get("Account") or "")[:8])
    kind = tx.get("TransactionType", "?")
    if kind == "Payment":
        dest = names.get(tx.get("Destination"), (tx.get("Destination") or "")[:8])
        amt = tx.get("DeliverMax", tx.get("Amount"))
        amount = f"{int(amt) / 1e6:g} XRP" if isinstance(amt, str) else "tokens"
        signed = f", {len(tx['Signers'])} signature(s)" if tx.get("Signers") else ""
        return f"Payment {who} -> {dest}: {amount}{signed}"
    return f"{kind} by {who}"


def _run(url: str) -> None:
    names = _names()
    while True:
        try:
            with WebsocketClient(url) as client:
                client.send(Subscribe(accounts=list(names)))
                for msg in client:
                    if msg.get("type") != "transaction" or not msg.get("validated"):
                        continue
                    tx = msg.get("tx_json") or msg.get("transaction") or {}
                    tx_hash = msg.get("hash") or tx.get("hash")
                    result = msg.get("meta", {}).get("TransactionResult") or msg.get("engine_result", "")
                    events.emit("ledger_stream", f"On-ledger ({'Quicknode' if url != PUBLIC_WS else 'public node'}): "
                                f"{_describe(tx, names)}: {result}", "good" if result == "tesSUCCESS" else "warn",
                                tx_hash=tx_hash, link=config.xrpl_tx_link(tx_hash) if tx_hash else None, mode="LIVE")
        except Exception as exc:  # network blip: wait and reconnect
            config.log.warning("ledger feed reconnecting: %s", exc)
            time.sleep(5)


def start() -> None:
    """Start the feed in the background (no-op if LEDGER_FEED=false)."""
    if not config.flag("LEDGER_FEED", True):
        return
    url = config.env("XRPL_WS_URL", PUBLIC_WS)
    threading.Thread(target=_run, args=(url,), daemon=True).start()
