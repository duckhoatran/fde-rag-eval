.PHONY: help corpus ingest embed eval report all clean

# fastembed (local ONNX) lives in its own venv; everything else is stdlib+system deps.
PY ?= $(shell test -x $(HOME)/.venvs/fde/bin/python && echo $(HOME)/.venvs/fde/bin/python || echo python3)

help:
	@echo "make corpus  - tải 7 tài liệu public -> data/corpus/*.md"
	@echo "make ingest  - text -> chunk -> data/index.sqlite (+FTS5)"
	@echo "make embed   - embeddings local (bge-small-en-v1.5, cache sha1)"
	@echo "make eval    - recall@5 · p50/p95 (không gọi LLM)"
	@echo "make report  - ghi reports/baseline.md (eval + answer 5 câu)"
	@echo "make all     - corpus ingest embed eval"
	@echo "  PY=$(PY)"

corpus:
	$(PY) fetch_corpus.py

ingest:
	$(PY) ingest.py

embed:
	$(PY) embed.py

eval:
	$(PY) run_eval.py

report:
	$(PY) run_eval.py --answer 5 --report

all: corpus ingest embed eval

clean:
	rm -f data/index.sqlite
