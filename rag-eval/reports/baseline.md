# Baseline — Phase 1 RAG (W45)

- Chạy lúc: 2026-11-03 15:02 UTC
- Commit: `b9d418f`
- Corpus: **7 tài liệu · 1167 chunk · 1,658,620 ký tự**
- Embedder: `BAAI/bge-small-en-v1.5` @ 384d · Answer model: `deepseek-v4-flash`
- Eval set: **4 câu answerable** + câu unanswerable (dùng cho hallucination ở W47)

## Kết quả retrieval

| pipeline | recall@5 | p50 | p95 |
|---|---|---|---|
| bm25 | **0.75** (3/4) | 6 ms | 28 ms |
| dense | **0.50** (2/4) | 20 ms | 639 ms |
| hybrid | **0.50** (2/4) | 22 ms | 28 ms |

## Cost (đo thật trên 4 câu, ngoại suy /1000 câu)

| metric | giá trị |
|---|---|
| token vào / câu | 2196.2 |
| token ra / câu | 507.2 |
| token vào /1000 câu | 2,196,250 |
| token ra /1000 câu | 507,250 |
| USD /1000 câu | n/a (pricing not configured) |

| câu | gold nằm trong top-5 | chunk được trích | ms |
|---|---|---|---|
| q001 | ❌ | — | 5195 |
| q002 | ✅ | gdpr#art33 | 1940 |
| q003 | ❌ | ai_act#art49, ai_act#art6-p1, ai_act#art74-p2 | 2620 |
| q004 | ✅ | psd2#art74 | 4652 |

## Chẩn đoán — vì sao số trông như vậy (đây là đầu vào của W46)

| # | Phát hiện | Bằng chứng thật | Việc cần làm ở W46 |
|---|---|---|---|
| D1 | **BM25 thắng dense** trên văn bản luật | q001: bm25 có `eba_rts_sca#art11` trong top-5, dense không có | thử rerank (cross-encoder) + chỉnh trọng số RRF thay vì 1:1 |
| D2 | **Chunk tiêu đề rỗng làm nhiễu dense** | dense trả `ai_act#ch3`, `ai_act#sec2`, `ai_act#sec3` — chunk chỉ gồm heading | đặt lại sàn `min_chars` (gộp chunk < 300 chars vào chunk sau) |
| D3 | **Recital dùng chung 1 section id** → nhiều chunk trùng tên chiếm top-5 | q001 dense trả 3 chunk đều tên `eba_rts_sca#the-european-commission` | tách recital thành `rec1..recN` để top-5 đa dạng nguồn |
| D4 | **Câu "liệt kê trong Annex" khó cho cả 2 pipeline** | q003 miss ở cả bm25 và dense: ANNEX III là danh sách thuần, không chứa cụm "high-risk" | thử query expansion (HyDE) hoặc chunk theo từng item của Annex |
| D5 | **Eval set 4 câu ⇒ mỗi câu = 25 điểm recall** | 0,75 vs 0,50 chỉ khác nhau **1 câu** | mở lên 50 câu rồi mới kết luận pipeline nào thắng |

> Đọc đúng: ở 4 câu, chênh lệch bm25/dense **chưa đủ tin cậy để kết luận**. Con số dùng được ngay là
> **chi phí token** và **thứ tự tài liệu tìm được** (D1–D4), không phải "bm25 tốt hơn dense".

## Tái lập

```bash
cd rag-eval
make corpus          # 7 tài liệu public -> data/corpus
make ingest          # -> 1167 chunk (section-aware)
make embed           # local bge-small-en-v1.5, 384d  (~10 phút trên VPS 2 vCPU)
make report          # bảng trên + reports/baseline.md
```

## Ghi chú (đọc trước khi trích số)

- `recall@5` đo **retrieval**, không đo văn phong câu trả lời.
- Câu `unanswerable` bị loại khỏi recall; chúng dùng để đo hallucination ở W47.
- Cost embedding là chi phí **một lần** khi index; cost/1000 câu ở trên chỉ tính bước answer.
- Latency retrieval đo trên VPS 2 vCPU; `dense p95 639 ms` gồm lần load model ONNX đầu tiên.
- Latency answer (1,9–5,2 s/câu) là **network + DeepSeek**, không phải retrieval.
- Giá token chưa cấu hình (`pricing_usd_per_1m_tokens: null`) nên cost in `n/a` — cố ý không đoán giá.

