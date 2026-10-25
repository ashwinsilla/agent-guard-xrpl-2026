# AgentGuard build plan

## What existed at the start (Layer 1 + 2a)
- `agentguard/xrpl_core.py`: proven XRPL passport helpers (CredentialCreate/Accept/Delete, Deposit Auth,
  DepositPreauth, Payment with CredentialIDs). Left unchanged.
- `agentguard/vendors.py` + `agent_client.py`: XRP-priced x402-style vendors (kept as the XRPL-rail demo).
- `scripts/`: wallet/vendor setup and the Layer 1 / 2a demos.

## What is being built (in order)
1. **Phase 1** `config`, `events`, `state`, `passport` (levels, expiry, "revoked" status), `setup_merchant`, `reset_demo`, `preflight`.
2. **Phase 2** `merchants/`: four pay-per-call merchants in RLUSD (402 -> voucher -> passport check -> data).
3. **Phase 3** `agentguard/ap4m.py`: Mastercard AP4M (auth, channel, voucher signing GATE, redeem, close). Ported from the
   official JS SDK (`https://hackathon.ap4m.build/sdk/ap4m-hackathon-sdk.js`). MOCK mode when no registered wallet/budget.
4. **Phase 4** `checker.py` (rules + Bedrock LLM) and `killswitch.py`.
5. **Phase 5** `agents/treasury_analyst.py` (Strands agent; AgentCore deploy notes).
6. **Phase 6** `dashboard/` (FastAPI + one HTML page, live SSE feed, Quicknode webhook/WebSocket).
7. **Phase 7** `run_demo.py`, `DEMO_SCRIPT.md`. **Phase 8** tests + `scripts/e2e_testnet.py`.
8. **Phase 9** Ledger signer (only if time). **Phase 10** README, SUBMISSION, MASTERCARD, PITCH_OUTLINE.

## Design decisions
- Env names keep the repo's existing `XRPL_*_SECRET` convention (not `*_SEED`) so Layer 1 keeps working.
- AP4M: a channel pays the *team's own* merchant, so all four merchants share one payout wallet; the scam merchant
  is never paid because the voucher gate refuses to sign for it.
- Whoever calls `redeemVoucher` is the merchant's submitter wallet (needs XRP gas); anyone may submit a valid agent-signed voucher.
