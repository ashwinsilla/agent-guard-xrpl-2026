"""The CHECKER: reviews every purchase BEFORE AgentGuard co-signs anything.

Two layers, so the demo is reliable AND smart:
  1. Hard RULES in plain Python (always run first, instant, explainable):
       passport not active -> BLOCK | merchant not on Acme's approved list -> BLOCK
       price above 3x the merchant's usual price -> BLOCK | daily budget exceeded -> BLOCK
       a single purchase above the auto-approve limit -> HOLD (a human approves it on the dashboard)
  2. The checker AI (Amazon Bedrock) for purchases the rules allow: does it fit the agent's task?
     It may only make the verdict STRICTER (APPROVE -> HOLD/BLOCK), never looser.
     For purchases the rules already blocked, the AI only explains why (it can't unblock).

Anti prompt-injection: the AI sees ONLY structured facts (task, merchant, category, price, usual
price, past prices). It never sees the merchant's text or the agent's own explanation, which is
exactly where injected instructions would hide.
If Bedrock is unavailable we use rules only and label it "LLM OFFLINE".

Outcomes:
  APPROVE : AgentGuard will co-sign (XRPL) or sign the voucher (AP4M) for this exact purchase, once.
  HOLD    : waits for a human (dashboard button).
  BLOCK   : refused, and counts as a STRIKE. At STRIKES_BEFORE_REVOKE strikes the kill switch fires.
"""
import time
import uuid
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from agentguard import config, events, llm, passport, state

TASK = "Write Acme Corp's daily FX and crypto risk report (EUR, JPY and XRP exposure, market news)."
APPROVED_MERCHANTS = {"fx", "crypto", "news", "news_deep"}  # keys in merchants.app.MERCHANTS
# What each kind of data normally costs, per merchant key (the attacker's "signals" are priced like data).
USUAL_PRICE = {"fx": "0.05", "crypto": "0.05", "alpha": "0.05", "news": "0.25", "news_deep": "0.50"}
PRICE_MULTIPLE_LIMIT = Decimal(3)
DAILY_BUDGET = {"XRP": Decimal(config.env("DAILY_BUDGET_XRP", "2")),
                "RLUSD": Decimal(config.env("DAILY_BUDGET_RLUSD", "2"))}
# Routine buys are automatic; anything bigger than this per purchase waits for a human.
# Default: the 0.50 RLUSD deeper news pull is held, everything else in the demo is automatic.
AUTO_APPROVE_MAX = {"XRP": Decimal(config.env("AUTO_APPROVE_MAX_XRP", "1")),
                    "RLUSD": Decimal(config.env("AUTO_APPROVE_MAX_RLUSD", "0.40"))}


@dataclass
class Purchase:
    merchant_key: str        # fx | crypto | news | news_deep | alpha
    merchant: str            # display name
    item: str
    category: str            # e.g. fx_rates, trading_signals
    price: str               # decimal string, in `currency`
    currency: str            # XRP (XRPL rail) or RLUSD (AP4M rail)
    rail: str                # "xrpl" or "ap4m"
    pay_to: str              # where the money would go
    requires_passport: bool
    reason: str = ""         # the agent's explanation: logged, NEVER shown to the checker AI
    purchase_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def label(self) -> str:
        return f"{self.merchant} / {self.item} ({self.price} {self.currency})"


@dataclass
class Decision:
    decision: str            # APPROVE | HOLD | BLOCK
    reason: str
    task_fit_score: int      # 0-100, how well it fits the agent's task
    layer: str               # "rules" or "rules+llm"
    llm: str                 # "ONLINE" or "LLM OFFLINE (<why>)"
    ai_explanation: str = ""
    purchase_id: str = ""


def _rules(p: Purchase) -> tuple[str, str, int]:
    """Deterministic checks. Returns (decision, reason, task_fit_score)."""
    s = state.load()
    st = passport.get_passport_status()["status"]
    if st != "active":
        return "BLOCK", f"agent passport is not valid (status: {st})", 0
    price = Decimal(p.price)
    usual = Decimal(USUAL_PRICE.get(p.merchant_key, "0.05"))
    problems = []
    if p.merchant_key not in APPROVED_MERCHANTS:
        problems.append("merchant is not on Acme's approved list")
    if price > PRICE_MULTIPLE_LIMIT * usual:
        problems.append(f"price {price} {p.currency} is {price / usual:.0f}x the usual {usual} (limit {PRICE_MULTIPLE_LIMIT}x)")
    if problems:
        return "BLOCK", "; ".join(problems), 5
    spent = Decimal(s["spent_today"].get(p.currency, "0"))
    if spent + price > DAILY_BUDGET[p.currency]:
        return "BLOCK", f"daily budget {DAILY_BUDGET[p.currency]} {p.currency} would be exceeded (spent {spent})", 30
    if price > AUTO_APPROVE_MAX[p.currency]:
        return "HOLD", f"{price} {p.currency} is above the {AUTO_APPROVE_MAX[p.currency]} auto-approve limit: a human decides", 70
    return "APPROVE", f"approved merchant, price {price} {p.currency} within 3x of usual, inside the daily budget", 90


def structured_facts(p: Purchase) -> dict:
    """The ONLY things the checker AI is allowed to see (no merchant text, no agent explanation)."""
    return {"task": TASK, "merchant": p.merchant, "category": p.category, "price": p.price,
            "currency": p.currency, "usual_price": USUAL_PRICE.get(p.merchant_key, "unknown"),
            "on_approved_list": p.merchant_key in APPROVED_MERCHANTS,
            "past_prices_paid": state.load()["price_history"].get(p.merchant_key, [])[-5:]}


