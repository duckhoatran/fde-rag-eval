#!/usr/bin/env python3
"""Retrieval: BM25 (SQLite FTS5) · dense (Gemini + numpy cosine) · hybrid (RRF).

Three pipelines exist so Phase 1 can *measure* which one wins on legal text
instead of asserting it. Dense retrieval over a few thousand chunks does not
need FAISS — a normalized matrix dot product is enough and has no extra deps.

CLI (sanity check by hand):
    python3 retrieve.py "What does Article 33 GDPR require?"
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
DB_PATH = ROOT / CFG["paths"]["db"]
TOP_K = int(CFG["retrieval"]["top_k"])
RRF_K = int(CFG["retrieval"]["rrf_k"])
EMB = CFG["embedder"]

STOP = {
    "the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are", "be",
    "what", "which", "does", "do", "how", "must", "shall", "with", "on", "by",
    "under", "that", "this", "it", "its", "as", "at", "from", "any",
}


@dataclass
class Hit:
    chunk_id: str
    section: str
    heading: str
    text: str
    score: float


_conn: sqlite3.Connection | None = None
_matrix: np.ndarray | None = None
_ids: list[str] | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
    return _conn


def _fts_query(query: str) -> str:
    tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", query.lower()) if t not in STOP and len(t) > 1]
    if not tokens:
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower()) or ["x"]
    return " OR ".join(f'"{t}"' for t in tokens[:32])


def bm25(query: str, k: int = TOP_K) -> list[Hit]:
    rows = _db().execute(
        """
        SELECT c.chunk_id, c.section, c.heading, c.text, bm25(chunks_fts) AS s
        FROM chunks_fts JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
        WHERE chunks_fts MATCH ? ORDER BY s LIMIT ?
        """,
        (_fts_query(query), k),
    ).fetchall()
    return [Hit(r[0], r[1], r[2], r[3], float(r[4])) for r in rows]


def embed_query(query: str) -> np.ndarray:
    """Same provider as the document side — see embedding.py."""
    from embedding import embed_query as _embed_query

    return _embed_query(query)


def _load_matrix() -> tuple[np.ndarray, list[str]]:
    global _matrix, _ids
    if _matrix is None:
        rows = _db().execute(
            """
            SELECT e.chunk_id, e.vec FROM emb e
            JOIN chunks c ON c.chunk_id = e.chunk_id
            ORDER BY c.doc_id, c.section, c.seq
            """
        ).fetchall()
        ids = [r[0] for r in rows]
        mat = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _matrix, _ids = mat / norms, ids
    return _matrix, _ids  # type: ignore[return-value]


def dense(query: str, k: int = TOP_K) -> list[Hit]:
    mat, ids = _load_matrix()
    qv = embed_query(query)
    qv = qv / (np.linalg.norm(qv) or 1.0)
    scores = mat @ qv
    order = np.argsort(-scores)[:k]
    wanted = [(ids[i], float(scores[i])) for i in order]
    placeholders = ",".join("?" * len(wanted))
    meta = {
        r[0]: r[1:]
        for r in _db()
        .execute(
            f"SELECT chunk_id, section, heading, text FROM chunks WHERE chunk_id IN ({placeholders})",
            [c for c, _ in wanted],
        )
        .fetchall()
    }
    return [Hit(cid, meta[cid][0], meta[cid][1], meta[cid][2], sc) for cid, sc in wanted if cid in meta]


def hybrid(query: str, k: int = TOP_K) -> list[Hit]:
    """Reciprocal Rank Fusion of BM25 and dense rankings."""
    pools = [bm25(query, k), dense(query, k)]
    fused: dict[str, float] = {}
    hits: dict[str, Hit] = {}
    for pool in pools:
        for rank, hit in enumerate(pool, start=1):
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            hits.setdefault(hit.chunk_id, hit)
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
    return [
        Hit(hits[cid].chunk_id, hits[cid].section, hits[cid].heading, hits[cid].text, score)
        for cid, score in ranked
    ]


PIPELINES = {"bm25": bm25, "dense": dense, "hybrid": hybrid}


def search(pipeline: str, query: str, k: int = TOP_K) -> list[Hit]:
    return PIPELINES[pipeline](query, k)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('usage: python3 retrieve.py "question"')
    q = " ".join(sys.argv[1:])
    for name in PIPELINES:
        print(f"\n=== {name} ===")
        for i, h in enumerate(search(name, q), start=1):
            print(f"{i}. [{h.section}] {h.heading[:70]}  ({h.text[:90].replace(chr(10), ' ')}...)")
