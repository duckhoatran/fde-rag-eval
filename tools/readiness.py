#!/usr/bin/env python3
"""Readiness score for the FDE evidence project — one rubric, applied to every milestone.

The 80 % baseline recorded on 28/09/2026 was never written down as weights x coverage, so at M1 the
honest answer was "cannot be compared". This script fixes that: it recomputes the weights from both
JD corpora with the same vocabulary, applies one coverage rule, and scores both milestones.

    python3 tools/readiness.py                      # uses the two corpora below
    python3 tools/readiness.py --out READINESS.md

Rubric (also stored in tools/coverage.json so a change is a diff, not a memory):

  weight_i   = % of FDE JDs asking for requirement i, measured by analyze_fde_demand.SKILLS
               over the corpus of that milestone
  coverage_i = 1   an artifact exists (repo, report, system in production) and is named
               0.5 skill/experience exists but no artifact to point at
               0    nothing
  readiness  = sum(w_i * coverage_i) / sum(w_i)   over scored requirements

Excluded on purpose: "Travel required" — a condition of employment, not a capability. Scoring it
would be awarding points for being willing to board a plane.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COVERAGE = ROOT / "coverage.json"
DEMAND_SCRIPT = Path.home() / ".hermes/scripts/analyze_fde_demand.py"

MILESTONES = {
    "baseline": {
        "label": "Baseline 28/09/2026",
        "corpus": Path.home() / ".hermes/scripts/out/fde_corpus_2026-09-28.json",
    },
    "now": {
        "label": "M1 16/11/2026",
        "corpus": Path("/tmp/fde_jobs.json"),
    },
}


def load_demand_module():
    spec = importlib.util.spec_from_file_location("analyze_fde_demand", DEMAND_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # module-level code is only the regex/vocab tables
    return mod


def weights(mod, jobs: list[dict]) -> tuple[dict[str, float], int]:
    """% of JDs mentioning each requirement, after the same dedupe/filter as the demand script."""
    seen, uniq = set(), []
    for j in jobs:
        if not mod.FDE_TITLE.search(j.get("title") or ""):
            continue
        key = (j.get("company"), j.get("title"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    with_text = [j for j in uniq if len(j.get("text") or "") > 400]

    def section(t: str) -> str:
        m = mod.SECT.search(t)
        return t[m.start():] if m else t

    n = max(len(with_text), 1)
    out = {}
    for name, rx in mod.SKILLS.items():
        hits = sum(1 for j in with_text if re.search(rx, section(j["text"]), re.I))
        out[name] = 100.0 * hits / n
    return out, len(with_text)


def score(weight: dict[str, float], coverage: dict[str, dict], excluded: dict[str, str]) -> dict:
    total_w = num = 0.0
    rows = []
    for name, w in weight.items():
        if name in excluded:
            continue
        cov = coverage.get(name, {}).get("coverage")
        if cov is None:
            raise SystemExit(f"no coverage entry for requirement {name!r} — add it to tools/coverage.json")
        total_w += w
        num += w * cov
        rows.append((name, w, cov, w * cov))
    rows.sort(key=lambda r: -(r[1] * (1 - r[2])))  # biggest remaining gap first
    return {"readiness": num / total_w if total_w else 0.0, "rows": rows, "total_w": total_w}


def pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="write a markdown report to this path")
    args = ap.parse_args()

    mod = load_demand_module()
    cfg = json.loads(COVERAGE.read_text(encoding="utf-8"))
    buckets = cfg["buckets"]
    excluded = cfg["_excluded"]

    results = {}
    for key, meta in MILESTONES.items():
        if not meta["corpus"].exists():
            raise SystemExit(f"corpus missing for {key}: {meta['corpus']}")
        jobs = json.loads(meta["corpus"].read_text(encoding="utf-8"))
        w, n = weights(mod, jobs)
        cov = {b: {"coverage": buckets.get(b, {}).get(key, {}).get("coverage", 0.0)} for b in w}
        results[key] = {
            "label": meta["label"],
            "n_jd": n,
            **score(w, cov, excluded),
            "weights": w,
            "coverage": cov,
            "corpus": str(meta["corpus"]),
        }

    base, now = results["baseline"], results["now"]
    delta = now["readiness"] - base["readiness"]

    def project(changes: dict[str, float]) -> float:
        cov = {k: dict(v) for k, v in now["coverage"].items()}
        for k, v in changes.items():
            cov[k] = {"coverage": v}
        return score(now["weights"], cov, excluded)["readiness"]

    print(f"{'milestone':22}{'JD':>6}{'readiness':>12}")
    for k in ("baseline", "now"):
        r = results[k]
        print(f"{r['label']:22}{r['n_jd']:>6}{pct(r['readiness']):>12}")
    print(f"{'delta':22}{'':>6}{delta * 100:>+11.1f} pp")

    if args.out:
        ratio = (now["readiness"] / base["readiness"] - 1) * 100 if base["readiness"] else 0.0
        lines = [
            "# Readiness — FDE evidence project",
            "",
            "One rubric applied to both milestones, both weights recomputed from the JD corpora with the same",
            "vocabulary (`analyze_fde_demand.SKILLS`). Regenerate with `python3 tools/readiness.py --out READINESS.md`.",
            "",
            "| milestone | corpus | JD | readiness |",
            "|---|---|---|---|",
            f"| {base['label']} | `{Path(base['corpus']).name}` | {base['n_jd']} | **{pct(base['readiness'])}** |",
            f"| {now['label']} | `{Path(now['corpus']).name}` | {now['n_jd']} | **{pct(now['readiness'])}** |",
            "| delta | | | **{d}** ({r:+.0f} %) |".format(d=f"{delta * 100:+.1f} pp", r=ratio),
            "",
            f"Excluded from the score: {', '.join(f'*{k}* ({v})' for k, v in excluded.items())}.",
            "",
            "## Route to the 80 % target",
            "",
            "| khi xong | readiness dự phóng |",
            "|---|---|",
            f"| M1 hôm nay | {pct(now['readiness'])} |",
            f"| + W48 Docker | {pct(project({'Docker': 1}))} |",
            f"| + Phase 2 đủ (Docker · CI/CD · Terraform · Cloud) → **M2** | "
            f"**{pct(project({'Docker': 1, 'CI/CD': 1, 'Terraform / IaC': 1, 'Cloud (AWS/GCP/Azure)': 1}))}** |",
            f"| + Kubernetes | {pct(project({'Docker': 1, 'CI/CD': 1, 'Terraform / IaC': 1, 'Cloud (AWS/GCP/Azure)': 1, 'Kubernetes': 1}))} |",
            f"| + video demo (pre-sales 1.0) | {pct(project({'Docker': 1, 'CI/CD': 1, 'Terraform / IaC': 1, 'Cloud (AWS/GCP/Azure)': 1, 'Pre-sales / demo': 1}))} |",
            "",
            "Đọc: mục tiêu **80 %** đạt được ở **M2 (W50)**, không phải M1 — và đó là điều plan 13 tuần vốn nói "
            "(M2 mới đóng gap Cloud/CI-CD/IaC). Con số 80 % ghi ngày 28/09 không phải baseline của rubric này; "
            "baseline của rubric này là con số ở bảng trên.",
            "",
            "## What still costs the most points (M1)",
            "",
            "| requirement | % JD | coverage | points lost | evidence |",
            "|---|---|---|---|---|",
        ]
        for name, w, cov, contrib in now["rows"]:
            ev = buckets.get(name, {}).get("now", {}).get("evidence", "—")
            lost = w * (1 - cov)
            if lost <= 0.5:
                continue
            lines.append(f"| {name} | {w:.0f} % | {cov:g} | {lost:.1f} | {ev} |")
        lines += [
            "",
            "## Full table",
            "",
            "| requirement | weight (baseline JD) | weight (M1 JD) | coverage baseline | coverage M1 |",
            "|---|---|---|---|---|",
        ]
        for name, _w, _c, _t in now["rows"]:
            cb = buckets.get(name, {}).get("baseline", {}).get("coverage", 0.0)
            cm = buckets.get(name, {}).get("now", {}).get("coverage", 0.0)
            lines.append(
                f"| {name} | {base['weights'].get(name, 0):.0f} % | {now['weights'].get(name, 0):.0f} % | {cb:g} | {cm:g} |"
            )
        lines += [
            "",
            "## Rules (so the next milestone is comparable)",
            "",
            "1. Weights are always recomputed from the fresh JD corpus — never copied from the previous milestone.",
            "2. Coverage 1 requires a **named artifact** (repo path, report, running system). \"Đã học\" is 0.5 at most.",
            "3. A requirement is never dropped because it is inconvenient; only *conditions of employment* are excluded.",
            "4. Score is Σ(w×coverage)/Σw over the requirements present in that corpus — no weighting by hand.",
            "",
        ]
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nreport -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
