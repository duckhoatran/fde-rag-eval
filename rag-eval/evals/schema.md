# Schema — `evals/questions.jsonl`

Mỗi dòng là một JSON object. Không có comment trong file; dòng bắt đầu bằng `//` bị bỏ qua.

| field | kiểu | bắt buộc | ý nghĩa |
|---|---|---|---|
| `id` | string | ✅ | `q001`, `q002`… dùng để đối chiếu khi pipeline miss |
| `q` | string | ✅ | câu hỏi, tiếng Anh (corpus là tiếng Anh) |
| `gold` | string[] | ✅ | section id kỳ vọng, dạng `doc#section` — rỗng nếu `answerable=false` |
| `type` | string | — | `lookup` · `list` · `multi-hop` · `unanswerable` |
| `answerable` | bool | — | mặc định `true`. `false` = corpus không có đáp án (đo hallucination) |

## Quy tắc viết gold

- `gold` là **section**, không phải chunk: `gdpr#art33` (không phải `gdpr#art33-p2`). Nhờ vậy đổi cách chunk không làm hỏng eval.
- Section id lấy từ `ingest.py`: `Article 33` → `art33` · `ANNEX III` → `annex3` · `4.2.1` → `sec4-2-1` · window chunk → `w001`.
- Liệt kê **tối đa 3** section nếu câu trả lời nằm rải ở nhiều nơi; nhiều hơn nghĩa là câu hỏi chưa đủ hẹp.
- Muốn biết section id thật:
  ```bash
  sqlite3 data/index.sqlite "select section, heading from chunks where doc_id='gdpr' limit 20;"
  ```

## Câu `unanswerable`

Đặt `"answerable": false` và `gold: []`. Mục đích: đo **hallucination rate** ở W47 — model phải trả lời `insufficient evidence`, không được bịa.

## Ví dụ

```json
{"id":"q002","q":"Within how many hours must a controller notify a personal data breach?","gold":["gdpr#art33"],"type":"lookup","answerable":true}
{"id":"q005","q":"What does PCI DSS v4.0 require for cryptographic key rotation?","gold":[],"type":"unanswerable","answerable":false}
```
