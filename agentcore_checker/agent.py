"""AgentGuard's CHECKER AI, deployed on Amazon Bedrock AgentCore Runtime.

AgentGuard (on the laptop) runs its hard rules first, then calls this runtime with ONLY structured
facts about a purchase: task, merchant, category, price, usual price, approved-list flag, past prices.
Never the merchant's text or the agent's own explanation, so prompt injection has nothing to ride on.
The runtime answers {"decision": APPROVE|HOLD|BLOCK, "reason": ..., "task_fit_score": 0-100}.

No wallet keys or secrets live here: the runtime only judges. Signing stays with AgentGuard.
Deploy:  see agentcore_checker/README.md
"""
import json
import os
import re

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

app = BedrockAgentCoreApp()
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
SYSTEM = ("You are AgentGuard's strict corporate purchase checker for an AI treasury agent. You only ever "
          "receive structured facts from AgentGuard's own records. Decide APPROVE, HOLD (unsure: a human decides) "
          'or BLOCK. Reply ONLY with JSON: {"decision": "...", "reason": "<one sentence for a compliance '
          'officer>", "task_fit_score": <0-100>}')


@app.entrypoint
def invoke(payload: dict) -> dict:
    """payload = {"facts": {...structured purchase facts...}, "rules_verdict": "APPROVE|HOLD|BLOCK"}."""
    facts = payload.get("facts", {})
    agent = Agent(model=BedrockModel(model_id=MODEL_ID), system_prompt=SYSTEM, callback_handler=None)
    answer = str(agent(f"Purchase facts: {json.dumps(facts)}\nThe hard rules said: {payload.get('rules_verdict')}.\n"
                       "Does this purchase fit the agent's task?"))
    match = re.search(r"\{.*\}", answer, re.S)
    try:
        result = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        result = {}
    if result.get("decision") not in ("APPROVE", "HOLD", "BLOCK"):
        result = {"decision": "HOLD", "reason": "checker could not parse its own answer: a human decides",
                  "task_fit_score": 50}
    return {**result, "model": MODEL_ID, "runtime": "Amazon Bedrock AgentCore"}


if __name__ == "__main__":
    app.run()
