# W47 — retrieval trên eval set 40 câu (W46 để lại 17 câu)

- Chạy lúc: 2026-11-16 04:31 UTC
- Commit: `734e5be`
- Corpus: **7 tài liệu · 1686 chunk · 1,656,953 ký tự**
- Embedder: `BAAI/bge-small-en-v1.5` @ 384d · Answer model: `deepseek-v4-flash`
- Eval set: **40 câu answerable** + câu unanswerable (dùng cho hallucination ở W47)

## Kết quả retrieval

| pipeline | recall@5 | p50 | p95 |
|---|---|---|---|
| bm25 | **0.75** (30/40) | 3 ms | 5 ms |
| dense | **0.82** (33/40) | 53 ms | 125 ms |
| hybrid | **0.82** (33/40) | 63 ms | 87 ms |

## Ghi chú (đọc trước khi trích số)

- `recall@5` đo **retrieval**, không đo văn phong câu trả lời.
- Câu `unanswerable` bị loại khỏi recall; chúng dùng để đo hallucination ở W47.
- Cost embedding là chi phí **một lần** khi index; cost/1000 câu ở trên chỉ tính bước answer.
- Latency đo trên VPS dùng chung, gồm cả network tới API provider.
