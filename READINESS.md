# Readiness — FDE evidence project

One rubric applied to both milestones, both weights recomputed from the JD corpora with the same
vocabulary (`analyze_fde_demand.SKILLS`). Regenerate with `python3 tools/readiness.py --out READINESS.md`.

| milestone | corpus | JD | readiness |
|---|---|---|---|
| Baseline 28/09/2026 | `fde_corpus_2026-09-28.json` | 982 | **64.0 %** |
| M1 16/11/2026 | `fde_jobs.json` | 989 | **76.4 %** |
| delta | | | **+12.4 pp** (+19 %) |

Excluded from the score: *Travel required* (điều kiện công việc, không phải năng lực cần bằng chứng — tính vào nó là tự thưởng điểm).

## Route to the 80 % target

| khi xong | readiness dự phóng |
|---|---|
| M1 hôm nay | 76.4 % |
| + W48 Docker | 77.3 % |
| + Phase 2 đủ (Docker · CI/CD · Terraform · Cloud) → **M2** | **84.0 %** |
| + Kubernetes | 85.8 % |
| + video demo (pre-sales 1.0) | 84.0 % |

Đọc: mục tiêu **80 %** đạt được ở **M2 (W50)**, không phải M1 — và đó là điều plan 13 tuần vốn nói (M2 mới đóng gap Cloud/CI-CD/IaC). Con số 80 % ghi ngày 28/09 không phải baseline của rubric này; baseline của rubric này là con số ở bảng trên.

## What still costs the most points (M1)

| requirement | % JD | coverage | points lost | evidence |
|---|---|---|---|---|
| Ownership / ambiguous problems | 40 % | 0.5 | 19.9 | FDE lab 0→1 có DoD + lịch sử commit; vẫn không tự nâng lên 1 khi chưa có người dùng thật |
| AI agents / MCP / tooling | 39 % | 0.5 | 19.6 | vận hành Hermes agent (skills/cron/MCP tools) hằng ngày nhưng chưa có artifact ship được |
| Code review / mentoring | 31 % | 0.5 | 15.7 | không đổi |
| CI/CD | 14 % | 0 | 13.7 | chưa có — W49 |
| Cloud (AWS/GCP/Azure) | 26 % | 0.5 | 12.9 | không đổi; Phase 2 (W48–W50) mới đóng phần này |
| Kubernetes | 9 % | 0 | 8.9 | chưa có — không nằm trong Phase 2 bắt buộc |
| Terraform / IaC | 8 % | 0 | 7.8 | chưa có — W50 |
| Data engineering (ETL/warehouse) | 15 % | 0.5 | 7.6 | ingest→embed→index là pipeline thật nhưng chỉ 1.686 chunk |
| Docker | 4 % | 0 | 4.3 | chưa có — W48 |
| Enterprise deployment (on-prem/air-gapped) | 4 % | 0 | 4.1 | chưa có — W02 |
| Networking/security (SSO, VPC, IAM) | 6 % | 0.5 | 3.0 | không đổi — Phase 4 (W01–W03) |
| Data viz / BI | 4 % | 0.5 | 2.1 | không đổi |

## Full table

| requirement | weight (baseline JD) | weight (M1 JD) | coverage baseline | coverage M1 |
|---|---|---|---|---|
| Ownership / ambiguous problems | 38 % | 40 % | 0.5 | 0.5 |
| AI agents / MCP / tooling | 42 % | 39 % | 0 | 0.5 |
| Code review / mentoring | 34 % | 31 % | 0.5 | 0.5 |
| CI/CD | 13 % | 14 % | 0 | 0 |
| Cloud (AWS/GCP/Azure) | 28 % | 26 % | 0.5 | 0.5 |
| Kubernetes | 12 % | 9 % | 0 | 0 |
| Terraform / IaC | 8 % | 8 % | 0 | 0 |
| Data engineering (ETL/warehouse) | 17 % | 15 % | 0.5 | 0.5 |
| Docker | 7 % | 4 % | 0 | 0 |
| Enterprise deployment (on-prem/air-gapped) | 5 % | 4 % | 0 | 0 |
| Networking/security (SSO, VPC, IAM) | 5 % | 6 % | 0.5 | 0.5 |
| Data viz / BI | 4 % | 4 % | 0.5 | 0.5 |
| Python | 53 % | 51 % | 1 | 1 |
| SQL / data modelling | 20 % | 21 % | 1 | 1 |
| JavaScript/TypeScript | 26 % | 24 % | 1 | 1 |
| REST/GraphQL API | 34 % | 35 % | 1 | 1 |
| Linux / shell | 10 % | 11 % | 1 | 1 |
| LLM / RAG | 32 % | 30 % | 0.5 | 1 |
| Customer-facing / discovery | 66 % | 72 % | 1 | 1 |
| Pre-sales / demo | 41 % | 42 % | 0.5 | 1 |
| Async / writing | 22 % | 22 % | 1 | 1 |

## Rules (so the next milestone is comparable)

1. Weights are always recomputed from the fresh JD corpus — never copied from the previous milestone.
2. Coverage 1 requires a **named artifact** (repo path, report, running system). "Đã học" is 0.5 at most.
3. A requirement is never dropped because it is inconvenient; only *conditions of employment* are excluded.
4. Score is Σ(w×coverage)/Σw over the requirements present in that corpus — no weighting by hand.

