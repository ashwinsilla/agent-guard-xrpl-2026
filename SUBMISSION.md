# Submission form fields (ready to paste)

Character counts are checked by `scripts/check_submission.py`.

## Project name
AgentGuard

## Track
Agentic Finance

## Prizes to tick
Agentic Finance track · Mastercard (Agent Pay for Machines) · AWS (Agentic Finance) · Ledger · Quicknode

## Repository
https://github.com/ashwinsilla/agent-guard-xrpl-2026

## Short description
<!-- short -->
Know Your Agent, built into the XRP Ledger: AI agents get an on-ledger passport, every payment needs AgentGuard's co-signature, and a kill switch cuts a rogue agent off everywhere.
<!-- /short -->

## Description
<!-- description -->
AI agents are starting to pay for the data and services they use. That raises two problems: merchants can't tell which agent is paying, and companies can't stop a rogue agent everywhere at once. Today the choice is all or nothing: give the agent full access and hope, or approve every payment by hand.

AgentGuard is an employee ID badge for AI agents, enforced by the XRP Ledger itself.

1. Passport: Acme issues its AI Treasury Analyst an XRPL Credential with an expiry ("valid today") and a level label ("small purchases"), approved with Acme's approver key (a Ledger device in production).
2. Verified merchants only: data vendors switch on Deposit Authorization and preauthorize Acme's passport type. The ledger's validators refuse payments from agents without a valid passport: no SDK, no merchant code.
3. Co-signing checker: the agent's wallet has its master key disabled and a signer list (agent 1, AgentGuard 1, Acme approver 2, quorum 2). The agent can't pay alone. AgentGuard co-signs only after hard rules (approved merchant, price within 3x of usual, daily budget) and a checker AI on Amazon Bedrock that judges whether the purchase fits the agent's task, using structured facts only, never merchant text or the agent's own reasoning.
4. Kill switch: repeated refusals freeze the agent at once (in the demo, the agent's runtime also reports a direct-payment attempt). AgentGuard stops co-signing and closes the agent's Mastercard channel. Acme then confirms with its approver key: the passport is deleted and the remaining float returns to the treasury.

The demo: the agent buys live FX rates and crypto prices on the XRP Ledger (co-signed, presenting its passport) and news sentiment through Mastercard Agent Pay for Machines (RLUSD vouchers that AgentGuard's gate signs), then writes the morning risk report. A fake vendor injects an "insider signals" offer at 100x the price. AgentGuard refuses to co-sign; the manipulated agent tries to pay the attacker directly and the XRP Ledger rejects it (tefBAD_QUORUM). The kill switch fires, the passport is revoked, and a payment to an honest vendor with the old passport now fails on the ledger (tecBAD_CREDENTIALS). Every step is visible on the public explorer and on a live dashboard.

What's new: the blockchain itself blocks unverified agents; one action cuts an agent off from everyone, attacker included; and an AI judgment about task fit is enforced by the ledger's validators, not by the agent's goodwill.

Honest limits: the attack scene is a labelled simulation; a software key stands in for the Ledger device; in the demo all signer keys sit on one machine (the design separates them).
<!-- /description -->

## Technical description
<!-- technical -->
Python 3.12. xrpl-py on XRPL testnet: CredentialCreate/Accept/Delete, Deposit Authorization + DepositPreauth (AuthorizeCredentials), Payments with CredentialIDs, SignerListSet + asfDisableMaster multi-signing (agent 1, AgentGuard 1, approver 2, quorum 2), and the approver as the issuer's regular key. x402-style FastAPI merchants verify payments on-ledger. Mastercard AP4M lane (live): EIP-712 vouchers over x402 (PAYMENT-SIGNATURE) on XRPL EVM testnet (chain 1449000), voucher gate, background redeemVoucher + settle with receipts, over-cap check, channel close. Strands Agents + Amazon Bedrock for the agent and checker AI, with labelled offline fallbacks. Live FastAPI/SSE dashboard; all XRPL traffic via Quicknode RPC, live ledger feed via Quicknode WebSocket.
<!-- /technical -->
