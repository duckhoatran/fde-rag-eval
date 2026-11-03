#!/usr/bin/env python3
"""Embed every chunk with Gemini and cache vectors in SQLite.

Cache key is sha1(text): re-running never pays twice for the same chunk.
Vectors are stored as float32 blobs (768 dims -> 3 KB per chunk).

Free-tier reality: the embeddings quota is per-minute, so this throttles and
adapts — on HTTP 429 it backs off and shrinks the batch instead of dying.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
DB_PATH = ROOT / CFG["paths"]["db"]
EMB = CFG["embedder"]
MAX_BATCH = int(EMB["batch"])
MIN_BATCH = 8
PAUSE = float(EMB.get("pause_seconds", 1.0))


def _post(url: str, payload: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def _call(texts: list[str], task: str, api_key: str) -> list[list[float]]:
    url = f"{EMB['endpoint']}/{EMB['model']}:batchEmbedContents"
    payload = {
        "requests": [
            {
                "model": f"models/{EMB['model']}",
                "content": {"parts": [{"text": t[:8000]}]},
                "taskType": task,
                "outputDimensionality": EMB["dim"],
            }
            for t in texts
        ]
    }
    data = _post(url, payload, api_key)
    return [e["values"] for e in data["embeddings"]]


def embed_batch(texts: list[str], task: str, api_key: str) -> list[list[float]]:
    attempt = 0
    while True:
        try:
            return _call(texts, task, api_key)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt >= 6:
                raise
            wait = min(60, 8 * (2 ** attempt))
            print(f"\n  [429/5xx] backing off {wait}s (attempt {attempt + 1})", file=sys.stderr)
            time.sleep(wait)
            attempt += 1


def main() -> int:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set (source ~/.hermes/.env)", file=sys.stderr)
        return 1
    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run ingest.py first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    cached = {row[0]: row[1] for row in conn.execute("SELECT chunk_id, sha1 FROM emb").fetchall()}
    todo = []
    for chunk_id, text in conn.execute("SELECT chunk_id, text FROM chunks").fetchall():
        digest = hashlib.sha1(text.encode()).hexdigest()
        if cached.get(chunk_id) != digest:
            todo.append((chunk_id, text, digest))

    print(f"{len(cached)} cached · {len(todo)} to embed · dim={EMB['dim']}")
    if not todo:
        return 0

    batch = MAX_BATCH
    done = 0
    chars = 0
    t0 = time.time()
    while done < len(todo):
        chunk = todo[done : done + batch]
        try:
            vectors = embed_batch([c[1] for c in chunk], EMB["task_document"], api_key)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and batch > MIN_BATCH:
                batch = max(MIN_BATCH, batch // 2)
                print(f"\n  [429] shrinking batch to {batch}", file=sys.stderr)
                time.sleep(20)
                continue
            raise
        rows = []
        for (chunk_id, text, digest), vec in zip(chunk, vectors):
            arr = np.asarray(vec, dtype=np.float32)
            rows.append((chunk_id, digest, int(arr.size), arr.tobytes()))
            chars += len(text)
        conn.executemany("INSERT OR REPLACE INTO emb VALUES (?,?,?,?)", rows)
        conn.commit()
        done += len(chunk)
        rate = done / max(1e-6, time.time() - t0)
        print(f"  {done}/{len(todo)} chunks · {rate:.1f} chunk/s", end="\r", flush=True)
        time.sleep(PAUSE)

    print(f"\nembedded {done} chunks · ~{chars // 4:,} input tokens (chars/4) · {time.time() - t0:.0f}s")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
