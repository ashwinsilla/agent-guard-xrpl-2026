# Blockers

| Blocker | Effect today | What unblocks it |
|---|---|---|
| ~~AP4M sign-in~~ **resolved**: team name `gizmogeeks` + registered agent wallet; the Mastercard lane is LIVE | - | Before the final demo, decide on `KILL_SWITCH_CLOSE_REAL_CHANNEL=true` (really closes the channel) |
| ~~No AWS credentials~~ **resolved**: Bedrock online (Nova Pro; auto-fallback list in `agentguard/llm.py`) | - | Optional: submit the Anthropic use-case form in the Bedrock console to use Claude Haiku 4.5 |
| ~~Public XRPL RPC~~ **resolved**: Quicknode RPC + WebSocket in use | - | Optional: connect a Quicknode Stream to `POST /webhooks/quicknode` (needs a public tunnel) |
| AgentCore Runtime deploy | Checker packaged for AgentCore (`agentcore_checker/`), execution role created; deploy blocked | Our AWS account's organization policy explicitly denies `s3:CreateBucket` and ECR, which both AgentCore deploy modes need. Use an account without that restriction and run the 2 commands in `agentcore_checker/README.md` |
| No Ledger device on site | Software approver key in the device's slot (weight 2) | Swap the approver key for a device/Speculos signer; nothing else changes |
