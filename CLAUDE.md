# AgentGuard — "Know Your Agent, built into the XRP Ledger"

Hackathon: AI & Fintech XRPL Hackathon (New York, Oct 24–25, 2026), Agentic Finance track.

## Use case
Acme Corp's AI Treasury Analyst agent buys market data (FX rates, crypto prices,
news sentiment) from pay-per-call vendors to write a daily risk report.

- The ISSUER (Acme) issues the AGENT's wallet an on-ledger passport (XRPL Credential) with a type and an expiry.
- MERCHANTS (data vendors) enable Deposit Authorization and preauthorize that credential type,
  so the XRP Ledger itself refuses payments from agents without a valid passport.
- Later layers (NOT built yet): a checker AI reviews purchases (AWS Bedrock/Strands);
  repeated failures trigger the kill switch (CredentialDelete); payments also go through
  Mastercard AP4M (RLUSD on XRPL EVM).

Python only. XRPL testnet JSON-RPC: https://s.altnet.rippletest.net:51234/

## Rules
1. Python only, using the existing `.venv` (xrpl-py 5.2.0, python-dotenv, web3, fastapi, requests). Don't install new packages without asking.
2. NEVER print, log or show any secret/seed/private key, in the terminal or in messages.
3. In `.env`, only ADD lines; never change or delete existing ones. Never commit `.env`.
4. XRPL testnet only.
5. If `XRPL_AGENT_SECRET` is missing from .env, STOP and tell the user to add it themselves (never ask them to paste it).
6. Write clear beginner-friendly comments in every file.

## Folder layout
- `agentguard/` — reusable Python package (shared code)
- `scripts/` — runnable scripts
- `docs/` — notes
