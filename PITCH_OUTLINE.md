# Pitch outline (short deck)

1. **Title:** AgentGuard: Know Your Agent, built into the XRP Ledger. Team, track (Agentic Finance), partners.
2. **Problem:** agents pay for things by themselves. Merchants can't tell whose agent is paying; companies can't stop a rogue one everywhere. Today it's all or nothing.
3. **Analogy:** employee ID badge + a manager who countersigns + security deactivating the badge, except that the XRP Ledger refuses the payment itself.
4. **Use case:** Acme's AI Treasury Analyst buys FX, crypto (XRP Ledger) and news (Mastercard AP4M) to write the daily risk report.
5. **How it works:** the 4 layers (passport, verified-only merchants, co-signing checker, kill switch) and the signer-list diagram (agent 1, AgentGuard 1, Acme approver 2, quorum 2, master key off).
6. **Live demo** (DEMO_SCRIPT.md).
7. **Novelty:** (a) the ledger blocks unverified agents, with no merchant SDK; (b) one action cuts the agent off everywhere, attacker included, because its wallet can't sign alone; (c) an AI task-fit check whose verdict validators enforce.
8. **Proof:** the PROOF.md table: tesSUCCESS co-signed, tefBAD_QUORUM, tecBAD_CREDENTIALS, tecNO_PERMISSION, float returned.
9. **Partners:** XRPL, Mastercard AP4M (live), AWS Strands/Bedrock, Ledger (approver slot), Quicknode (all ledger traffic + the live feed as an independent witness).
10. **Honest limitations + next steps:** deploy the checker to AgentCore Runtime (packaged; blocked by our new account's S3/ECR policy), a Ledger device in the approver slot, a checker accuracy benchmark, an RLUSD trustline on the XRPL lane.

## Likely judge questions

**"Doesn't Mastercard already do this?"** Mastercard verifies and permissions agents inside its network. AgentGuard implements the credential and permission pillars natively on the XRP Ledger, adds a task-fit check, and adds instant AI-triggered revocation. It governs the agent's Mastercard lane too: vouchers only after checks, channel closed on kill. It's complementary.

**"Why would merchants adopt this?"** It's one account setting and no code. A merchant doesn't have to block its other customers: it opens a separate "verified agents" address with Deposit Authorization on, and only agent customers who want it pay there. The value: it knows who is paying *before* accepting. Today, merchants taking crypto from anonymous agents can only screen known-bad addresses after the fact. Be honest: AgentGuard's main value is for the agent's owner (co-signing and the kill switch work even if no merchant opts in).

**"What if the agent is hacked?"** It holds one key of weight 1; the quorum is 2. Its lone signature is refused by the ledger (we show `tefBAD_QUORUM`). In production, to steal, an attacker must break into two separate systems (the agent *and* AgentGuard, which would run as a separate service with its own key storage), and even then can take only the small daily float. Be upfront: in our demo all keys sit on one laptop, so the separation is the architecture, not this deployment. Acme's approver key outranks both and can revoke and pull the funds back.

**"What if the checker AI is wrong?"** The hard rules decide the obvious cases (the 100× attack is blocked before the AI is asked). The AI can only make verdicts stricter; unsure → hold for a human. We don't have an accuracy number yet; the next step is a labelled set of ~100 on-task, off-task and attack purchases to measure wrong approvals, wrong blocks and latency.

**"What if the checker itself gets prompt-injected?"** It never sees merchant text or the agent's explanation, only structured facts from AgentGuard's own records (task, merchant, category, price, usual price, past prices). There's a unit test for that.

**"How does AgentGuard know the agent tried to pay alone?"** Honestly: it can't, in general. A refused `tef…` transaction never reaches a ledger. In the demo the agent's runtime reports the attempt. In production the freeze is driven by repeated refusals. The important part holds regardless: the ledger refuses the agent's lone signature, so no money moves.

**"Isn't it just your software refusing on the EVM rail?"** Partly, and we say so. On the main XRP Ledger the validators enforce both the passport and the co-signature. On the EVM rail it's the merchant's passport check, AgentGuard's voucher gate, and closing the funded channel, so the agent loses its lane, not just our approval.

**"Who issues passports? Business model?"** The agent's owner or a trusted verification provider; merchants choose which issuers to trust. Issuers pay to issue and manage passports; merchants get protection free with one setting.
