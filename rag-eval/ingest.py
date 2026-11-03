#!/usr/bin/env python3
"""Corpus text -> sections -> chunks -> SQLite (+ FTS5 index for BM25).

Two chunking strategies (per-document, declared in manifest.json):
  * "section" — split on legal/technical headings first (Article / Chapter /
    Annex / numbered sections), then split oversized sections on paragraph
    boundaries with overlap. Section-aware chunking is what makes recall@5
    meaningful: a chunk maps to "Article 33", not to an arbitrary window.
  * "window"  — fixed-size paragraph windows. Used for PDFs whose text has no
    reliable heading structure (NIST AI RMF, Basel III), and as automatic
    fallback when "section" detects almost nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
MANIFEST = json.loads((ROOT / CFG["corpus"]["manifest"]).read_text())["documents"]
CORPUS_DIR = ROOT / CFG["corpus"]["dir"]
DB_PATH = ROOT / CFG["paths"]["db"]
MAX = CFG["chunking"]["max_chars"]
OVERLAP = CFG["chunking"]["overlap_chars"]
MIN = CFG["chunking"]["min_chars"]
DEFAULT_STRATEGY = CFG["chunking"]["strategy"]

HEADING_PATTERNS = [
    re.compile(r"^(Article\s+\d+[a-z]?)\b", re.I),
    re.compile(r"^((?:CHAPTER|TITLE|SECTION|ANNEX)\s+[IVXLCDM\d]+)\b", re.I),
    re.compile(r"^(\d+(?:\.\d+){1,3})\.?\s+\S"),          # 4.2  Authentication
    re.compile(r"^([A-Z][A-Z0-9 \-/&,'()]{5,70})$"),      # ALL CAPS heading
]


ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8,
         "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15}


def _num(suffix: str) -> str:
    """'III' -> '3' (roman), '3' -> '3'."""
    return str(ROMAN.get(suffix.lower(), suffix.lower()))


def _slug_one(h: str) -> tuple[str | None, int]:
    """(slug, specificity) for a single heading fragment."""
    m = re.match(r"article\s+(\d+[a-z]?)", h, re.I)
    if m:
        return f"art{m.group(1).lower()}", 4
    m = re.match(r"annex\s+([ivxlcdm\d]+)", h, re.I)
    if m:
        return f"annex{_num(m.group(1))}", 3
    m = re.match(r"(chapter|title|section)\s+([ivxlcdm\d]+)", h, re.I)
    if m:
        kind = {"chapter": "ch", "title": "tit", "section": "sec"}[m.group(1).lower()]
        return f"{kind}{_num(m.group(2))}", 2
    m = re.match(r"(\d+(?:\.\d+){1,3})", h)
    if m:
        return "sec" + m.group(1).replace(".", "-"), 2
    generic = re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")[:40]
    return (generic or None), 1


def slugify(heading: str) -> str:
    """Slug the most specific fragment — merged headings look like
    'CHAPTER II | Article 10', where the article is what we want to cite."""
    best: tuple[str, int] = ("top", 0)
    for part in heading.split("|"):
        slug, rank = _slug_one(part.strip())
        if slug and rank > best[1]:
            best = (slug, rank)
    return best[0]


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(heading, body)] — first item is the document preamble."""
    sections: list[tuple[str, str]] = []
    heading = "preamble"
    buf: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        is_heading = False
        if 0 < len(stripped) <= 80:
            for pat in HEADING_PATTERNS:
                if pat.match(stripped):
                    is_heading = True
                    break
        if is_heading:
            body = "\n".join(buf).strip()
            if body:
                sections.append((heading, body))
                heading, buf = stripped, []
            else:
                # consecutive headings (e.g. "ANNEX I" then its title on the next
                # line): merge the labels so the annex keeps its identity.
                heading = stripped if heading in ("", "preamble") else f"{heading} | {stripped}"
        else:
            buf.append(line)

    body = "\n".join(buf).strip()
    if body:
        sections.append((heading, body))
    return sections


