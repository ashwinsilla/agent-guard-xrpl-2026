"""Small persistent state shared by the checker, voucher gate and kill switch.

Stored in data/state.json so a restart doesn't lose strikes or voucher totals.
(The per-channel voucher total is the important one: AP4M vouchers carry the RUNNING TOTAL,
so forgetting it would make the next voucher invalid.)
"""
import json
import os
import threading

from agentguard.config import DATA_DIR

STATE_FILE = os.path.join(DATA_DIR, "state.json")
_lock = threading.RLock()

DEFAULT = {
    "strikes": 0,                 # number of BLOCKed purchases since last reset
    "frozen": False,              # True once the kill switch fires: AgentGuard co-signs NOTHING any more
    "agent_revoked": False,       # True after Acme deleted the passport (CredentialDelete)
    "pending_revoke": False,      # frozen, waiting for Acme's approver key to confirm the revocation
    "channel_totals": {},         # channel_id -> cumulative RLUSD base units (string) already SIGNED
    "approved_purchases": {},     # purchase_id -> {"merchant","rail","amount","pay_to"}: approvals the signers honour once
    "held": {},                   # purchase_id -> purchase waiting for human approval
    "spent_today": {"XRP": "0", "RLUSD": "0"},  # approved spend per currency (decimal strings)
    "price_history": {},          # merchant key -> list of prices paid (the checker AI sees this)
    "last_credential_id": None,   # last passport ID seen on the ledger (shown again after revoke to prove the refusal)
    "channel_id": None,           # the AP4M channel in use
    "channel_mode": None,         # "live" or "mock": which mode opened that channel
    "mock_ledger": {},            # MOCK mode only: simulated on-chain data
}


def load() -> dict:
    with _lock:
        if not os.path.exists(STATE_FILE):
            return json.loads(json.dumps(DEFAULT))
        with open(STATE_FILE) as f:
            data = json.load(f)
        for k, v in DEFAULT.items():
            data.setdefault(k, json.loads(json.dumps(v)))
        return data


def save(state: dict) -> None:
    """Write atomically (temp file then rename) so a crash can't leave a broken file."""
    with _lock:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)


def update(**changes) -> dict:
    with _lock:
        s = load()
        s.update(changes)
        save(s)
        return s


def mutate(fn) -> dict:
    """Load, let `fn(state)` change it in place, save. Keeps read-modify-write atomic."""
    with _lock:
        s = load()
        fn(s)
        save(s)
        return s


def reset(keep_channel: bool = True) -> dict:
    """Back to the start-of-demo state. Keeps the channel id and its voucher total by default."""
    with _lock:
        old = load()
        s = json.loads(json.dumps(DEFAULT))
        if keep_channel:
            s["channel_id"] = old["channel_id"]
            s["channel_totals"] = old["channel_totals"]
            s["mock_ledger"] = old["mock_ledger"]
            s["channel_mode"] = old.get("channel_mode")
        save(s)
        return s
