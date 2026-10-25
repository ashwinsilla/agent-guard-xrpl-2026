"""Shared event log: everything that happens is written here, and the dashboard shows it.

Two ways to listen:
  * `subscribe()`  : in-memory queue, instant, but only for code in the SAME process.
  * `read_since()` : reads the JSON-lines file, works across processes (merchants, agent, dashboard).
Each event is one line of JSON: {"id", "ts", "kind", "title", "severity", ...extra fields}.
"""
import json
import os
import queue
import threading
import time

from agentguard.config import DATA_DIR

EVENTS_FILE = os.path.join(DATA_DIR, "events.jsonl")
_lock = threading.Lock()
_subscribers: list[queue.Queue] = []


def emit(kind: str, title: str, severity: str = "info", **fields) -> dict:
    """Record an event. severity is one of: info, good, warn, bad.

    `mode` (if given) should be LIVE, MOCK or OFFLINE so mocked activity is never
    mistaken for real on-chain activity.
    """
    with _lock:
        event = {"id": _next_id(), "ts": time.time(), "kind": kind, "title": title, "severity": severity, **fields}
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")
    for q in list(_subscribers):
        q.put(event)
    print(f"[{kind}] {title}")  # also visible in the terminal
    return event


def _next_id() -> int:
    """Event IDs count up from the number of lines already in the file."""
    if not os.path.exists(EVENTS_FILE):
        return 1
    with open(EVENTS_FILE) as f:
        return sum(1 for _ in f) + 1


def read_since(last_id: int = 0) -> list[dict]:
    """All events with id greater than last_id (reads the file, so it works across processes)."""
    if not os.path.exists(EVENTS_FILE):
        return []
    out = []
    with open(EVENTS_FILE) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue  # a half-written line; it will be complete next time
            if ev["id"] > last_id:
                out.append(ev)
    return out


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


def clear() -> None:
    """Start a fresh log (used by reset_demo)."""
    with _lock:
        open(EVENTS_FILE, "w").close()