def split_long(body: str) -> list[str]:
    """Split an oversized block on paragraph boundaries, with overlap."""
    if len(body) <= MAX:
        return [body]
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in paras:
        if cur_len + len(p) + 1 > MAX and cur:
            out.append("\n".join(cur))
            tail: list[str] = []
            tail_len = 0
            for prev in reversed(cur):
                if tail_len + len(prev) > OVERLAP:
                    break
                tail.insert(0, prev)
                tail_len += len(prev)
            cur, cur_len = tail, tail_len
        cur.append(p)
        cur_len += len(p) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def window_items(text: str, doc_id: str) -> list[tuple[str, str, str]]:
    """Fixed windows -> [(suffix, heading, body)]."""
    items: list[tuple[str, str, str]] = []
    for idx, body in enumerate(split_long(text), start=1):
        first = next((ln.strip() for ln in body.split("\n") if ln.strip()), "")
        items.append((f"w{idx:03d}", f"part {idx:03d}: {first[:60]}", body))
    return items


def build() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE docs (
            doc_id TEXT PRIMARY KEY, title TEXT, license TEXT, source TEXT,
            chars INTEGER, sha256 TEXT, sections INTEGER, chunks INTEGER,
            strategy TEXT
        );
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, doc_id TEXT, section TEXT, heading TEXT,
            seq INTEGER, n_chars INTEGER, text TEXT
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, text);
        CREATE TABLE emb (chunk_id TEXT PRIMARY KEY, sha1 TEXT, dim INTEGER, vec BLOB);
        """
    )

    total_chunks = 0
    print(f"{'doc':16}{'strategy':>10}{'sections':>9}{'chunks':>8}{'chars':>10}")
    for entry in MANIFEST:
        doc_id = entry["doc_id"]
        path = CORPUS_DIR / f"{doc_id}.md"
        if not path.exists():
            print(f"{doc_id:16}{'MISSING':>10}")
            continue
        text = path.read_text(encoding="utf-8")
        strategy = entry.get("chunk", DEFAULT_STRATEGY)

        if strategy == "section":
            sections = split_sections(text)
            if len(sections) < 10:
                print(
                    f"  [warn] {doc_id}: section split found only {len(sections)} sections "
                    f"-> falling back to window chunking"
                )
                strategy = "window"
        else:
            sections = []

        if strategy == "window":
            items = window_items(text, doc_id)
        else:
            items = [(slugify(h), h, b) for h, b in sections]

        rows: list[tuple] = []
        for idx, (suffix, heading, body) in enumerate(items, start=1):
            section_id = f"{doc_id}#{suffix}"
            parts = split_long(body) if strategy == "section" else [body]
            for part_no, part in enumerate(parts, start=1):
                suffix2 = "" if len(parts) == 1 else f"-p{part_no}"
                chunk_id = f"{section_id}{suffix2}"
                if any(r[0] == chunk_id for r in rows):
                    chunk_id = f"{chunk_id}-{idx}-{part_no}"
                rows.append((chunk_id, doc_id, section_id, heading, part_no, len(part), part))

        conn.executemany("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?)", rows)
        conn.executemany(
            "INSERT INTO chunks_fts (chunk_id, text) VALUES (?,?)",
            [(r[0], f"{r[3]}\n{r[6]}") for r in rows],  # heading is indexed too:
            # "ANNEX III" must be findable, and it only lives in the heading.
        )
        conn.execute(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?)",
            (
                doc_id, entry["title"], entry["license"], entry["source"], len(text),
                hashlib.sha256(text.encode()).hexdigest()[:16], len(items), len(rows), strategy,
            ),
        )
        total_chunks += len(rows)
        print(f"{doc_id:16}{strategy:>10}{len(items):>9}{len(rows):>8}{len(text):>10,}")

    conn.commit()
    n_docs = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    avg = conn.execute("SELECT AVG(n_chars) FROM chunks").fetchone()[0] or 0
    print(f"\n{n_docs} docs · {total_chunks} chunks · avg {avg:.0f} chars -> {DB_PATH.relative_to(ROOT)}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(build())
