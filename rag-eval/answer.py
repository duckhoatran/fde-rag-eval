#!/usr/bin/env python3
"""Answer step: retrieved chunks -> grounded answer with mandatory citations.

Guardrails applied from the first commit (they become the W47 measurement):
  * answer only from context
  * every claim must cite [chunk_id]
  * if context is insufficient -> say "insufficient evidence", never guess

CLI:  python3 answer.py "Within how many hours must a breach be notified?"
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
ANS = CFG["answer"]

SYSTEM = (
    "You are a compliance research assistant. Answer ONLY from the provided context. "
    "Every factual sentence must end with a citation to the chunk it came from, in the form [chunk_id]. "
    "If the context does not contain the answer, reply exactly: "
    "'insufficient evidence' and list what is missing. Never use outside knowledge."
)


def build_context(hits, max_chars: int = 14000) -> str:
    parts, used = [], 0
    for h in hits:
        block = f"[{h.chunk_id}] ({h.heading})\n{h.text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def ask(question: str, hits) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY not set (source ~/.hermes/.env)")
    payload = {
        "model": ANS["model"],
        "temperature": ANS["temperature"],
        "max_tokens": ANS["max_tokens"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{build_context(hits)}",
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

    if len(sys.argv) < 2:
        raise SystemExit('usage: python3 answer.py "question"')
    q = " ".join(sys.argv[1:])
    hits = search("hybrid", q)
    result = ask(q, hits)
    print(result["answer"])
    print(f"\n--- tokens in/out: {result['tokens_in']}/{result['tokens_out']}")
    print(f"--- citations: {sorted(set(result['citations']))}")
