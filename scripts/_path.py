"""Lets scripts import the `agentguard` package when run as `python scripts/x.py`."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
