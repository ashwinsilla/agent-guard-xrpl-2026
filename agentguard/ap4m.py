"""Mastercard Agent Pay for Machines (AP4M) on the XRPL EVM testnet, in Python.

This is a port of the official hackathon SDK (https://hackathon.ap4m.build/sdk/ap4m-hackathon-sdk.js).
How a payment works, in plain words:
  1. The agent and the AP4M service share a payment CHANNEL with a spending cap (in RLUSD).
  2. To pay, the agent signs a VOUCHER: "I owe the merchant a TOTAL of X RLUSD on this channel".
     X is the running total (cumulative), NOT the price of this one purchase.
  3. Anyone can submit the voucher to the PaymentLedger contract (`redeemVoucher`). The contract
     emits a VoucherRedeemed event and the service pays the merchant RLUSD from the vault.

THE VOUCHER GATE (the important AgentGuard idea):
  `sign_voucher()` below is the ONLY place that signs vouchers, and it lives in AgentGuard, not in
  the AI agent. It refuses when the passport is revoked/expired or the checker has not approved
  that exact purchase. The agent never holds the signing key in its tools, so it cannot bypass it.

Modes (events and the dashboard always show which one is active):
  LIVE : real AP4M service + real contracts (needs the team's agent wallet registered and funded
         in the participant portal: https://hackathon.ap4m.build/participant).
  MOCK : same cryptography (real EIP-712 signatures, real signature checks) but the channel and
         the redemption are simulated locally. Never presented as on-chain activity.
Force a mode with AP4M_MODE=live|mock; the default "auto" uses LIVE when sign-in works.
"""
import os
import threading
import time
import uuid
from decimal import Decimal

import requests
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from web3 import Web3

from agentguard import config, events, passport, state

DECIMALS = config.RLUSD_DECIMALS

