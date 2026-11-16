#!/usr/bin/env python3
"""Capture the real demo outputs into JSON so the video can't show invented text."""
import json, subprocess, os
from pathlib import Path

ROOT = Path.home() / "fde-lab/rag-eval"
PY = str(Path.home() / ".venvs/fde/bin/python")
OUT = Path("/tmp/demo/capture.json")

env = dict(os.environ)
for line in (Path.home() / ".hermes/.env").read_text().splitlines():
    if line.startswith("DEEPSEEK_API_KEY="):
        env["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip()

COMMANDS = [
    ("tree", "ls -1 && echo && wc -l evals/questions.jsonl evals/injections.jsonl"),
    ("eval", f"{PY} run_eval.py"),
    ("guarded", f"{PY} answer.py 'What is the maximum administrative fine under the UK Data Protection Act 2018?'"),
    ("naive", f"{PY} answer.py --naive 'What is the maximum administrative fine under the UK Data Protection Act 2018?'"),
    ("metrics", "sed -n '16,26p' reports/w47-guardrails.md"),
    ("git", "git -C .. log --oneline -3"),
]

out = {}
for key, cmd in COMMANDS:
    r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=300, env=env)
    text = (r.stdout or "").strip()
    if r.returncode != 0:
        text += "\n" + (r.stderr or "").strip()
    out[key] = {"cmd": cmd.replace(PY, "python3"), "out": text, "rc": r.returncode}
    print(f"=== {key} (rc={r.returncode}) ===\n{text[:400]}\n")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
print("saved", OUT, OUT.stat().st_size, "bytes")
