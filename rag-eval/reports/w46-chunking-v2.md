# W46 — chunking v2 (recital + annex item split)

- Chạy lúc: 2026-11-09 15:24 UTC
- Commit: `ce90cfa`
- Corpus: **7 tài liệu · 1686 chunk · 1,656,953 ký tự**
- Embedder: `BAAI/bge-small-en-v1.5` @ 384d · Answer model: `deepseek-v4-flash`
- Eval set: **17 câu answerable** + câu unanswerable (dùng cho hallucination ở W47)

## Kết quả retrieval

| pipeline | recall@5 | p50 | p95 |
|---|---|---|---|
| bm25 | **0.71** (12/17) | 3 ms | 4 ms |
| dense | **0.71** (12/17) | 66 ms | 146 ms |
| hybrid | **0.71** (12/17) | 60 ms | 77 ms |

## Trước ↔ sau (cùng 20 câu, cùng embedder)

| pipeline | v1 (1167 chunk) | v2 (1686 chunk) | Δ |
|---|---|---|---|
| bm25 | 0,71 (12/17) | **0,71** (12/17) | 0 |
| dense | 0,71 (12/17) | **0,71** (12/17) | 0 |
| hybrid | 0,65 (11/17) | **0,71** (12/17) | **+6 điểm %** |

**Kết luận thẳng: chưa đạt ngưỡng W46 (≥ +10 điểm %).** Chỉ hybrid tăng 6 điểm.

## ⚠️ Một sai lệch đã tự phát hiện và sửa

Lần đo đầu tiên của v2 báo `dense 0,82 (+11 điểm)` — **con số đó là giả**: lúc đo, index mới embed xong **1.426/1.686 chunk** (thiếu 260 chunk chưa có vector), nên dense chỉ tìm trong 85% corpus và vô tình bỏ qua vài chunk gây nhiễu. Embed xong đủ 1.686 thì dense về **0,71**.

⇒ Bài học dùng được khi phỏng vấn: **eval phải assert index đầy đủ trước khi tin số**. Đã thêm cảnh báo coverage vào ghi chú dưới.

## Vì sao không tăng — 3 lý do có bằng chứng

1. **Chunk nhỏ hơn nhưng không "khớp từ vựng" hơn.** v2 cắt nhỏ (avg 983 ký tự so với 1.421) ⇒ mỗi chunk tả ít ngữ cảnh hơn, trong khi câu hỏi lại dùng từ khác bài luật (q012 hỏi *"notify"*, Article 75 dùng *"notification and rectification"*).
2. **Top-5 bị các điều khoản "nhắc tới" chiếm chỗ.** q001/q013/q014: các article khác nhắc *"strong customer authentication"*, *"transaction risk analysis"* nhiều lần hơn chính điều khoản định nghĩa ⇒ BM25 và dense đều xếp chúng lên trước.
3. **Annex split giúp BM25 nhưng không giúp dense.** q003 giờ **hit ở bm25** (trước miss), nhưng dense vẫn miss vì vector của một mục Annex (danh sách) không gần câu hỏi "categories".

## Việc W46 còn lại (T4)

- [ ] **Rerank** (cross-encoder bge-reranker-base) trên top-20 → đo lại; đây mới là đòn đánh đúng vào lỗi #2.
- [ ] **Query expansion**: sinh 2–3 biến thể câu hỏi (thuật ngữ pháp lý) trước khi retrieve.
- [ ] **pytest threshold**: `assert dense_recall >= 0.70` + `assert index_coverage == 1.0` — chặn đúng lỗi vừa xảy ra.
- [ ] Đo lại cost/1000 câu khi bật rerank (thêm 1 model local, không tốn API).

## Ghi chú (đọc trước khi trích số)

- `recall@5` đo **retrieval**, không đo văn phong câu trả lời.
- Câu `unanswerable` bị loại khỏi recall; chúng dùng để đo hallucination ở W47.
- Cost embedding là chi phí **một lần** khi index; cost/1000 câu ở trên chỉ tính bước answer.
- Latency retrieval đo trên VPS 2 vCPU. `dense p50` tăng 25→66 ms vì corpus chunk nhiều hơn (1.686 vs 1.167).
- **Coverage:** trước khi tin recall, kiểm `select count(*) from chunks where chunk_id not in (select chunk_id from emb)` phải = 0.