def _llm(p: Purchase, rules_verdict: str) -> dict | None:
    facts = structured_facts(p)
    return llm.ask_json(
        f"Purchase facts (structured, from AgentGuard's own records): {facts}\n"
        f"The hard rules said: {rules_verdict}.\n"
        "Does this purchase fit the agent's task? Decide APPROVE, HOLD (unsure: ask a human) or BLOCK, "
        'and explain briefly for a compliance officer. Reply ONLY with JSON: '
        '{"decision": "...", "reason": "...", "task_fit_score": <0-100>}',
        system="You are AgentGuard's strict corporate purchase checker for an AI treasury agent.")


def decide(p: Purchase) -> Decision:
    """Rules first; then the AI. The AI may only tighten the verdict."""
    verdict, reason, fit = _rules(p)
    layer, llm_status, explanation = "rules", f"LLM OFFLINE ({llm.offline_reason()[:60]})", ""
    if not reason.startswith("agent passport"):  # nothing for the AI to judge if the passport is gone
        j = _llm(p, verdict)
        if j and j.get("decision") in ("APPROVE", "HOLD", "BLOCK"):
            layer, llm_status, explanation = "rules+llm", "ONLINE", str(j.get("reason", ""))
            strictness = {"APPROVE": 0, "HOLD": 1, "BLOCK": 2}
            if strictness[j["decision"]] > strictness[verdict]:
                verdict, reason = j["decision"], f"checker AI: {explanation}"
            fit = min(fit, int(j.get("task_fit_score", fit))) if verdict != "APPROVE" else int(j.get("task_fit_score", fit))
    if not explanation and verdict == "BLOCK" and p.merchant_key not in APPROVED_MERCHANTS:
        explanation = "off-task for a risk report and a compliance red flag (rule-based note, LLM OFFLINE)"
    return Decision(verdict, reason, fit, layer, llm_status, explanation, p.purchase_id)


def review(p: Purchase) -> Decision:
    """Decide, log it, update strikes / approvals / holds, and fire the kill switch when due."""
    d = decide(p)
    severity = {"APPROVE": "good", "HOLD": "warn", "BLOCK": "bad"}[d.decision]
    title = f"Checker {d.decision}: {p.label}: {d.reason}"
    if d.ai_explanation and d.ai_explanation not in d.reason:
        title += f" | AI: {d.ai_explanation}"
    events.emit("checker", title, severity, decision=d.decision, merchant=p.merchant, item=p.item, price=p.price,
                currency=p.currency, reason=d.reason, ai_explanation=d.ai_explanation, task_fit_score=d.task_fit_score,
                layer=d.layer, llm=d.llm, purchase_id=p.purchase_id)
    if d.decision == "APPROVE":
        _approve(p)
    elif d.decision == "HOLD":
        state.mutate(lambda s: s["held"].__setitem__(p.purchase_id, {**asdict(p), "decision": asdict(d)}))
    else:
        _strike(p)
    return d


def _base_units(p: Purchase) -> str:
    """Amount as the signer will see it: XRP drops, or RLUSD wei (18 decimals)."""
    if p.currency == "XRP":
        return str(int(Decimal(p.price) * 1_000_000))
    return str(int(Decimal(p.price) * 10 ** config.RLUSD_DECIMALS))


def _approve(p: Purchase) -> None:
    def add(s):
        s["approved_purchases"][p.purchase_id] = {
            "merchant": p.merchant_key, "rail": p.rail, "amount": _base_units(p), "pay_to": p.pay_to,
            "requires_passport": p.requires_passport, "label": p.label}
        s["spent_today"][p.currency] = str(Decimal(s["spent_today"].get(p.currency, "0")) + Decimal(p.price))
        s["price_history"].setdefault(p.merchant_key, []).append(p.price)
    state.mutate(add)


def _strike(p: Purchase) -> None:
    if state.load()["frozen"]:
        return  # already frozen: no point counting more strikes
    s = state.mutate(lambda st: st.__setitem__("strikes", st["strikes"] + 1))
    n = s["strikes"]
    events.emit("strike", f"STRIKE {n}/{config.STRIKES_BEFORE_REVOKE}: refused purchase from {p.merchant}",
                "bad", strikes=n, limit=config.STRIKES_BEFORE_REVOKE)
    if n >= config.STRIKES_BEFORE_REVOKE:
        from agentguard import killswitch  # imported here to avoid a circular import
        killswitch.freeze(f"{n} refused purchases: possible manipulation")


def approve_held(purchase_id: str) -> bool:
    """A human approves a held purchase (dashboard button)."""
    held = state.load()["held"].get(purchase_id)
    if not held:
        return False
    p = Purchase(**{k: held[k] for k in Purchase.__dataclass_fields__})
    _approve(p)
    state.mutate(lambda st: st["held"].pop(purchase_id, None))
    events.emit("checker", f"Human APPROVED held purchase: {p.label}", "good", purchase_id=purchase_id)
    return True


def wait_for_human(purchase_id: str, timeout: float = 120.0) -> bool:
    """Block until a held purchase is approved (True) or rejected / timed out (False)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = state.load()
        if purchase_id in s["approved_purchases"]:
            return True
        if purchase_id not in s["held"]:
            return False  # rejected / reset
        time.sleep(1)
    state.mutate(lambda st: st["held"].pop(purchase_id, None))
    events.emit("checker", "Held purchase timed out with no human approval: dropped", "warn", purchase_id=purchase_id)
    return False


def reject_held(purchase_id: str) -> None:
    state.mutate(lambda st: st["held"].pop(purchase_id, None))
    events.emit("checker", "Human REJECTED held purchase", "warn", purchase_id=purchase_id)
