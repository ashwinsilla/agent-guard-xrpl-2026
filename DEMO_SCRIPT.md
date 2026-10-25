# 3-minute demo script

**Before judges arrive:** `.venv/bin/python scripts/reset_demo.py`, then `.venv/bin/python run_demo.py`, and open
http://127.0.0.1:8080 full-screen. Preflight must show **0 failures**. Also open in a browser tab the agent account on the explorer:
https://testnet.xrpl.org/accounts/rMJefsPRgw7VW71PdTpbF9VL2ELM3jt2JE (it shows the signer list).

| Time | Click | Say |
|---|---|---|
| 0:00–0:30 | nothing (dashboard on screen) | "AI agents now pay for data by themselves. A merchant can't tell whose agent is paying, and a company can't stop a rogue agent everywhere at once. AgentGuard is an employee ID badge for agents, enforced by the XRP Ledger itself." |
| 0:30–1:00 | point at the **Passport** card (ACTIVE) and the **Agent wallet** card | "Acme issued this passport with its approver key. It's a real XRPL Credential with an expiry, public on the explorer. The agent's wallet has its master key switched off: the ledger needs two signatures, the agent's and AgentGuard's." |
| 1:00–1:45 | **▶ Start agent** | "No human from here. The agent buys FX rates and crypto prices on the XRP Ledger, presenting its passport. Each payment is checked and co-signed by AgentGuard. News comes through Mastercard Agent Pay for Machines, an RLUSD voucher that AgentGuard's gate signs. Here's the risk report." (click an explorer link on a `CO-SIGNED … tesSUCCESS` line) |
| (1:30) | if a **Held for a human** card appears: **Approve** | "Bigger purchases, like this deeper news pull, wait for a person. One click." (Set `VOLATILITY_THRESHOLD=30` in `.env` to make sure the deeper pull happens on a calm news day.) |
| 1:45–2:15 | point at the red **Checker BLOCK** lines | "The attacker, Premium Alpha Signals, slipped a prompt injection into the news feed: insider tips for 5 XRP, 100× the normal price. AgentGuard refuses to co-sign: not on Acme's approved list, 100× the usual price. The checker AI never reads the attacker's text, only structured facts." |
| 2:15–2:45 | point at **tefBAD_QUORUM**, **KILL SWITCH FIRED**, then **🔑 Confirm revoke** | "The manipulated agent tries to pay the attacker directly. The XRP Ledger itself refuses: AgentGuard didn't sign. (A refused attempt never reaches a ledger, so there's no explorer page; the code is the ledger server's answer.) AgentGuard freezes the agent and closes its Mastercard channel. Acme confirms with its approver key: passport revoked, float back in the treasury, and look: a payment to FX Rates with the old passport is refused by the ledger, `tecBAD_CREDENTIALS`." |
| 2:45–3:00 | (optional) **↻ Re-issue passport** | "Open, ledger-enforced trust for AI agents. A merchant needs one account setting: no SDK, no vendor. And once it's safe, Acme re-issues with one approval." |

## If something goes wrong
- **Wi-Fi or a data API is down:** merchants serve the last good data marked `cached: true`; the payments still run.
- **XRPL testnet slow:** each payment can take 5–10 s; keep talking through the feed. `PROOF.md` has the hashes from a full rehearsal run.
- **Agent stuck or busy:** wait for the ⏳ to clear, then **⟲ Reset demo** (about 20 s) and **▶ Start agent** again.
- **Nothing works:** show `PROOF.md` (every step with explorer links) and run `.venv/bin/python -m pytest -q` live.

## Labels you may see (be upfront about them)
- **REHEARSAL (channel close):** with `KILL_SWITCH_CLOSE_REAL_CHANNEL=false` the Mastercard channel close is simulated; everything else on that lane is live.
- **LLM OFFLINE:** no AWS credentials or Bedrock model; the checker runs its hard rules and the agent runs a fixed plan with the same tools.
- **SIMULATED HIJACK:** the attack scene is scripted, because a well-aligned model usually ignores the injection.

## Mastercard judging (5-minute version)
Mastercard's track uses a 5-minute demo. Add after 1:45: **⛔ Over-cap test** ("the spend limit is enforced by AgentGuard and by the
PaymentLedger itself"), and click the **Verifiable AP4M receipt** link in the feed (channel + claim + payout). See `MASTERCARD.md`.
