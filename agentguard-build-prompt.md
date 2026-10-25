> **Superseded:** the latest spec is `docs/AgentGuard_Project_Brief.pdf` (co-signed XRPL wallet, XRP prices, News-only AP4M, 3x rule). This file is kept for history.

# AgentGuard: complete the project for hackathon submission

You are finishing **AgentGuard** in this repository (`agent-guard-xrpl-hackathon`) for the AI & Fintech XRPL Hackathon (team "gizmo geeks", Agentic Finance track). Work autonomously from start to finish. The final project submission closes **Sunday Oct 25, 12:30 PM EDT**, so prioritise a working, demo-ready, well-documented project over perfection.

---

## 0. HARD RULES (never break these)

1. **Never stage anything.** Do not run `git add`, `git add -p`, `git rm`, `git mv`, or anything else that touches the index.
2. **Never commit.** No `git commit`, `git commit --amend`, `git merge`, `git rebase`, `git cherry-pick`, `git tag`, `git push`, `git stash`, `git reset`, `git restore --staged`, `git checkout -- <file>`, or `git clean`. Do not edit anything inside `.git/`. The human will stage and commit everything himself.
3. Read-only git is fine: `git status`, `git diff`, `git log`, `git show`.
4. **Secrets:** never hardcode, print or log seeds, private keys, API keys or tokens. Everything secret lives in `.env` (make sure `.env` is listed in `.gitignore`; editing `.gitignore` is fine, just don't stage it). Provide `.env.example` with placeholder values and a comment per variable.
5. **Never fake results.** If something can't be done for real (missing credentials, API down, unsupported feature), build a clearly labelled fallback (`MOCK`/`OFFLINE` shown in logs and on the dashboard), record it in `BLOCKERS.md`, and keep going. Never present mocked output as real on-chain activity.
6. **Ask before irreversible or budget-consuming actions:** onboarding the agent on AP4M (this locks the 20 RLUSD budget), closing a real AP4M payment channel, or any action you cannot undo. Everything else, just do.
7. **Don't delete or rewrite the human's existing work** without reason. Layer 1 (XRPL passport) is already proven at commit `f326811`: build on it, refactor carefully, and keep its behaviour.
8. **Do not read online docs from memory.** For AP4M, Strands, AgentCore, Quicknode and the Ledger DMK, read the real docs/SDK first and follow them. Don't invent endpoints or method names.

---

## 1. What AgentGuard is (the story the code must tell)

**Problem:** AI agents now pay for data and services by themselves. Merchants can't verify which agent is paying, and companies can't stop a rogue agent everywhere at once.

**Solution:** every AI agent gets a **passport** on the XRP Ledger. A **checker AI** reviews every purchase against the agent's task. A **kill switch** revokes a rogue agent's passport and closes its Mastercard payment channel in seconds.

**Use case:** Acme Corp's **AI Treasury Analyst** agent must produce a daily FX and crypto risk report. It buys data, paying per call in **RLUSD** via **Mastercard Agent Pay for Machines (AP4M)**, from:

| Merchant | Sells | Price/call |
|---|---|---|
| FX Rates Co. | Live EUR/USD, USD/JPY (real public data) | 0.01 RLUSD |
| Crypto Prices Co. | Live XRP, BTC (real public data) | 0.01 RLUSD |
| News Sentiment Co. | Today's market headlines + AI risk score | 0.05 RLUSD |
| "Premium Alpha Signals" (scam) | "Insider trading signals" | 5 RLUSD (100× normal) |

**Demo flow:**
1. Acme issues the agent a passport (approved on a Ledger device if available).
2. The agent autonomously buys FX, crypto and news data. If news shows high volatility, it decides by itself to buy a deeper data pull.
3. The agent writes the morning risk report.
4. The scam merchant injects an offer for insider tips. The checker AI **blocks** it (off-task, overpriced, compliance red flag).
5. The scam keeps pushing and the agent keeps trying: a sign of manipulation. After repeated blocks (default 3 strikes), the **kill switch** fires: `CredentialDelete` on XRPL + the AP4M channel is closed. Every honest merchant now refuses the agent, and the next XRPL payment fails with `tecBAD_CREDENTIALS`.
6. Acme re-issues the passport with one approval.

**Important design truths (reflect these in code and docs):**
- The scam merchant will never enable Deposit Authorization, so **revoking the passport does not by itself stop payments to the scammer**. What protects Acme's money is: (a) the checker AI refusing, (b) AgentGuard **refusing to sign AP4M vouchers** for blocked or revoked agents (the agent's payments must go through AgentGuard's signing gate; it must not be able to bypass it in the demo), and (c) the kill switch closing the funded AP4M channel. The passport is how **honest merchants** know who they're dealing with.
- On the main XRPL, validators enforce passports (Deposit Authorization + credential). On the AP4M EVM rail, enforcement is: merchants check the passport on XRPL before serving, AgentGuard's voucher-signing gate, and channel closure.
- Merchant value proposition: a free "verified business customers" tier with one account setting and no code. Verified agents can get credit, higher limits and licensed data.

---

## 2. Known facts and addresses

**XRPL testnet (main ledger):**
- Agent `rMJefsPRgw7VW71PdTpbF9VL2ELM3jt2JE`
- Issuer (Acme) `r4tL45QHUTg1sMMG4geyCYvZ5AvhXPh3Gt`
- Merchant `rBYEkseGfQAYStADBY6Bco1x3Rq2rMzH7G`
- Proven: no passport → `tecNO_PERMISSION`; with passport → `tesSUCCESS`; after revoke → `tecBAD_CREDENTIALS`; re-issue → `tesSUCCESS`.
- Uses xrpl-py: CredentialCreate / CredentialAccept / CredentialDelete, Deposit Authorization (`asfDepositAuth`), DepositPreauth with `AuthorizeCredentials`, Payment with `CredentialIDs`.
- Passports should carry a **level** (encode in the credential type, e.g. `AGENT_PASSPORT_SMALL`) and an **expiry** (`Expiration` field, e.g. end of today).

**Mastercard AP4M (XRPL EVM testnet):**
- Chain ID `1449000` · RPC `https://rpc.testnet.xrplevm.org` · Explorer `https://explorer.testnet.xrplevm.org` · gas in XRP
- PaymentLedger `0xcAB42800A5ECF0D253Fa2581Bb3334B4DAEfaE91`
- ParticipantRegistry `0x4cF27435FE56161aa9b1cffdD87784aa68b7D1E8`
- PooledEscrowVault `0x83DD9cD010eb46e96eceF8F7eB0a18f7845AaBC0`
- RLUSD `0x27b57a9D0b8d24EB97259c4E2279e45255e016f3` (18 decimals)
- API base `https://hackathon.ap4m.build`; SDK and examples at `https://hackathon.ap4m.build/sdk/` → **read these first**
- Voucher: EIP-712, domain `{name: "AP4M Payment Ledger", version: "1", chainId, verifyingContract: PaymentLedger}`; type `Voucher {bytes32 channelId, uint256 cumulativeAmount}`. **cumulativeAmount is the running total, not the increment.** Persist the per-channel running total to disk so restarts don't break it.
- `redeemVoucher((bytes32 channelId, uint256 cumulativeAmount) voucher, bytes agentSignature)`
- Auth: `POST /public/participant/challenge {teamName, wallet}` → sign the message → `POST /public/participant/session {challengeId, signature}` → Bearer token.
- Budget 20 RLUSD, locked once the agent is onboarded. Spend carefully; the 5 RLUSD scam purchase must never actually be paid.
- Mastercard judging criteria: autonomy (no human in the loop), load-bearing payment, **VoucherRedeemed** event on-chain, merchant payout **RLUSD balance changes**, live 3-minute demo, creativity.
- Find out from the SDK how channels are opened/closed and whether a new channel can be opened after closing. Design the kill switch so the demo can be **rehearsed repeatedly** without burning the real channel (e.g. a `KILL_SWITCH_CLOSE_REAL_CHANNEL=false` flag during rehearsal; true for the live demo), and document this.

**Ledger (optional, built last):**
- Docker Desktop, Node.js 22+, Chrome; Speculos emulator `ghcr.io/ledgerhq/speculos`, Stax model
- Ports 5000 (transport + web page), 9999 (APDU), 41000 (VNC). On macOS, AirPlay Receiver uses port 5000.
- Workshop repo: `github.com/LedgerHQ/device-management-kit-ts-workshop/tree/main/xrpl-hackathon`
- Signing: path `44'/144'/0'/0/0` → autofill → `encode` (not `encodeForSigning`) → `signTransaction` → set `TxnSignature` → submit. Set `LastLedgerSequence` manually (autofill leaves only ~1 minute).

**Prizes being entered:** Agentic Finance track ($6k), Mastercard ($6k), AWS Agentic Finance ($2k: "Agentic payments stack (AgentCore + x402/RLUSD)"), Ledger ($3k: device as real trust layer, ≥1 tx on XRPL or EVM sidechain, docs feedback valued), Quicknode ($3k: best use of Quicknode).

---

## 3. Language and stack

- **Python for everything** (3.11+), managed with a `venv` and a pinned `requirements.txt`.
- **Exception:** one small Node.js/JavaScript helper for Ledger signing in `ledger-signer/`, called from Python via subprocess (JSON in, signed blob out). Keep it small and self-contained; the team will not edit it.
- Merchants and dashboard: FastAPI + uvicorn. Dashboard frontend: a single plain HTML/JS/CSS page served by FastAPI (no build step), using Server-Sent Events or WebSocket for the live feed.
- Agents: **Strands Agents** with an Amazon Bedrock model; deploy to **Amazon Bedrock AgentCore** Runtime. Put the model ID in config (verify it's available in the configured region); don't hardcode it.
- EVM: `web3.py` + `eth-account` for EIP-712 signing and contract calls.
- XRPL: `xrpl-py`. All XRPL JSON-RPC/WebSocket traffic goes through the **Quicknode** endpoint from `.env` (fall back to the public testnet URL only if unset, and log a warning).

---

## 4. How to work

1. **Recon first (≈10 min):** read the whole repo, `git log`, existing scripts and `.env`. Run the existing Layer 1 code to confirm it still works. Then write `PLAN.md` (what exists, what you'll build, in what order) and keep `STATUS.md` updated as you finish each phase.
2. **Credentials check:** compare `.env` with everything needed below. List **all** missing variables to the human in **one** message, then carry on with everything that doesn't need them.
3. Build in the phase order below. **After every phase the project must still run end-to-end in some form.** Must-haves first, nice-to-haves after.
4. Test as you go against the real testnets. Record every real transaction hash in `PROOF.md` with explorer links.
5. Keep code readable for beginners: short modules, docstrings, comments explaining *why*. The human is new to blockchain and will explain this code to judges.

### Environment variables to support (`.env.example`)
`XRPL_RPC_URL` (Quicknode), `XRPL_WS_URL` (Quicknode), `ISSUER_SEED`, `AGENT_SEED`, `MERCHANT_SEED` (+ one per merchant if separate accounts), `EVM_RPC_URL`, `AGENT_EVM_PRIVATE_KEY`, `MERCHANT_EVM_PRIVATE_KEY` (or per merchant), `AP4M_API_BASE`, `AP4M_TEAM_NAME=gizmo geeks`, `AWS_REGION`, `BEDROCK_MODEL_ID`, AWS credentials (via the standard AWS profile or env vars), `QUICKNODE_WEBHOOK_SECRET`, `USE_LEDGER=false`, `KILL_SWITCH_CLOSE_REAL_CHANNEL=false`, `STRIKES_BEFORE_REVOKE=3`, `DEMO_MODE=live`.

---

## 5. Phases

### Phase 1: Core package and XRPL passport (MUST)
Create a package `agentguard/` and refactor the proven Layer 1 into `agentguard/passport.py`:
- `issue_passport(level, expires_at)` (issuer CredentialCreate), `accept_passport()` (agent CredentialAccept), `revoke_passport()` (issuer CredentialDelete), `get_passport_status()` (exists / accepted / expired / revoked, read from the ledger), `pay_with_passport(dest, amount)` (Payment with `CredentialIDs`).
- `scripts/setup_merchant.py`: idempotently enable Deposit Authorization and DepositPreauth for the Acme passport type on merchant account(s).
- `scripts/preflight.py`: checks env vars, balances (XRP, RLUSD), passport state, merchant settings, Quicknode reachability, AP4M auth, Bedrock access. Prints a clear green/red checklist.
- `scripts/reset_demo.py`: puts everything back into the "start of demo" state (re-issues and accepts the passport, clears strikes, resets local state) so the demo can be run again and again.
- Every action writes an event to a shared event log (`agentguard/events.py`, JSON lines file + in-memory pub/sub) that the dashboard reads.

### Phase 2: Merchants with x402-style pay-per-call (MUST)
`merchants/` FastAPI app(s) for the four merchants (one app with four routers on different paths/ports is fine).
- Unpaid request → HTTP **402** with payment requirements (merchant, price, currency RLUSD, payment rail details, required passport issuer/type).
- Paid request (payment proof in a header, e.g. a signed AP4M voucher) → merchant **verifies the agent's passport on XRPL** (valid, accepted, not expired, issued by a trusted issuer), verifies the payment/voucher, then serves the data. No valid passport → `403` with a clear reason.
- Real data: FX from a free public API (e.g. Frankfurter or open.er-api.com), crypto from CoinGecko's public API. News: real headlines from a free public RSS feed, with a risk score from Bedrock. Cache the last good response and serve it if the upstream API fails, flagged `cached: true`.
- "Deeper data pull" endpoint on News Sentiment (higher price, e.g. 0.05–0.10 RLUSD) that the agent buys only when volatility is high.
- Premium Alpha Signals: same 402 interface, price 5 RLUSD, and it pushes a **prompt-injection offer** (e.g. inside a response field or an "ad" the agent sees) urging the agent to buy insider signals. Make the attack deterministic when `DEMO_MODE` triggers it.

### Phase 3: Mastercard AP4M payments (MUST, ask before onboarding)
`agentguard/ap4m.py`, built from the official SDK/examples:
- Participant auth (challenge → sign → session token), registration/onboarding of agent and merchant(s) as the SDK requires, opening/funding a channel.
- **Voucher signing gate:** `sign_voucher(channel_id, increment)` lives in AgentGuard, not in the agent. It refuses to sign if the passport is revoked/expired or if the checker hasn't approved that specific purchase. It tracks and persists the cumulative amount.
- Merchant side: `redeemVoucher` on-chain, then confirm the **VoucherRedeemed** event and the merchant's **RLUSD balance change**; push both to the event log with explorer links.
- Kill switch hook: `close_channel()` per the SDK (respect `KILL_SWITCH_CLOSE_REAL_CHANNEL`).
- Batch redemption is fine (e.g. merchant redeems the latest cumulative voucher after each purchase or every N purchases) as long as at least several real VoucherRedeemed events happen in the demo.

### Phase 4: Checker AI and kill switch (MUST)
`agentguard/checker.py`:
- Input: agent task, merchant, item, price, merchant's usual price, the agent's stated reason, recent purchase history.
- Two layers: (1) **deterministic rules** first (price > 10× usual → BLOCK; merchant not on the approved list → HOLD or BLOCK; passport invalid → BLOCK; daily budget exceeded → BLOCK), so the demo is reliable; (2) a **Strands/Bedrock LLM judgment** returning structured output `{decision: APPROVE|HOLD|BLOCK, reason, task_fit_score}`. If Bedrock is unavailable, fall back to rules only and label it `LLM OFFLINE`.
- HOLD → waits for human approval from the dashboard (approval via Ledger device if `USE_LEDGER=true`).
- Strike counter: each BLOCK is a strike; at `STRIKES_BEFORE_REVOKE` → `agentguard/killswitch.py` runs `revoke_passport()` + `close_channel()` + marks the agent revoked, and logs everything. Also expose a manual **KILL** action.
- After revoke, demonstrate both enforcement paths: an honest merchant refuses (passport check fails) and a direct XRPL payment to the merchant fails with `tecBAD_CREDENTIALS`. Log the tx hash.

### Phase 5: Treasury Analyst agent (MUST)
`agents/treasury_analyst.py`, a Strands agent with tools: `list_merchants`, `buy_data(merchant, item, reason)` (goes through checker → voucher gate → merchant), `write_report(...)`.
- The agent decides by itself what to buy (including the deeper pull when volatility is high), then writes a concise morning risk report (EUR, JPY and XRP exposure moves, news risks) saved to `reports/` and shown on the dashboard.
- The scam merchant's injected offer reaches the agent so it genuinely tries to buy; the checker blocks it repeatedly until the kill switch fires.
- Run locally first. Then **deploy the agent (and checker if practical) to Bedrock AgentCore Runtime** following the official AgentCore docs, and document the deploy steps. If AgentCore deploy fails, keep the local version working, note it in `BLOCKERS.md`, and move on.

### Phase 6: Dashboard with Quicknode live feed (MUST)
`dashboard/` FastAPI + single HTML page:
- Panels: passport status (level, expiry, issuer, live from ledger), live event feed (payments, VoucherRedeemed, checker decisions with reasons, strikes, revocation), merchant RLUSD balances, the risk report, explorer links (`https://testnet.xrpl.org/transactions/<hash>` and `https://explorer.testnet.xrplevm.org/tx/<hash>`).
- Buttons: **Start agent**, **Approve held purchase**, big red **KILL SWITCH**, **Re-issue passport**, **Reset demo**.
- Quicknode: all XRPL traffic via the Quicknode endpoint. Check the Quicknode docs for **Streams/webhooks** support for XRPL testnet. If supported, add `POST /webhooks/quicknode` (verify the secret) to feed on-ledger events into the live feed, and document how to expose it (e.g. ngrok). If not usable in time, subscribe to the agent/issuer/merchant accounts over the Quicknode WebSocket instead and document that honestly.
- Looks clean and readable on a projector: large fonts, clear green/amber/red states.

### Phase 7: One-command demo (MUST)
- `run_demo.py` (or a `Makefile`) that starts merchants + dashboard, runs preflight, and lets the human drive the 3-minute demo from the dashboard.
- `DEMO_SCRIPT.md`: exact 3-minute script with timings (0:00 problem → 0:30 passport issued → 1:00 autonomous buying + report → 1:45 attack blocked → 2:15 kill switch + ledger refusal + channel closed → 2:45 why it matters), what to click, what to say, and a backup plan if Wi-Fi or an API fails.

### Phase 8: Tests (MUST, keep light)
`pytest` tests for: checker rules, strike counter → kill switch trigger, voucher cumulative-amount logic and EIP-712 signature (recover the signer and compare), x402 merchant flow (402 → paid → 200, no passport → 403) with mocks. Plus `scripts/e2e_testnet.py` that runs the full scenario against the real testnets and writes hashes into `PROOF.md`.

### Phase 9: Ledger signer (NICE-TO-HAVE, only if everything above works)
- `ledger-signer/` Node helper based on the workshop repo, working with Speculos (and a real device if connected).
- Python wrapper `agentguard/ledger_signer.py`; with `USE_LEDGER=true`, CredentialCreate (issue), CredentialDelete (revoke) and HOLD approvals require on-device confirmation.
- Get at least one real Ledger-signed transaction on XRPL testnet into `PROOF.md`.
- Write `LEDGER_DOCS_FEEDBACK.md`: honest notes on what was confusing or missing in Ledger's docs (judges value this).

### Phase 10: Submission materials (MUST)
- `README.md`: problem, solution (with the employee-ID-badge analogy), architecture diagram (Mermaid), how each partner is used (XRPL, Mastercard AP4M, AWS Strands/AgentCore, Ledger, Quicknode), setup, how to run, demo walkthrough, proof table of real tx hashes, honest limitations, the merchant-adoption argument, and the "scam merchant / voucher gate" truth from section 1.
- `SUBMISSION.md`: ready-to-paste form fields with character counts checked by code: project name, **short description ≤200 chars**, **description ≤5,000 chars**, **technical description ≤1,000 chars**, repo URL placeholder, track = Agentic Finance, and the prizes to tick.
- `MASTERCARD.md`: how the project meets each AP4M criterion, with tx hashes for VoucherRedeemed and RLUSD balance changes.
- `PITCH_OUTLINE.md`: slide-by-slide outline for a short pitch deck, plus answers to likely judge questions ("Doesn't Mastercard already do this?", "Why would merchants adopt this?", "What if the checker AI is wrong?", "What if the agent is hacked?", "Isn't it just your software refusing on the EVM rail?").
- Make sure no secrets appear anywhere in tracked files, and that `requirements.txt`, `.env.example` and `.gitignore` are complete.

---

## 6. Finish

1. Run `scripts/reset_demo.py`, then the full demo end-to-end once more, and confirm it works.
2. Run the test suite and report results.
3. Run `git status` and `git diff --cached --stat`. **Confirm the index is empty (nothing staged) and no commits were made since you started.**
4. Give the human a short final summary: what works for real, what is fallback/mocked and why, remaining blockers, the exact commands to run the demo, and a suggested list of logical commits (file groups + commit messages) he can make himself.