#!/usr/bin/env python3
"""Eval harness: questions.jsonl -> recall@5 · p50/p95 latency · cost/1000 questions.

recall@5 = share of answerable questions whose gold section appears in the
top-5 retrieved sections. Gold is a section id (e.g. gdpr#art33), so a chunk
scores a hit if its section matches — chunk-level ids are free to change.

    python3 run_eval.py                 # retrieval only (cheap, no LLM calls)
    python3 run_eval.py --answer 5      # + answer step on 5 questions (token cost)
    python3 run_eval.py --report        # rewrite reports/baseline.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
DB_PATH = ROOT / CFG["paths"]["db"]
QUESTIONS = ROOT / CFG["paths"]["questions"]
REPORT = ROOT / CFG["paths"]["report"]
PRICING = CFG["pricing_usd_per_1m_tokens"]
TOP_K = int(CFG["retrieval"]["top_k"])


def load_questions() -> list[dict]:
    rows = []
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "uncommitted"


def corpus_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    docs = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    chars = conn.execute("SELECT SUM(n_chars) FROM chunks").fetchone()[0] or 0
    conn.close()
    return {"docs": docs, "chunks": chunks, "chars": chars}


def evaluate(questions: list[dict]) -> dict:
    from retrieve import PIPELINES, search

    answerable = [q for q in questions if q.get("answerable", True)]
    results: dict[str, dict] = {}
    retrieved_log: dict[str, dict[str, list[str]]] = {}

    for name in PIPELINES:
        hits = 0
        lat: list[float] = []
        retrieved_log[name] = {}
        for q in questions:
            t0 = time.perf_counter()
            top = search(name, q["q"], TOP_K)
            lat.append((time.perf_counter() - t0) * 1000)
            sections = [h.section for h in top]
            retrieved_log[name][q["id"]] = sections
            if q.get("answerable", True) and any(g in sections for g in q.get("gold", [])):
                hits += 1
        results[name] = {
            "recall@5": hits / len(answerable) if answerable else 0.0,
            "p50_ms": float(np.percentile(lat, 50)),
            "p95_ms": float(np.percentile(lat, 95)),
            "hits": hits,
            "n": len(answerable),
        }
    return {"metrics": results, "retrieved": retrieved_log}


def answer_pass(questions: list[dict], n: int) -> dict | None:
    if n <= 0:
        return None
    from answer import ask
    from retrieve import search

    sample = [q for q in questions if q.get("answerable", True)][:n]
    tin = tout = 0
    rows = []
    for q in sample:
        hits = search("hybrid", q["q"], TOP_K)
        t0 = time.perf_counter()
        res = ask(q["q"], hits)
        dt = (time.perf_counter() - t0) * 1000
        tin += res.get("tokens_in") or 0
        tout += res.get("tokens_out") or 0
        gold_hit = any(g in [h.section for h in hits] for g in q.get("gold", []))
        rows.append(
            {
                "id": q["id"],
                "gold_retrieved": gold_hit,
                "cited": sorted(set(res["citations"])),
                "ms": round(dt),
                "answer": res["answer"].strip().replace("\n", " ")[:400],
            }
        )
    per_q_in, per_q_out = tin / len(sample), tout / len(sample)
    cost = None
    if PRICING.get("answer_in") is not None and PRICING.get("answer_out") is not None:
        cost = (per_q_in * PRICING["answer_in"] + per_q_out * PRICING["answer_out"]) / 1_000_000 * 1000
    return {
        "n": len(sample),
        "tokens_in_per_q": round(per_q_in, 1),
        "tokens_out_per_q": round(per_q_out, 1),
        "tokens_in_per_1000q": round(per_q_in * 1000),
        "tokens_out_per_1000q": round(per_q_out * 1000),
        "usd_per_1000q": cost,
        "rows": rows,
    }


def fmt_cost(cost) -> str:
    return "n/a (pricing not configured)" if cost is None else f"${cost:.4f}"


def write_report(metrics: dict, ans: dict | None, stats: dict) -> None:
    m = metrics["metrics"]
    lines = [
        "# Baseline — Phase 1 RAG (W45)",
        "",
        f"- Chạy lúc: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Commit: `{git_sha()}`",
        f"- Corpus: **{stats['docs']} tài liệu · {stats['chunks']} chunk · {stats['chars']:,} ký tự**",
        f"- Embedder: `{CFG['embedder']['model']}` @ {CFG['embedder']['dim']}d · Answer model: `{CFG['answer']['model']}`",
        f"- Eval set: **{m['bm25']['n']} câu answerable** + câu unanswerable (dùng cho hallucination ở W47)",
        "",
        "## Kết quả retrieval",
        "",
        "| pipeline | recall@5 | p50 | p95 |",
        "|---|---|---|---|",
    ]
    for name, r in m.items():
        lines.append(
            f"| {name} | **{r['recall@5']:.2f}** ({r['hits']}/{r['n']}) | {r['p50_ms']:.0f} ms | {r['p95_ms']:.0f} ms |"
        )

    if ans:
        lines += [
            "",
            "## Cost (đo thật trên " + str(ans["n"]) + " câu, ngoại suy /1000 câu)",
            "",
            "| metric | giá trị |",
            "|---|---|",
            f"| token vào / câu | {ans['tokens_in_per_q']} |",
            f"| token ra / câu | {ans['tokens_out_per_q']} |",
            f"| token vào /1000 câu | {ans['tokens_in_per_1000q']:,} |",
            f"| token ra /1000 câu | {ans['tokens_out_per_1000q']:,} |",
            f"| USD /1000 câu | {fmt_cost(ans['usd_per_1000q'])} |",
            "",
            "| câu | gold nằm trong top-5 | chunk được trích | ms |",
            "|---|---|---|---|",
        ]
        for row in ans["rows"]:
            cited = ", ".join(row["cited"][:3]) or "—"
            lines.append(
                f"| {row['id']} | {'✅' if row['gold_retrieved'] else '❌'} | {cited} | {row['ms']} |"
            )

    lines += [
        "",
        "## Ghi chú (đọc trước khi trích số)",
        "",
        "- `recall@5` đo **retrieval**, không đo văn phong câu trả lời.",
        "- Câu `unanswerable` bị loại khỏi recall; chúng dùng để đo hallucination ở W47.",
        "- Cost embedding là chi phí **một lần** khi index; cost/1000 câu ở trên chỉ tính bước answer.",
        "- Latency đo trên VPS dùng chung, gồm cả network tới API provider.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", type=int, default=0, help="run answer step on N questions")
    ap.add_argument("--report", action="store_true", help="write reports/baseline.md")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print("run ingest.py first", file=sys.stderr)
        return 1
    questions = load_questions()
    stats = corpus_stats()
    out = evaluate(questions)
    m = out["metrics"]

    print(f"corpus: {stats['docs']} docs · {stats['chunks']} chunks · {stats['chars']:,} chars")
    print(f"eval set: {m['bm25']['n']} answerable / {len(questions)} questions\n")
    print(f"{'pipeline':10}{'recall@5':>10}{'p50':>9}{'p95':>9}")
    for name, r in m.items():
        print(f"{name:10}{r['recall@5']:>10.2f}{r['p50_ms']:>8.0f}ms{r['p95_ms']:>8.0f}ms")

    by_id = {q["id"]: q for q in questions}
    for name in m:
        misses = [
            qid
            for qid, secs in out["retrieved"][name].items()
            if by_id[qid].get("answerable", True)
            and not any(g in secs for g in by_id[qid].get("gold", []))
        ]
        if misses:
            print(f"\n{name} miss: {', '.join(misses)}")

    ans = answer_pass(questions, args.answer)
    if ans:
        print(
            f"\nanswer step ({ans['n']} câu): {ans['tokens_in_per_q']} tok in + "
            f"{ans['tokens_out_per_q']} tok out / câu -> "
            f"{ans['tokens_in_per_1000q']:,} + {ans['tokens_out_per_1000q']:,} tok /1000 câu · "
            f"cost {fmt_cost(ans['usd_per_1000q'])}"
        )

    if args.report:
        write_report(out, ans, stats)
        print(f"\nreport -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
