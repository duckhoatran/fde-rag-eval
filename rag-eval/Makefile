.PHONY: help corpus ingest embed eval report all clean

help:
	@echo "make corpus  - tải 7 tài liệu public -> data/corpus/*.md"
	@echo "make ingest  - text -> chunk -> data/index.sqlite (+FTS5)"
	@echo "make embed   - Gemini embeddings (cache sha1)"
	@echo "make eval    - recall@5 · p50/p95 (không gọi LLM)"
	@echo "make report  - ghi reports/baseline.md (eval + answer 5 câu)"
	@echo "make all     - corpus ingest embed eval"

corpus:
	python3 fetch_corpus.py

ingest:
	python3 ingest.py

embed:
	python3 embed.py

eval:
	python3 run_eval.py

report:
	python3 run_eval.py --answer 5 --report

all: corpus ingest embed eval

clean:
	rm -f data/index.sqlite
	rm -f data/emb.npy
