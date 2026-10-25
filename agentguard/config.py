"""Central settings for AgentGuard, read from the .env file.

Why one file? Every module needs the same URLs, flags and links. Keeping them here means
there is exactly one place to look when something is configured wrongly.
Secrets (seeds / private keys) are read by the modules that need them and are never printed.
"""
import logging
import os

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

log = logging.getLogger("agentguard")

DATA_DIR = os.path.join(ROOT, "data")        # local state: events, strikes, voucher totals
REPORTS_DIR = os.path.join(ROOT, "reports")  # the agent's morning risk reports
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

PUBLIC_XRPL_TESTNET = "https://s.altnet.rippletest.net:51234/"


def env(name: str, default: str = "") -> str:
    """Read one setting; empty string counts as 'not set'."""
    return os.getenv(name) or default


def flag(name: str, default: bool = False) -> bool:
    """Read a true/false setting such as USE_LEDGER=true."""
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---- XRPL (main ledger) -----------------------------------------------------
def xrpl_rpc_url() -> str:
    """Quicknode endpoint if configured; otherwise the public testnet (with a warning)."""
    url = env("XRPL_RPC_URL")
    if not url or url == PUBLIC_XRPL_TESTNET:
        log.warning("XRPL_RPC_URL is not a Quicknode endpoint: using the public testnet server.")
        return PUBLIC_XRPL_TESTNET
    return url


def using_quicknode() -> bool:
    url = env("XRPL_RPC_URL")
    return bool(url) and "quiknode" in url


# ---- AP4M / EVM -------------------------------------------------------------
AP4M_API_BASE = env("AP4M_API_BASE", "https://hackathon.ap4m.build")
AP4M_TEAM_NAME = env("AP4M_TEAM_NAME", "gizmo geeks")
EVM_RPC_URL = env("EVM_RPC_URL", "https://rpc.testnet.xrplevm.org")
EVM_CHAIN_ID = 1449000
PAYMENT_LEDGER = "0xcAB42800A5ECF0D253Fa2581Bb3334B4DAEfaE91"
RLUSD = "0x27b57a9D0b8d24EB97259c4E2279e45255e016f3"
RLUSD_DECIMALS = 18

# ---- Behaviour flags --------------------------------------------------------
STRIKES_BEFORE_REVOKE = int(env("STRIKES_BEFORE_REVOKE", "3"))
CLOSE_REAL_CHANNEL = flag("KILL_SWITCH_CLOSE_REAL_CHANNEL", False)
USE_LEDGER = flag("USE_LEDGER", False)
DEMO_MODE = env("DEMO_MODE", "live")  # "live" = normal run; "attack" = scam offer always injected

# ---- Merchants (ports) ------------------------------------------------------
MERCHANT_PORT = int(env("MERCHANT_PORT", "8000"))
DASHBOARD_PORT = int(env("DASHBOARD_PORT", "8080"))
MERCHANT_BASE = env("MERCHANT_BASE", f"http://127.0.0.1:{MERCHANT_PORT}")

# ---- Explorer links ---------------------------------------------------------
def xrpl_tx_link(tx_hash: str) -> str:
    return f"https://testnet.xrpl.org/transactions/{tx_hash}"


def xrpl_account_link(address: str) -> str:
    return f"https://testnet.xrpl.org/accounts/{address}"


def evm_tx_link(tx_hash: str) -> str:
    return f"https://explorer.testnet.xrplevm.org/tx/{tx_hash}"


def evm_address_link(address: str) -> str:
    return f"https://explorer.testnet.xrplevm.org/address/{address}"
