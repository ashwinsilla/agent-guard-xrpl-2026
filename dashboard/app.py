"""The AgentGuard dashboard: one web page that shows everything live and drives the demo.

Run with everything else:  .venv/bin/python run_demo.py   (then open http://127.0.0.1:8080)

  GET  /                  the page (dashboard/static/index.html)
  GET  /api/status        passport, AgentGuard state, balances, held purchases, latest report
  GET  /api/events        live feed (Server-Sent Events) read from the shared event log
  POST /api/start         run the Treasury Analyst agent (in the background)
  POST /api/kill          big red button: freeze the agent now (stage 1)
  POST /api/confirm       Acme's approver key confirms: revoke passport, return float (stage 2)
  POST /api/reissue       Acme re-issues the passport with one approval
  POST /api/reset         back to the start of the demo
  POST /api/overcap       Mastercard check: a voucher above the channel cap is rejected
  POST /api/approve/{id}  approve a held purchase    POST /api/reject/{id}  reject it
  POST /webhooks/quicknode  Quicknode Streams/webhook deliveries (secret-checked) -> live feed
"""
import asyncio
import json
import os
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from agentguard import ap4m, checker, config, demo, events, killswitch, llm, multisig, passport, state, xrpl_core

app = FastAPI(title="AgentGuard dashboard")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_busy = {"task": None}           # only one long action at a time (agent run, reset...)
_cache = {"t": 0.0, "data": None}


def _background(name: str, fn) -> dict:
    """Run a slow action in a thread so the page stays responsive."""
    if _busy["task"]:
        return {"ok": False, "error": f"busy: {_busy['task']} is still running"}

    def run():
        _busy["task"] = name
        try:
            fn()
        except Exception as exc:
            events.emit("dashboard", f"{name} failed: {type(exc).__name__}: {str(exc)[:150]}", "bad")
        finally:
            _busy["task"] = None
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "started": name}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


def _status() -> dict:
    agent, treasury, _ = xrpl_core.load_wallets()
    pp = passport.get_passport_status()
    s = state.load()
    info = multisig.account_info(agent.classic_address)
    signers = [{"account": e["SignerEntry"]["Account"], "weight": e["SignerEntry"]["SignerWeight"]}
               for e in (info.get("_signer_list") or {}).get("SignerEntries", [])]
    names = {config.env(f"XRPL_{r}_ADDRESS"): r for r in multisig.WEIGHTS}
    payout = None
    try:
        if s["channel_id"]:
            payout_addr = ap4m.get_channel_state(s["channel_id"])["payout"]
            payout = {"address": payout_addr, "rlusd": ap4m.from_wei(ap4m.rlusd_balance(payout_addr))}
    except Exception:
        pass
    reports = sorted(os.listdir(config.REPORTS_DIR)) if os.path.isdir(config.REPORTS_DIR) else []
    report = open(os.path.join(config.REPORTS_DIR, reports[-1])).read() if reports else ""
    return {
        "passport": {**pp, "expires": pp["expires"].isoformat() if pp["expires"] else None,
                     "link": config.xrpl_account_link(agent.classic_address)},
        "agentguard": {"frozen": s["frozen"], "pending_revoke": s["pending_revoke"], "strikes": s["strikes"],
                       "strike_limit": config.STRIKES_BEFORE_REVOKE},
        "wallet": {"agent": agent.classic_address, "agent_spendable_xrp": round(multisig.spendable_xrp(agent.classic_address), 4),
                   "master_disabled": bool(info.get("Flags", 0) & multisig.LSF_DISABLE_MASTER),
                   "quorum": (info.get("_signer_list") or {}).get("SignerQuorum"),
                   "signers": [{**x, "role": names.get(x["account"], "?")} for x in signers],
                   "treasury": treasury.classic_address,
                   "treasury_xrp": round(int(multisig.account_info(treasury.classic_address).get("Balance", 0)) / 1e6, 2)},
        "spent_today": s["spent_today"],
        "ap4m": {"mode": ap4m.mode_label(), "why_mock": ap4m.mock_reason(), "channel_id": s["channel_id"], "payout": payout},
        "llm": {"online": llm.available(), "why": llm.offline_reason(), "model": llm.model_id()},
        "rpc": {"quicknode": config.using_quicknode()},
        "held": list(s["held"].values()),
        "report": report,
        "busy": _busy["task"],
    }


@app.get("/api/status")
def status():
    if time.time() - _cache["t"] > 2 or _cache["data"] is None:  # the ledger reads take ~1s; don't repeat them
        _cache["data"], _cache["t"] = _status(), time.time()
    return {**_cache["data"], "busy": _busy["task"]}


@app.get("/api/events")
async def stream(request: Request, last_id: int = 0):
    """Server-Sent Events: push every new event line to the page as it happens."""
    async def gen():
        last = last_id
        while not await request.is_disconnected():
            for ev in events.read_since(last):
                last = ev["id"]
                yield f"data: {json.dumps(ev, default=str)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


def _fresh():
    _cache["t"] = 0  # force the next /api/status to re-read the ledger


@app.post("/api/start")
def start():
    from agents import treasury_analyst
    _fresh()
    return _background("agent run", treasury_analyst.run)


@app.post("/api/kill")
def kill():
    _fresh()
    return killswitch.freeze("Acme pressed the KILL button", manual=True)


@app.post("/api/confirm")
def confirm():
    _fresh()
    return _background("revocation", killswitch.confirm_revoke)


@app.post("/api/reissue")
def reissue():
    _fresh()
    return _background("re-issue", demo.reissue_passport)


@app.post("/api/reset")
def reset():
    _fresh()
    return _background("reset", demo.reset_demo)


@app.post("/api/overcap")
def overcap():
    from agentguard import ap4m
    return _background("over-cap test", ap4m.prove_over_cap)


@app.post("/api/approve/{purchase_id}")
def approve(purchase_id: str):
    return {"ok": checker.approve_held(purchase_id)}


@app.post("/api/reject/{purchase_id}")
def reject(purchase_id: str):
    checker.reject_held(purchase_id)
    return {"ok": True}


@app.post("/webhooks/quicknode")
async def quicknode_webhook(request: Request):
    """Quicknode Streams / webhooks: on-ledger activity for our accounts lands in the live feed."""
    secret = config.env("QUICKNODE_WEBHOOK_SECRET")
    if not secret or request.headers.get("x-qn-secret", request.query_params.get("secret")) != secret:
        return JSONResponse({"error": "bad secret"}, status_code=401)
    payload = await request.json()
    items = payload if isinstance(payload, list) else [payload]
    for item in items[:20]:
        tx = item.get("transaction", item.get("tx_json", item)) if isinstance(item, dict) else {}
        h = tx.get("hash") or (item.get("hash") if isinstance(item, dict) else None)
        events.emit("quicknode", f"Quicknode stream: {tx.get('TransactionType', 'transaction')} on the XRP Ledger",
                    "info", tx_hash=h, link=config.xrpl_tx_link(h) if h else None, mode="LIVE")
    return {"ok": True}
