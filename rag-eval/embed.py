#!/usr/bin/env python3
"""Embed every chunk and cache vectors in SQLite.

Cache key is sha1(text) — re-running never recomputes the same chunk.
Vectors are float32 blobs. Provider is swappable via config.yaml
(fastembed = local ONNX by default; gemini = API).

Run with the venv that has fastembed:
    ~/.venvs/fde/bin/python embed.py
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import yaml

from embedding import DIM, EMB, PROVIDER, embed_documents

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
DB_PATH = ROOT / CFG["paths"]["db"]
BATCH = int(EMB["batch"])
PAUSE = float(EMB.get("pause_seconds", 0))


def main() -> int:
    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run ingest.py first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    dims = {row[0] for row in conn.execute("SELECT DISTINCT dim FROM emb").fetchall()}
    if dims and dims != {DIM}:
        print(f"embedder changed (stored dims {sorted(dims)} != {DIM}) — clearing cache")
        conn.execute("DELETE FROM emb")
        conn.commit()

    cached = {row[0]: row[1] for row in conn.execute("SELECT chunk_id, sha1 FROM emb").fetchall()}
    todo = []
    for chunk_id, text in conn.execute("SELECT chunk_id, text FROM chunks").fetchall():
        digest = hashlib.sha1(text.encode()).hexdigest()
        if cached.get(chunk_id) != digest:
            todo.append((chunk_id, text, digest))

    print(f"provider={PROVIDER} model={EMB['model']} dim={DIM}")
    print(f"{len(cached)} cached · {len(todo)} to embed")
    if not todo:
        return 0

    done = 0
    chars = 0
    t0 = time.time()
    while done < len(todo):
        chunk = todo[done : done + BATCH]
        vectors = embed_documents([c[1] for c in chunk])
        rows = []
        for (chunk_id, text, digest), vec in zip(chunk, vectors):
            arr = np.asarray(vec, dtype=np.float32)
            rows.append((chunk_id, digest, int(arr.size), arr.tobytes()))
            chars += len(text)
        conn.executemany("INSERT OR REPLACE INTO emb VALUES (?,?,?,?)", rows)
        conn.commit()
        done += len(chunk)
        rate = done / max(1e-6, time.time() - t0)
        print(f"  {done}/{len(todo)} chunks · {rate:.0f} chunk/s", end="\r", flush=True)
        if PAUSE:
            time.sleep(PAUSE)

    print(f"\nembedded {done} chunks · ~{chars // 4:,} input tokens · {time.time() - t0:.0f}s")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
