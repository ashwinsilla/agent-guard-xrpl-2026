"""Check SUBMISSION.md fields against the form's character limits.

    .venv/bin/python scripts/check_submission.py
"""
import os
import re

LIMITS = {"short": 200, "description": 5000, "technical": 1000}
text = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SUBMISSION.md")).read()
ok = True
for field, limit in LIMITS.items():
    body = re.search(rf"<!-- {field} -->\n(.*?)\n<!-- /{field} -->", text, re.S).group(1).strip()
    fits = len(body) <= limit
    ok &= fits
    print(f"{'OK  ' if fits else 'TOO LONG'} {field}: {len(body)} / {limit} characters")
print("All fields fit." if ok else "Shorten the fields marked TOO LONG.")
