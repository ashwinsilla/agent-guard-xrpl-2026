# AgentGuard build plan (follows docs/AgentGuard_Project_Brief.pdf, latest)

1. Multi-signed agent wallet (`scripts/setup_agent_wallet.py`, `agentguard/multisig.py`): agent 1, AgentGuard 1, approver 2, quorum 2, master off. Done.
2. AgentGuard co-signer (`agentguard/cosigner.py`): co-signs only the exact purchase the checker approved. Done.
3. Checker (`agentguard/checker.py`): hard rules (approved list, 3x, daily budget) then Bedrock on structured facts. Done.
4. Merchants on two rails (`merchants/app.py`): XRPL (FX, Crypto, attacker, in XRP) and AP4M (News, in RLUSD). Done.
5. Kill switch in two stages (`agentguard/killswitch.py`). Done.
6. Agent (`agents/treasury_analyst.py`), dashboard (`dashboard/`), `run_demo.py`, preflight, tests, e2e proof, docs. Done.
7. Open items: see STATUS.md and BLOCKERS.md.

Design notes
- Signers don't need funded accounts; the agent-signer, AgentGuard and approver keys are key pairs only.
- `tef*` refusals (`tefBAD_QUORUM`) never reach a ledger, so the dashboard shows the code without an explorer link.
- Accepting a passport needs a little free XRP for the ledger reserve, so reset/re-issue refill the float first.
- Merchants, dashboard and agent run in one process (`run_demo.py`) so the shared `data/state.json` is safe.
