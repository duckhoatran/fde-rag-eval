#!/usr/bin/env python3
"""Answer step: retrieved chunks -> grounded answer with mandatory citations.

Two prompt arms live in guardrails.py — "guarded" (W47 policy: citations,
refusal, instruction hierarchy) and "naive" (the W45/W46 behaviour, used as the
before-number in reports/w47-guardrails.md).

CLI:  python3 answer.py "Within how many hours must a breach be notified?"
      python3 answer.py --naive "Within how many hours must a breach be notified?"
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

from guardrails import SYSTEMS

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
ANS = CFG["answer"]


def build_context(hits, max_chars: int = 14000, extra: str | None = None) -> str:
    parts, used = [], 0
    if extra:  # W47 injection arm: a "document" carrying hostile instructions
        parts.append(extra)
        used += len(extra)
    for h in hits:
        block = f"[{h.chunk_id}] ({h.heading})\n{h.text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def ask(question: str, hits, mode: str = "guarded", poison: str | None = None) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY not set (source ~/.hermes/.env)")
    payload = {
        "model": ANS["model"],
        "temperature": ANS["temperature"],
        "max_tokens": ANS["max_tokens"],
        "messages": [
            {"role": "system", "content": SYSTEMS[mode]},
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{build_context(hits, extra=poison)}",
            },
        ],
    }
    req = urllib.request.Request(
        f"{ANS['base_url']}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    choice = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "answer": choice,
        "citations": __import__("re").findall(r"\[([a-z0-9_]+#[^\]]+)\]", choice),
        "tokens_in": usage.get("prompt_tokens"),
        "tokens_out": usage.get("completion_tokens"),
    }


if __name__ == "__main__":
    from retrieve import search

    args = sys.argv[1:]
    mode = "guarded"
    if args and args[0] == "--naive":
        mode = "naive"
        args = args[1:]
    if not args:
        raise SystemExit('usage: python3 answer.py "question"')
    q = " ".join(args)
    hits = search("hybrid", q)
    result = ask(q, hits, mode=mode)
    print(result["answer"])
    print(f"\n--- tokens in/out: {result['tokens_in']}/{result['tokens_out']}")
    print(f"--- citations: {sorted(set(result['citations']))}")
