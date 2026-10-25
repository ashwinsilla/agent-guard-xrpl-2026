# Status (spec: docs/AgentGuard_Project_Brief.pdf, latest version)

- [x] Passport (XRPL Credential, level + expiry), issued/revoked with Acme's approver key (issuer's regular key)
- [x] Verified-only merchants (Deposit Authorization + DepositPreauth) for FX Rates and Crypto Prices
- [x] Co-signed agent wallet: signer list agent 1 / AgentGuard 1 / approver 2, quorum 2, master key disabled
- [x] Checker: hard rules (approved list, 3x price, daily budget) + Bedrock AI on structured facts only (labelled LLM OFFLINE without AWS creds)
- [x] AgentGuard co-signer (XRPL) and voucher gate (Mastercard AP4M)
- [x] Merchants: XRPL rail (FX, Crypto, attacker) + AP4M rail (News, deeper pull)
- [x] Kill switch: freeze (stop co-signing, close channel) -> approver confirm (CredentialDelete, refusal proofs, float swept)
- [x] Treasury Analyst agent: Strands + Bedrock, labelled OFFLINE planner fallback, labelled SIMULATED HIJACK scene
- [x] Dashboard (live SSE feed, buttons) + run_demo.py + preflight + reset
- [x] Tests (17, offline) + e2e_testnet.py (14/14 on testnet, hashes in PROOF.md)
- [x] Docs: README, DEMO_SCRIPT, MASTERCARD, PITCH_OUTLINE, SUBMISSION (char counts checked)
- [x] Mastercard AP4M LIVE: channel open, VoucherRedeemed + settlement + receipt proven (PROOF.md)
- [x] Bedrock ONLINE (Amazon Nova Pro; Claude Haiku 4.5 once the Anthropic use-case form is submitted): checker AI, news score, Strands agent
- [x] Quicknode: all XRPL traffic via the Quicknode testnet endpoint; live feed via Quicknode WebSocket (Streams webhook not connected)
- [ ] AgentCore Runtime deploy (needs AWS credentials)
- [ ] Ledger device / Speculos in the approver slot (software key today)
