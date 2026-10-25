# Proof of real transactions (XRP Ledger testnet)

Every row links to the public explorer. `tef*` results (like `tefBAD_QUORUM`) are refused before they
reach a ledger, so they have no explorer page: the code shown is the ledger server's answer.
Mastercard AP4M rows say MOCK until the team's agent wallet is registered in the AP4M portal (see BLOCKERS.md).

## Co-signed agent wallet setup (scripts/setup_agent_wallet.py)

| Step | Result | Proof |
|---|---|---|
| Acme's approver key set as the issuer's regular key (SetRegularKey) | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/BBDAE046EE006A7A2C5B14840CE8C7EC6C6F69B5E0B0EFECF00609C48D781982) |
| Agent keeps a 10 XRP float, rest returned to the treasury | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/FCAF6A22E0E5D590990CE96EB1C071B0F1CBD52EF719400BC178BA24BCEF98AD) |
| Signer list on the agent: agent 1, AgentGuard 1, approver 2, quorum 2 (SignerListSet) | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/06B392A340C3C649961DD8327D0BCEFDA1FECBF6ACDA7A6FB22829408653A943) |
| Agent master key disabled (AccountSet asfDisableMaster) | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/7CDCD103A095A76AEDAC9192F4D525AE6BBF1D351618A0BDA3FD4260C5575CF5) |
| Agent account (signer list visible) | - | [explorer](https://testnet.xrpl.org/accounts/rMJefsPRgw7VW71PdTpbF9VL2ELM3jt2JE) |


## End-to-end run 2026-10-25 08:35 (AP4M MOCK)

| Step | Expected | Ledger said | Proof |
|---|---|---|---|
| Reset: passport active | active | active | - |
| FX Rates paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/E8F859DC9DD4A1B94BDE5BA98E99016AA3EFFA7955F10E687E8B3AA1ACDD752E) |
| Crypto Prices paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/266BBE4BBCCB474401778E997D97B8006A753969C29262C2318EAEC91E6C602D) |
| News paid via Mastercard AP4M (MOCK) | VoucherRedeemed | VoucherRedeemed | - |
| Attacker purchase refused by AgentGuard | BLOCK | BLOCK | - |
| Agent pays the attacker alone (no AgentGuard signature) | tefBAD_QUORUM | tefBAD_QUORUM | - |
| AgentGuard frozen | True | True | - |
| Acme revokes the passport (CredentialDelete, approver key) | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/402E78C68ABDA4B254EDF976E5E04895AE906C0CA868830370A5B0C67D3B5B97) |
| Payment to FX Rates with the old passport | tecBAD_CREDENTIALS | tecBAD_CREDENTIALS | [explorer](https://testnet.xrpl.org/transactions/5419F18D92959009BD8310C32A8114BB8ABD4E367932086722F41EF0CCD8D9E8) |
| Float swept back to Acme's treasury | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/43690768CE7F818E0B60EA4306CD2D6F0CE89360BCB2C45EFD841262793FBE82) |
| Payment to FX Rates with NO passport | tecNO_PERMISSION | tecNO_PERMISSION | [explorer](https://testnet.xrpl.org/transactions/749B6979ADA58450DE8DDAD81F59B38D51668B981C3A8E77880232C5DFACE787) |
| Acme re-issues the passport (one approval) | active | active | - |

## End-to-end run 2026-10-25 09:01 (AP4M MOCK)

| Step | Expected | Ledger said | Proof |
|---|---|---|---|
| Reset: passport active | active | active | - |
| FX Rates paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/E57937E06492C0CAA81DFC3B6EF07DA092FAD6C47318233A7B93995D11F7169F) |
| Crypto Prices paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/E5AC5FBE8C0D3A901462EE97F3ADB39988CF913F80A6D11990898D1059DA32F7) |
| News paid via Mastercard AP4M (MOCK) | VoucherRedeemed | VoucherRedeemed | - |
| Attacker purchase refused by AgentGuard | BLOCK | BLOCK | - |
| Agent pays the attacker alone (no AgentGuard signature) | tefBAD_QUORUM | tefBAD_QUORUM | - |
| AgentGuard frozen | True | True | - |
| Acme revokes the passport (CredentialDelete, approver key) | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/92444E55F59775E3CEB7C820DF627C595061B94D339E080F5D49F5B9B7B2AEE2) |
| Payment to FX Rates with the old passport | tecBAD_CREDENTIALS | tecBAD_CREDENTIALS | [explorer](https://testnet.xrpl.org/transactions/C335933DF96587EFE586779733585144FFC8870D56A258F5556DB33E38DBEC92) |
| Float swept back to Acme's treasury | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/3E6558D8428FA89EEF79B0CD06B540EB6F7B965D8C397412C699765BC75C77FE) |
| Payment to FX Rates with NO passport | tecNO_PERMISSION | tecNO_PERMISSION | [explorer](https://testnet.xrpl.org/transactions/B0E5D685C85DF3109E97493FB53B70484AC378A045EA833E51CB4FB335ADB947) |
| Acme re-issues the passport (one approval) | active | active | - |

## End-to-end run 2026-10-25 09:18 (AP4M MOCK)

| Step | Expected | Ledger said | Proof |
|---|---|---|---|
| Reset: passport active | active | active | - |
| FX Rates paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/6C6A5DCE091A7063889C96E74656BF790B2C01354F46A076F685BC0C0170D998) |
| Crypto Prices paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/F9ECE413C4E52949298C7CD9B2E86883C64839A9404081B73554C55200582695) |
| News voucher redeemed on the AP4M PaymentLedger (MOCK) | VoucherRedeemed | VoucherRedeemed | - |
| RLUSD settled to the merchant payout wallet (MOCK) | settled | settled | - |
| Voucher above the channel cap (MOCK) | rejected | rejected | - |
| Attacker purchase refused by AgentGuard | BLOCK | BLOCK | - |
| Agent pays the attacker alone (no AgentGuard signature) | tefBAD_QUORUM | tefBAD_QUORUM | - |
| AgentGuard frozen | True | True | - |
| Acme revokes the passport (CredentialDelete, approver key) | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/BFFD83A86EC299138C4E21D0C0FE880BCF7C6F67ED354B43E7DB986A3C72926F) |
| Payment to FX Rates with the old passport | tecBAD_CREDENTIALS | tecBAD_CREDENTIALS | [explorer](https://testnet.xrpl.org/transactions/CACA756C3D44D7D3EF6E91C8E62DC91E8FF7B46615DDD7A32EC88BC251B8A29F) |
| Float swept back to Acme's treasury | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/9E58FA3E03C746AAAD05578CDD57810C2D25AEF6FEA4C3637A1A77F9CAEDE27C) |
| Payment to FX Rates with NO passport | tecNO_PERMISSION | tecNO_PERMISSION | [explorer](https://testnet.xrpl.org/transactions/785912A20ED8A70F193F7F8E89380136D6B2CEA161C90E29CD8EA32CE348E530) |
| Acme re-issues the passport (one approval) | active | active | - |

## End-to-end run 2026-10-25 09:37 (AP4M LIVE)

| Step | Expected | Ledger said | Proof |
|---|---|---|---|
| Reset: passport active | active | active | - |
| FX Rates paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/37666EC96DC2B83FCDAB5B878A564B6211217F0950562E3842B6EA6E5EBB5591) |
| Crypto Prices paid, co-signed by agent + AgentGuard | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/8E0284E46067E6A4896E8DFBEBBC043BA7C0E4B9D809734F85B967D69D05635D) |
| News voucher redeemed on the AP4M PaymentLedger (LIVE) | VoucherRedeemed | VoucherRedeemed | [explorer](https://explorer.testnet.xrplevm.org/tx/0x273ac3cf9ebfca849b501ffa14d8425858eaf3d652bda12065d34e6ae0602c7f) |
| RLUSD settled to the merchant payout wallet (LIVE) | settled | settled | [explorer](https://explorer.testnet.xrplevm.org/tx/0x8a2d4593693fa67460a3d739452dac371624ef38b9ecd96609e03d727f38c2ad) |
| AP4M verifiable receipt (channel + claim + payout) | receipt | receipt | [explorer](https://hackathon.ap4m.build/public/evidence/claims/0x54aa6cf1778faf89a36160280a338f3ceea39f40111c80a147cf35fb1f07c7e8/0xd03af392f09eebd2d10684e2f9d614d0476f64c4640bf03cbfa29b1300a10e89.json) |
| Voucher above the channel cap (LIVE) | rejected | rejected | - |
| Attacker purchase refused by AgentGuard | BLOCK | BLOCK | - |
| Agent pays the attacker alone (no AgentGuard signature) | tefBAD_QUORUM | tefBAD_QUORUM | - |
| AgentGuard frozen | True | True | - |
| Acme revokes the passport (CredentialDelete, approver key) | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/E9A061B02DA6769E9FCFBC0FDD15F4919F65A61E5C18FE08BFC9796296D7726E) |
| Payment to FX Rates with the old passport | tecBAD_CREDENTIALS | tecBAD_CREDENTIALS | [explorer](https://testnet.xrpl.org/transactions/6E6C3FA249085C274250E7883DBE90C86D083C10AEE5F812F1F6754CDAB58B5A) |
| Float swept back to Acme's treasury | tesSUCCESS | tesSUCCESS | [explorer](https://testnet.xrpl.org/transactions/59EF3C7BEB83520F59A529F9961D6E2691DF222F609DF7CCB0744A002CD84946) |
| Payment to FX Rates with NO passport | tecNO_PERMISSION | tecNO_PERMISSION | [explorer](https://testnet.xrpl.org/transactions/C58E6E8FF9D784899034FE7D14EF8A7D4E836FF1C138C009C61F9F39A4472EC1) |
| Acme re-issues the passport (one approval) | active | active | - |
