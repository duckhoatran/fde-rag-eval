.PHONY: help corpus ingest embed eval report all

help:
	@$(MAKE) -C rag-eval help

corpus ingest embed eval report all:
	@$(MAKE) -C rag-eval $@
