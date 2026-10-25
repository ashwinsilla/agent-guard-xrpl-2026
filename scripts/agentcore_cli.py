"""Run the AgentCore CLI with the AWS credentials from .env (never printed).

    .venv/bin/python scripts/agentcore_cli.py <agentcore arguments...>   (run from agentcore_checker/)
"""
import os
import subprocess
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
os.environ["AGENTCORE_SUPPRESS_RECOMMENDATION"] = "1"
sys.exit(subprocess.call([os.path.join(ROOT, ".venv", "bin", "agentcore"), *sys.argv[1:]]))
