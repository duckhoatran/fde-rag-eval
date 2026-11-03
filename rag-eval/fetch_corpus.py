#!/usr/bin/env python3
"""Download the public corpus and convert it to plain text.

Two source types:
  * EU legal acts  -> Publications Office content negotiation (XHTML), no browser needed
  * NIST / BIS     -> PDF, text extracted with PyMuPDF

Run:  python3 fetch_corpus.py [--doc ai_act ...]
Exit code 0 even if some docs are skipped (existing .md is kept), so `make eval`
still works offline — the converted corpus text is committed to the repo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
MANIFEST = json.loads((ROOT / CFG["corpus"]["manifest"]).read_text())
CORPUS_DIR = ROOT / CFG["corpus"]["dir"]
PDF_DIR = ROOT / CFG["corpus"]["pdf_dir"]

UA = "Mozilla/5.0 (X11; Linux x86_64) fde-rag-eval/0.1"
CELEX = {
    "ai_act": "32024R1689",
    "gdpr": "32016R0679",
    "psd2": "32015L2366",
    "eba_rts_sca": "32018R0389",
}


class _Text(HTMLParser):
    """Minimal HTML -> text: block tags become newlines, script/style dropped."""

    SKIP = {"script", "style", "head", "meta"}
    BLOCK = {
        "p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6",
        "article", "section", "title", "td", "th",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)

    def text(self) -> str:
        return "".join(self.out)


def clean(text: str) -> str:
    text = text.replace("\r", "\n")
    # EUR-Lex uses NBSP between "Article" and the number, which breaks tokenisers
    for weird in ("\u00a0", "\u2009", "\u202f", "\u2007"):
        text = text.replace(weird, " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def fetch_bytes(url: str, headers: dict[str, str], timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_eu(doc_id: str, source: str) -> str:
    celex = CELEX[doc_id]
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    # EUR-Lex's own HTML endpoint serves a JS challenge (HTTP 202); the
    # Publications Office content-negotiation endpoint returns real XHTML.
    raw = fetch_bytes(url, {"Accept": "application/xhtml+xml", "Accept-Language": "eng"})
    parser = _Text()
    parser.feed(raw.decode("utf-8", errors="ignore"))
    return clean(parser.text())


def fetch_pdf(url: str, doc_id: str) -> str:
    import pymupdf  # imported lazily so fetch_eu works without it

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists() or pdf_path.stat().st_size < 10_000:
        pdf_path.write_bytes(fetch_bytes(url, {"Accept": "application/pdf"}))
    doc = pymupdf.open(pdf_path)
    return clean("\n".join(page.get_text() for page in doc))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", action="append", help="only fetch these doc_ids")
    args = ap.parse_args()

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for entry in MANIFEST["documents"]:
        doc_id = entry["doc_id"]
        if args.doc and doc_id not in args.doc:
            continue
        out_path = CORPUS_DIR / f"{doc_id}.md"
        try:
            text = fetch_eu(doc_id, entry["source"]) if entry["type"] == "html" else fetch_pdf(entry["source"], doc_id)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            keep = "" if not out_path.exists() else f" — keeping existing {out_path.stat().st_size:,} chars"
            print(f"[skip] {doc_id}: {exc}{keep}", file=sys.stderr)
            continue
        if len(text) < 5_000:
            print(f"[skip] {doc_id}: extracted only {len(text)} chars (suspicious)", file=sys.stderr)
            continue
        out_path.write_text(text, encoding="utf-8")
        print(f"[ok]   {doc_id:14} {len(text):>9,} chars -> {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
