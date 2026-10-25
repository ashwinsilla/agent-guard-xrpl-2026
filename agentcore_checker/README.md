# AgentGuard checker on Amazon Bedrock AgentCore Runtime

`agent.py` is AgentGuard's checker AI packaged as an AgentCore Runtime app (Strands Agents + Amazon Bedrock).
It receives only structured purchase facts and returns `{decision, reason, task_fit_score}`. No wallet keys live here.

Deploy (from this folder, AWS credentials in the project's `.env`):
```bash
../.venv/bin/python ../scripts/agentcore_cli.py configure -e agent.py -n agentguard_checker -dt direct_code_deploy -r us-east-1 -rf requirements.txt -dm -ni
../.venv/bin/python ../scripts/agentcore_cli.py deploy --env BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
../.venv/bin/python ../scripts/agentcore_cli.py invoke '{"facts": {"merchant": "FX Rates Co.", "category": "fx_rates", "price": "0.05", "currency": "XRP", "usual_price": "0.05", "on_approved_list": true, "task": "daily FX and crypto risk report"}, "rules_verdict": "APPROVE"}'
```

**Status at submission:** configured and packaged successfully (execution role created), but the deploy stops at
`s3:CreateBucket` because our new AWS account's organization policy explicitly denies S3 bucket and ECR repository creation.
The same checker logic runs locally on Bedrock today (`agentguard/checker.py`).
