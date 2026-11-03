# fde-rag-eval — Phase 1: RAG + evals có số đo

Repo này của dự án **Forward Deployed Engineer** (xem vault: `On-going projects/Forward Deployed Engineer/`).
Mục đích: đóng gap **LLM / RAG / evals** (32% JD FDE) bằng **bằng chứng đo được**, không phải "đã học".

Phase 1 trả lời đúng một câu: *retrieval của mình tốt đến đâu, bằng số?*

## Cấu trúc

```
rag-eval/
├── config.yaml          # corpus, chunking, embedder, answer model, pricing
├── fetch_corpus.py      # tải 7 tài liệu public → data/corpus/*.md
├── ingest.py            # text → section → chunk → SQLite + FTS5
├── embed.py             # Gemini gemini-embedding-001 (768d), cache theo sha1
├── retrieve.py          # bm25 | dense | hybrid (RRF)
├── answer.py            # DeepSeek + citation bắt buộc
├── run_eval.py          # recall@5 · p50/p95 · cost/1000 câu
├── evals/questions.jsonl
├── data/corpus/         # text đã convert (commit) + manifest.json
└── reports/baseline.md  # deliverable W45
```

Phase sau nằm ở thư mục khác trong repo: `deploy/` (W48–W50), `poc-1..3/` (W51–W53), `enterprise/` (W01–W03).

## Chạy

```bash
cd rag-eval
export GOOGLE_API_KEY=... DEEPSEEK_API_KEY=...   # hoặc source ~/.hermes/.env

make corpus     # tải tài liệu public (bỏ qua nếu đã có .md)
make ingest     # → data/index.sqlite
make embed      # → vectors (cache, chạy lại không tốn)
make eval       # → bảng recall@5 · p50/p95
make report     # → reports/baseline.md
```

Kiểm tay một câu:

```bash
python3 retrieve.py "Within how many hours must a breach be notified?"
python3 answer.py   "Within how many hours must a breach be notified?"
```

## Corpus (public, không có dữ liệu cá nhân)

| doc | nội dung | license |
|---|---|---|
| `ai_act` | EU AI Act 2024/1689 | EUR-Lex reuse — attribution |
| `gdpr` | GDPR 2016/679 | EUR-Lex reuse — attribution |
| `psd2` | PSD2 2015/2366 | EUR-Lex reuse — attribution |
| `eba_rts_sca` | EBA RTS 2018/389 (SCA) | EUR-Lex reuse — attribution |
| `nist_ai_rmf` | NIST AI RMF 1.0 | US public domain |
| `nist_800_63b` | NIST SP 800-63B | US public domain |
| `basel3` | Basel III final (BIS d424) | BIS — free w/ attribution |

## Định nghĩa số đo

- **recall@5** — tỉ lệ câu hỏi mà **section gold** nằm trong top-5 section retrieve được. Gold là `doc#article` (vd `gdpr#art33`), nên đổi cách chunk không làm hỏng eval.
- **p50/p95 latency** — riêng bước retrieval, đo trên VPS.
- **cost/1000 câu** — token vào/ra đo thật trên N câu rồi ngoại suy; giá đọc từ `config.yaml` (`pricing_usd_per_1m_tokens`), `null` = chưa cấu hình → báo `n/a`.
- **unanswerable** — câu không có đáp án trong corpus; loại khỏi recall, dùng đo hallucination ở W47.

## Nguyên tắc

- Không thêm framework (LangChain/LlamaIndex): eval phải tự viết mới đo được.
- Không thêm dependency nặng (torch/faiss): vài nghìn chunk thì numpy đủ.
- Số liệu phải tái lập: corpus text + manifest (URL, license, sha256) được commit; index build lại bằng `make ingest embed`.
