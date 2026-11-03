#!/usr/bin/env python3
"""Embedding providers behind one interface.

  fastembed  — local ONNX (BAAI/bge-small-en-v1.5, 384d): offline, no quota,
               deterministic. Default for this repo so the eval is reproducible
               and W46 can re-embed after every chunking experiment for free.
  gemini     — API (gemini-embedding-001, 768d): better quality, but free tier
               hits a daily quota, which makes repeated experiments painful.

Both expose the same two calls: embed_documents(texts) and embed_query(text).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
EMB = CFG["embedder"]
PROVIDER = EMB["provider"]
DIM = int(EMB["dim"])

_local_model = None


def _local():
    global _local_model
    if _local_model is None:
        from fastembed import TextEmbedding

        _local_model = TextEmbedding(model_name=EMB["model"])
    return _local_model


def _gemini(texts: list[str], task: str) -> list[list[float]]:
    import json
    import os
    import time
    import urllib.error
    import urllib.request

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("GOOGLE_API_KEY not set")
    url = f"{EMB['endpoint']}/{EMB['model']}:batchEmbedContents"
    payload = {
        "requests": [
            {
                "model": f"models/{EMB['model']}",
                "content": {"parts": [{"text": t[:8000]}]},
                "taskType": task,
                "outputDimensionality": DIM,
            }
            for t in texts
        ]
    }
    attempt = 0
    while True:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            return [e["values"] for e in data["embeddings"]]
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt >= 20:
                raise
            wait = min(60, 8 * (attempt + 1))
            print(f"  [gemini {exc.code}] backoff {wait}s", flush=True)
            time.sleep(wait)
            attempt += 1


def embed_documents(texts: list[str]) -> list[list[float]]:
    if PROVIDER == "fastembed":
        return [v.tolist() for v in _local().embed(texts)]
    return _gemini(texts, EMB["task_document"])


def embed_query(text: str) -> np.ndarray:
    if PROVIDER == "fastembed":
        vec = next(iter(_local().query_embed([text])))
    else:
        vec = np.asarray(_gemini([text], EMB["task_query"])[0])
    return np.asarray(vec, dtype=np.float32)


if __name__ == "__main__":
    docs = embed_documents(["Article 33 requires notification within 72 hours."])
    q = embed_query("breach notification deadline")
    print(f"provider={PROVIDER} model={EMB['model']} dim={len(docs[0])} query_dim={q.shape[0]}")
