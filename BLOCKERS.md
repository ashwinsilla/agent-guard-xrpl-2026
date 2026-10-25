# Blockers

| Blocker | Effect today | What unblocks it |
|---|---|---|
| ~~AP4M sign-in~~ **resolved**: team name `gizmogeeks` + registered agent wallet; the Mastercard lane is LIVE | - | Before the final demo, decide on `KILL_SWITCH_CLOSE_REAL_CHANNEL=true` (really closes the channel) |
| No AWS credentials / `BEDROCK_MODEL_ID` on this machine | Checker uses hard rules only, news risk score uses keywords, agent runs the OFFLINE planner (all labelled) | Add AWS credentials (profile or env vars) and `BEDROCK_MODEL_ID` to `.env` |
| `XRPL_RPC_URL` is the public testnet server | Works; preflight warns; dashboard badge says "Public XRPL RPC" | Set `XRPL_RPC_URL` to the team's Quicknode XRPL testnet endpoint; point a Quicknode Stream/webhook at `POST /webhooks/quicknode?secret=...` (expose with ngrok) |
| AgentCore Runtime deploy | Agent runs locally | Needs AWS credentials; follow the AgentCore Runtime docs to wrap `agents/treasury_analyst.run` |
| No Ledger device on site | Software approver key in the device's slot (weight 2) | Swap the approver key for a device/Speculos signer; nothing else changes |
