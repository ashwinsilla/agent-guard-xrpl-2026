# AgentGuard × Mastercard Agent Pay for Machines (AP4M)

**What it does:** News Sentiment Co. is paid per call in **RLUSD on the XRPL EVM testnet (chain 1449000)** through an AP4M
channel. AgentGuard governs that lane like the XRP Ledger lane: the agent can't get a voucher signed unless AgentGuard's checks pass,
and the kill switch closes the channel.

## The four AP4M pillars

| Pillar (workshop) | In AgentGuard |
|---|---|
| **Credentialing: Know Your Agent** | The agent is registered in the AP4M ParticipantRegistry (team `gizmogeeks`). On top, its **XRPL passport** names its EVM wallet (`evm:<address>` in the credential URI), so the merchant checks on the XRP Ledger that the voucher signer *is* a verified, unrevoked agent before serving. |
| **Permissioning: Funded ASL** | The channel cap is the hard limit (5 RLUSD of the 20 RLUSD budget). AgentGuard adds per-purchase limits: the **voucher gate** (`agentguard/ap4m.py: sign_voucher`) signs only purchases the checker approved (exact merchant + amount, single use), within the cap, while the passport is active and AgentGuard isn't frozen. |
| **Transacting: EIP-712 vouchers over x402** | 402 → the agent sends `PAYMENT-SIGNATURE` (base64 voucher) → the merchant verifies the signer, channel, price and cap, then **releases the data immediately** with a `PAYMENT-RESPONSE` header. No chain write on the hot path. |
| **Settling: RLUSD** | In the background: `redeemVoucher` (VoucherRedeemed), then the service's `settle` (ClaimPaid + SettlementRecorded, RLUSD to the payout wallet) and the **verifiable receipt** link, all shown in the dashboard feed. |

## "What a strong demo proves" checklist

| Workshop item | Where to see it |
|---|---|
| PSP-attested identities | AP4M portal: agent wallet registered; plus the XRPL passport check (merchant 403 when revoked) |
| Funded channel cap | Dashboard AP4M card (channel + cap) |
| **Over-cap attempt rejected** | Dashboard **⛔ Over-cap test**: a voucher 1 RLUSD above the cap is refused by AgentGuard's gate *and* reverted by the PaymentLedger (`eth_call`, no gas) |
| HTTP 402 requirements | `GET /news/sentiment` without payment → 402 with the AP4M requirements |
| Agent-signed voucher | Feed: `Voucher gate SIGNED …` (EIP-712, agent wallet) |
| Immediate resource release | Merchant serves the data as soon as the voucher checks out; redemption is queued |
| VoucherRedeemed claim | Feed: `VoucherRedeemed on the PaymentLedger … (claim 0x…)` + explorer link |
| ClaimPaid + SettlementRecorded | Feed: `Settled … RLUSD to the merchant` + settlement tx link |
| Receipt: channel + claim + payout | Feed: `Verifiable AP4M receipt` link |

**AgentGuard's addition (trust and control, 25%):** a rogue agent is stopped *before* it signs. Off-task purchases are refused by the
checker, the passport can be revoked on the XRP Ledger, and the kill switch closes the funded channel. Before closing, the merchant's
pending vouchers are redeemed and settled, so honest merchants still get paid.

## Status
- Code follows the official SDK (`ap4m-agent.js`): sign-in, requestChannel, listChannels, redeemVoucher, settle, closeChannel.
- **LIVE** with team `gizmogeeks`, registered agent wallet `0xc4959e…7b5d9`, channel `0x605d896f…` (5 RLUSD cap), payout = hackathon pool wallet.
- Live proof (full table in `PROOF.md`): [VoucherRedeemed](https://explorer.testnet.xrplevm.org/tx/0x273ac3cf9ebfca849b501ffa14d8425858eaf3d652bda12065d34e6ae0602c7f) · [settlement: ClaimPaid + SettlementRecorded](https://explorer.testnet.xrplevm.org/tx/0x8a2d4593693fa67460a3d739452dac371624ef38b9ecd96609e03d727f38c2ad) ·
  [verifiable receipt](https://hackathon.ap4m.build/public/evidence/claims/0x54aa6cf1778faf89a36160280a338f3ceea39f40111c80a147cf35fb1f07c7e8/0xd03af392f09eebd2d10684e2f9d614d0476f64c4640bf03cbfa29b1300a10e89.json) · over-cap voucher reverted by the PaymentLedger.
- Note for Mastercard: `/public/config` lists `https://faucet.testevm.ripple.com`, which doesn't resolve; we used https://faucet.xrplevm.org.
- `KILL_SWITCH_CLOSE_REAL_CHANNEL=false` simulates the close during rehearsals; set `true` for the final live demo.
- Mastercard's judging uses a **5-minute** live demo: use `DEMO_SCRIPT.md` and add the over-cap test and the receipt link.