# --- minimal contract ABIs (just the calls we use) -----------------------------------------
LEDGER_ABI = [
    {"type": "function", "name": "redeemVoucher", "stateMutability": "nonpayable",
     "inputs": [{"name": "voucher", "type": "tuple", "components": [
         {"name": "channelId", "type": "bytes32"}, {"name": "cumulativeAmount", "type": "uint256"}]},
         {"name": "agentSignature", "type": "bytes"}],
     "outputs": [{"name": "claimId", "type": "bytes32"}, {"name": "amount", "type": "uint256"},
                 {"name": "digest", "type": "bytes32"}]},
    {"type": "function", "name": "channels", "stateMutability": "view",
     "inputs": [{"name": "channelId", "type": "bytes32"}],
     "outputs": [{"name": n, "type": t} for n, t in [
         ("allocationId", "bytes32"), ("merchantPspId", "bytes32"), ("requestDigest", "bytes32"),
         ("authorityAttestationId", "bytes32"), ("merchantAttestationId", "bytes32"), ("merchantId", "bytes32"),
         ("latestVoucherDigest", "bytes32"), ("cap", "uint256"), ("redeemed", "uint256"), ("agent", "address"),
         ("allocationGeneration", "uint64"), ("status", "uint8"), ("payout", "address"),
         ("merchantGeneration", "uint64"), ("merchantPspSigner", "address"),
         ("merchantPspSignerGeneration", "uint64"), ("validAfter", "uint64"), ("validBefore", "uint64")]]},
]
ERC20_ABI = [{"type": "function", "name": "balanceOf", "stateMutability": "view",
              "inputs": [{"name": "a", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]}]
VOUCHER_REDEEMED_TOPIC = Web3.keccak(
    text="VoucherRedeemed(bytes32,bytes32,bytes32,bytes32,address,bytes32,address,address,uint256,uint256,uint256)"
).hex()

_lock = threading.RLock()
_mode_cache: dict = {}
_token_cache: dict = {}


class GateRefused(Exception):
    """Raised by the voucher gate when it will not sign. `.reason` explains why."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --- unit helpers ---------------------------------------------------------------------------
def to_wei(rlusd) -> int:
    """RLUSD (like '0.05') -> base units (18 decimals), exact, no float rounding."""
    return int(Decimal(str(rlusd)) * 10 ** DECIMALS)


def from_wei(wei) -> str:
    return format(Decimal(int(wei)) / 10 ** DECIMALS, "f").rstrip("0").rstrip(".") or "0"


def _w3() -> Web3:
    return Web3(Web3.HTTPProvider(config.EVM_RPC_URL, request_kwargs={"timeout": 30}))


def _agent_account():
    key = config.env("AGENT_EVM_PRIVATE_KEY")
    if not key:
        raise RuntimeError("AGENT_EVM_PRIVATE_KEY is missing from .env")
    return Account.from_key(key)


def _merchant_account():
    key = config.env("MERCHANT_EVM_PRIVATE_KEY")
    if not key:
        raise RuntimeError("MERCHANT_EVM_PRIVATE_KEY is missing from .env")
    return Account.from_key(key)


def agent_address() -> str:
    return _agent_account().address


# --- mode + session ---------------------------------------------------------------------------
def sign_in() -> str:
    """Challenge -> sign -> session token (cached for 10 minutes)."""
    cached = _token_cache.get("t")
    if cached and cached[1] > time.time():
        return cached[0]
    acct = _agent_account()
    base = config.AP4M_API_BASE
    r = requests.post(f"{base}/public/participant/challenge",
                      json={"teamName": config.AP4M_TEAM_NAME, "wallet": acct.address}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"AP4M sign-in challenge failed ({r.status_code}): {r.json().get('error', r.text)}")
    challenge = r.json()
    signature = Account.sign_message(encode_defunct(text=challenge["message"]), acct.key).signature.hex()
    r = requests.post(f"{base}/public/participant/session",
                      json={"challengeId": challenge["challengeId"], "signature": signature if signature.startswith("0x") else "0x" + signature},
                      timeout=30)
    if not r.ok:
        raise RuntimeError(f"AP4M sign-in failed ({r.status_code}): {r.json().get('error', r.text)}")
    token = r.json()["token"]
    _token_cache["t"] = (token, time.time() + 600)
    return token


def mode() -> str:
    """'live' or 'mock'. Decided once per process (see module docstring)."""
    forced = config.env("AP4M_MODE", "auto").lower()
    if forced in ("live", "mock"):
        return forced
    if "m" not in _mode_cache:
        try:
            sign_in()
            _mode_cache["m"] = "live"
        except Exception as exc:  # not registered, no key, service down...
            config.log.warning("AP4M LIVE unavailable (%s): using MOCK mode", exc)
            _mode_cache["m"] = "mock"
            _mode_cache["why"] = str(exc)
    return _mode_cache["m"]


def mode_label() -> str:
    return "LIVE" if mode() == "live" else "MOCK"


def mock_reason() -> str:
    mode()
    return _mode_cache.get("why", "")


# --- reading the chain ------------------------------------------------------------------------
def rlusd_balance(address: str) -> int:
    """RLUSD balance (base units). In MOCK mode, the simulated balance."""
    if mode() == "mock":
        return int(state.load()["mock_ledger"].get("balances", {}).get(address.lower(), "0"))
    w3 = _w3()
    token = w3.eth.contract(address=Web3.to_checksum_address(config.RLUSD), abi=ERC20_ABI)
    return token.functions.balanceOf(Web3.to_checksum_address(address)).call()


def get_channel_state(channel_id: str) -> dict:
    """{cap, redeemed, status, payout, agent, valid_before} for a channel (wei ints)."""
    if mode() == "mock":
        ch = state.load()["mock_ledger"]["channels"][channel_id]
        return {"cap": int(ch["cap"]), "redeemed": int(ch["redeemed"]), "status": ch["status"],
                "payout": ch["payout"], "agent": agent_address(), "valid_before": 2**62}
    c = _w3().eth.contract(address=Web3.to_checksum_address(config.PAYMENT_LEDGER), abi=LEDGER_ABI)
    r = c.functions.channels(channel_id).call()
    return {"cap": r[7], "redeemed": r[8], "status": int(r[11]), "payout": r[12], "agent": r[9], "valid_before": r[17]}


# --- channel lifecycle ------------------------------------------------------------------------
def ensure_channel(cap_rlusd: str = "5") -> str:
    """Return the id of an open channel, opening one if needed (and remembering it)."""
    s = state.load()
    if s["channel_id"]:
        return s["channel_id"]
    if mode() == "mock":
        return _mock_open_channel(cap_rlusd)
    token = sign_in()
    base = config.AP4M_API_BASE
    headers = {"Authorization": f"Bearer {token}"}
    open_ones = [c for c in requests.get(f"{base}/public/participant/channels", headers=headers, timeout=30).json().get("channels", [])
                 if c["channel_status"] == "open"]
    if open_ones:
        channel_id = open_ones[0]["channel_id"]
    else:
        channel_id = _live_request_channel(token, cap_rlusd)
    state.update(channel_id=channel_id)
    events.emit("ap4m", f"AP4M channel ready ({channel_id[:10]}…)", "good", mode="LIVE", channel_id=channel_id)
    return channel_id


def _live_request_channel(token: str, cap_rlusd: str) -> str:
    """Port of requestChannel(): prepare -> agent sends the vault tx -> service opens the channel."""
    base, headers = config.AP4M_API_BASE, {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{base}/public/participant/channel-requests/prepare", headers=headers,
                      json={"cap_rlusd": str(cap_rlusd)}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"channel request failed ({r.status_code}): {r.json().get('error', r.text)}")
    prepared, acct, w3 = r.json(), _agent_account(), _w3()
    tx = {"to": Web3.to_checksum_address(prepared["to"]), "data": prepared["data"], "from": acct.address,
          "nonce": w3.eth.get_transaction_count(acct.address), "chainId": config.EVM_CHAIN_ID,
          "gasPrice": w3.eth.gas_price, "value": 0}
    tx["gas"] = w3.eth.estimate_gas(tx)
    tx_hash = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    r = requests.post(f"{base}/public/participant/channel-requests", headers=headers,
                      json={"tx_hash": tx_hash.hex() if tx_hash.hex().startswith("0x") else "0x" + tx_hash.hex()}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"channel request sent but not recorded ({r.status_code}): {r.json().get('error', r.text)}")
    channel = r.json()
    deadline = time.time() + 180
    while channel.get("channel_status") != "open":
        if channel.get("channel_status") == "failed":
            raise RuntimeError(f"channel failed: {channel.get('failure')}")
        if time.time() > deadline:
            raise RuntimeError("channel still not open after 3 minutes")
        time.sleep(2)
        chans = requests.get(f"{base}/public/participant/channels", headers=headers, timeout=30).json()["channels"]
        channel = next((c for c in chans if c["channel_id"] == channel["channel_id"]), channel)
    return channel["channel_id"]


def _mock_open_channel(cap_rlusd) -> str:
    channel_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    merchant = _merchant_account().address
    def init(s):
        led = s["mock_ledger"]
        led.setdefault("channels", {})[channel_id] = {"cap": str(to_wei(20)), "redeemed": "0", "status": 1, "payout": merchant}
        led.setdefault("balances", {})
    state.mutate(init)
    state.update(channel_id=channel_id)
    events.emit("ap4m", f"MOCK channel opened ({channel_id[:10]}…): simulated, not on-chain", "warn",
                mode="MOCK", channel_id=channel_id)
    return channel_id


def close_channel() -> dict:
    """Kill-switch hook: close the AP4M channel so no more vouchers can ever be redeemed.

    Respects KILL_SWITCH_CLOSE_REAL_CHANNEL (default false) so the demo can be rehearsed without
    burning the real channel. Returns {"closed": bool, "simulated": bool, "tx_hash": str|None}.
    """
    s = state.load()
    channel_id = s["channel_id"]
    if not channel_id:
        return {"closed": False, "simulated": True, "tx_hash": None, "note": "no channel"}
    if mode() == "mock":
        def close(st):
            st["mock_ledger"]["channels"][channel_id]["status"] = 2
        state.mutate(close)
        events.emit("ap4m", "MOCK channel closed (simulated)", "warn", mode="MOCK", channel_id=channel_id)
        return {"closed": True, "simulated": True, "tx_hash": None}
    if not config.CLOSE_REAL_CHANNEL:
        events.emit("ap4m", "Channel close SIMULATED (rehearsal mode: KILL_SWITCH_CLOSE_REAL_CHANNEL=false). "
                    "The agent can no longer get vouchers signed.", "warn", mode="REHEARSAL", channel_id=channel_id)
        return {"closed": True, "simulated": True, "tx_hash": None}
    return _live_close(channel_id)


def _live_close(channel_id: str) -> dict:
    """Port of closeChannel(): fetch checkpoint -> agent signs it -> service closes the channel."""
    base, headers = config.AP4M_API_BASE, {"Authorization": f"Bearer {sign_in()}"}
    r = requests.get(f"{base}/public/participant/close-channel-challenge", headers=headers,
                     params={"channel_id": channel_id}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"close-channel-challenge failed ({r.status_code}): {r.json().get('error', r.text)}")
    data = r.json()
    typed = data["typedData"]
    value = dict(typed["value"])
    for k in ("finalCumulativeAmount", "merchantPspSignerGeneration", "signedAt"):
        value[k] = int(value[k])
    full = {"types": {"EIP712Domain": _domain_fields(typed["domain"]), **typed["types"]},
            "primaryType": next(iter(typed["types"])), "domain": typed["domain"], "message": value}
    sig = Account.sign_message(encode_typed_data(full_message=full), _agent_account().key)
    # r + yParityAndS ("vs"): EIP-2098 compact form
    s_int = sig.s | ((sig.v - 27) << 255)
    r2 = requests.post(f"{base}/public/participant/close-channel", headers=headers, timeout=60, json={
        "agent_signature_r": "0x" + sig.r.to_bytes(32, "big").hex(),
        "agent_signature_vs": "0x" + s_int.to_bytes(32, "big").hex(),
        "channel_id": data["checkpoint"]["channelId"]})
    if not r2.ok:
        raise RuntimeError(f"close-channel failed ({r2.status_code}): {r2.json().get('error', r2.text)}")
    out = r2.json()
    events.emit("ap4m", "AP4M channel CLOSED on-chain", "bad", mode="LIVE", tx_hash=out.get("tx_hash"),
                link=config.evm_tx_link(out["tx_hash"]) if out.get("tx_hash") else None, channel_id=channel_id)
    return {"closed": True, "simulated": False, "tx_hash": out.get("tx_hash")}


def _domain_fields(domain: dict) -> list:
    types = {"name": "string", "version": "string", "chainId": "uint256", "verifyingContract": "address", "salt": "bytes32"}
    return [{"name": k, "type": types[k]} for k in domain if k in types]


# --- vouchers: signing (gate) and verifying ------------------------------------------------------
def _voucher_message(channel_id: str, cumulative: int) -> dict:
    return {
        "types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                   {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
                  "Voucher": [{"name": "channelId", "type": "bytes32"}, {"name": "cumulativeAmount", "type": "uint256"}]},
        "primaryType": "Voucher",
        "domain": {"name": "AP4M Payment Ledger", "version": "1", "chainId": config.EVM_CHAIN_ID,
                   "verifyingContract": config.PAYMENT_LEDGER},
        "message": {"channelId": bytes.fromhex(channel_id[2:]), "cumulativeAmount": int(cumulative)},
    }


def sign_voucher_raw(channel_id: str, cumulative: int) -> str:
    """EIP-712 signature over Voucher{channelId, cumulativeAmount}. Internal: use sign_voucher() (the gate)."""
    sig = Account.sign_message(encode_typed_data(full_message=_voucher_message(channel_id, cumulative)),
                               _agent_account().key).signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig


def recover_voucher_signer(channel_id: str, cumulative: int, signature: str) -> str:
    """Who signed this voucher? (Merchants use this; tests use it to check the signature.)"""
    return Account.recover_message(encode_typed_data(full_message=_voucher_message(channel_id, cumulative)),
                                   signature=signature)


def gate_check(purchase_id: str, merchant: str, increment_wei: int) -> None:
    """Raise GateRefused unless signing this voucher is allowed. Order matters: cheapest/safest first."""
    s = state.load()
    if s["agent_revoked"]:
        raise GateRefused("agent has been revoked by the kill switch")
    status = passport.get_passport_status()["status"]
    if status != "active":
        raise GateRefused(f"passport is not active (status: {status})")
    approval = s["approved_purchases"].get(purchase_id)
    if not approval:
        raise GateRefused("the checker has not approved this purchase")
    if approval["merchant"] != merchant or int(approval["amount_wei"]) != int(increment_wei):
        raise GateRefused("purchase does not match what the checker approved")
    if increment_wei <= 0:
        raise GateRefused("amount must be positive")
    if not s["channel_id"]:
        raise GateRefused("no open payment channel")
    if mode() == "mock" and s["mock_ledger"]["channels"][s["channel_id"]]["status"] != 1:
        raise GateRefused("payment channel is closed")


def sign_voucher(purchase_id: str, merchant: str, increment_rlusd) -> dict:
    """THE VOUCHER GATE. Sign a voucher for `increment_rlusd` more RLUSD, or refuse.

    The running total is read from disk (and the chain), increased by the price, saved, and only
    then signed, so a restart can never produce a voucher that reuses an old total.
    Returns {"channel_id", "cumulative", "signature"}.
    """
    increment = to_wei(increment_rlusd)
    with _lock:
        try:
            gate_check(purchase_id, merchant, increment)
        except GateRefused as exc:
            events.emit("gate", f"Voucher gate REFUSED to sign for {merchant}: {exc.reason}", "bad",
                        merchant=merchant, reason=exc.reason)
            raise
        s = state.load()
        channel_id = s["channel_id"]
        persisted = int(s["channel_totals"].get(channel_id, "0"))
        onchain = get_channel_state(channel_id)["redeemed"]
        cumulative = max(persisted, onchain) + increment
        if cumulative > get_channel_state(channel_id)["cap"]:
            reason = "channel spending cap would be exceeded"
            events.emit("gate", f"Voucher gate REFUSED: {reason}", "bad", merchant=merchant, reason=reason)
            raise GateRefused(reason)

        def save_total(st):
            st["channel_totals"][channel_id] = str(cumulative)
            st["approved_purchases"].pop(purchase_id, None)  # an approval is single-use
        state.mutate(save_total)
        signature = sign_voucher_raw(channel_id, cumulative)
    events.emit("gate", f"Voucher gate SIGNED {from_wei(increment)} RLUSD for {merchant} "
                f"(running total {from_wei(cumulative)})", "good", merchant=merchant, mode=mode_label(),
                cumulative=from_wei(cumulative))
    return {"channel_id": channel_id, "cumulative": cumulative, "signature": signature}


# --- merchant side: redeem ------------------------------------------------------------------------
def redeem_voucher(channel_id: str, cumulative: int, signature: str, merchant_name: str = "merchant") -> dict:
    """Merchant submits the agent's voucher to the PaymentLedger and reports VoucherRedeemed + balance change.

    Returns {"tx_hash", "claim_id", "amount_wei", "payout", "balance_before", "balance_after", "mode", "link"}.
    """
    signer = recover_voucher_signer(channel_id, cumulative, signature)
    if signer.lower() != agent_address().lower():
        raise ValueError("voucher was not signed by our agent")
    before_state = get_channel_state(channel_id)
    payout = before_state["payout"]
    balance_before = rlusd_balance(payout)
    if cumulative <= before_state["redeemed"]:
        raise ValueError("voucher is stale: cumulative amount not above what is already redeemed")

    if mode() == "mock":
        def apply(st):
            ch = st["mock_ledger"]["channels"][channel_id]
            if int(ch["status"]) != 1:
                raise ValueError("channel is closed")
            delta = cumulative - int(ch["redeemed"])
            ch["redeemed"] = str(cumulative)
            bal = st["mock_ledger"]["balances"]
            bal[payout.lower()] = str(int(bal.get(payout.lower(), "0")) + delta)
        state.mutate(apply)
        tx_hash, link, claim_id = "MOCK-" + uuid.uuid4().hex[:16], None, "0xMOCK" + uuid.uuid4().hex[:8]
    else:
        w3, acct = _w3(), _merchant_account()
        ledger = w3.eth.contract(address=Web3.to_checksum_address(config.PAYMENT_LEDGER), abi=LEDGER_ABI)
        call = ledger.functions.redeemVoucher((bytes.fromhex(channel_id[2:]), cumulative), bytes.fromhex(signature[2:]))
        tx = call.build_transaction({"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                                     "chainId": config.EVM_CHAIN_ID, "gasPrice": w3.eth.gas_price})
        h = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(h, timeout=120)
        if receipt.status != 1:
            raise RuntimeError("redeemVoucher transaction reverted")
        tx_hash = h.hex() if h.hex().startswith("0x") else "0x" + h.hex()
        link = config.evm_tx_link(tx_hash)
        topic = VOUCHER_REDEEMED_TOPIC if VOUCHER_REDEEMED_TOPIC.startswith("0x") else "0x" + VOUCHER_REDEEMED_TOPIC
        logs = [lg for lg in receipt.logs if lg["address"].lower() == config.PAYMENT_LEDGER.lower()
                and lg["topics"][0].hex().lower().replace("0x", "") == topic.replace("0x", "").lower()]
        if not logs:
            raise RuntimeError("redeemVoucher succeeded but no VoucherRedeemed event was found")
        t2 = logs[0]["topics"][2].hex()
        claim_id = t2 if t2.startswith("0x") else "0x" + t2
        _record_redemption(tx_hash)
    after_state = get_channel_state(channel_id)
    delta = after_state["redeemed"] - before_state["redeemed"]
    # Payout to the merchant happens shortly after (the service pays from the vault), so the live
    # balance may lag by a few blocks; we report whatever we see now and the dashboard re-polls.
    balance_after = rlusd_balance(payout)
    result = {"tx_hash": tx_hash, "claim_id": claim_id, "amount_wei": delta, "payout": payout,
              "balance_before": balance_before, "balance_after": balance_after, "mode": mode_label(), "link": link}
    events.emit("voucher_redeemed",
                f"VoucherRedeemed: {from_wei(delta)} RLUSD to {merchant_name} (claim {claim_id[:12]}…)",
                "good" if mode() == "live" else "warn", **{k: (str(v) if isinstance(v, int) else v) for k, v in result.items()},
                merchant=merchant_name)
    return result


def _record_redemption(tx_hash: str) -> None:
    """Tell the service about the redemption so it sees it at once (optional in the SDK; best effort)."""
    try:
        requests.post(f"{config.AP4M_API_BASE}/public/participant/record-redemption",
                      headers={"Authorization": f"Bearer {sign_in()}"}, json={"tx_hash": tx_hash}, timeout=30)
    except Exception as exc:  # the chain is the source of truth; this is only a nudge
        config.log.warning("record-redemption failed: %s", exc)
