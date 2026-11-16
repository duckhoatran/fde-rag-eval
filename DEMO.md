# 3-minute demo — script and commands

The video itself is recorded by hand (screen + voice); this file exists so the recording is one take, not
an improvisation. Total: 3 min, 5 blocks. Every command is copy-paste and works from a clean shell.

## Status (16/11/2026)

**Recorded, generated headlessly:** `demo/w47-demo.mp4` — 2:26, 1600×900, every terminal line produced by
actually running the commands below (`/tmp/demo/capture.json`), narration synthesised with Gemini TTS
(voice `Kore`), English captions burned in, `ffmpeg` H.264 + AAC, 2.8 MB.

Rebuild with `python3 /tmp/demo/{capture,tts,render}.py` (capture → narration → frames + mux). Honest caveat:
**the voice is synthetic, not K T's**. For an application video where the voice matters, re-record with a
real microphone using the same 5 blocks — the script below is the shot list.

```bash
cd ~/fde-lab/rag-eval
set -a && source ~/.hermes/.env && set +a
export PY=~/.venvs/fde/bin/python
```

## 0:00–0:25 — the claim

> "This is a compliance RAG assistant. The interesting part is not that it answers — it's that it refuses
> when the corpus doesn't contain the answer, and that I can put a number on that. Seven public regulatory
> documents, 1,686 chunks, eval set of 50 questions: 40 answerable, 10 impossible by design."

Show: `$PY -c "import json;q=[json.loads(l) for l in open('evals/questions.jsonl')];print(len(q),'questions')"`

## 0:25–1:05 — retrieval, with the caveat

```bash
$PY run_eval.py
```

> "Recall@5 on 40 answerable questions: BM25 0.75, dense and hybrid 0.82 on the same set. Two weeks ago I
> reported 0.71 for all three — that was a 17-question set, and it was wrong. The number I'd quote today is
> 0.82 at n=40, and the report says so next to every figure."

## 1:05–1:50 — the refusal arm (the actual product)

```bash
$PY answer.py "What is the maximum administrative fine under the UK Data Protection Act 2018?"
```

> "That topic isn't in the corpus. The guarded prompt refuses and lists what's missing, instead of quoting a
> figure from memory."

Then the contrast arm:

```bash
$PY answer.py --naive "What is the maximum administrative fine under the UK Data Protection Act 2018?"
```

> "Same retrieval, no guardrail: it hedges 'the context doesn't cover this' and then gives the £17.5 million
> figure from memory. That is the failure a compliance team cannot detect by reading — which is why it has
> to be measured."

## 1:50–2:30 — the measurement

```bash
sed -n '8,26p' reports/w47-guardrails.md
```

> "Ten unanswerable questions, read by hand: six hallucinated without the guardrail, zero with it.
> Grounded answers 40 out of 40. Prompt injection: 4 of 8 cases passed before, 7 of 8 after — the one that
> still fails is an instruction hidden inside a retrieved document, which needs sanitisation, not a better
> prompt. I'd rather show that gap than round it away."

## 2:30–3:00 — what breaks next

> "Cost of the guardrail is output length: 1.8× tokens, because every answer carries citations and the missing
> evidence. Next three weeks: dockerise this so a clean machine runs it in one command, put the eval in CI so
> a regression is a red build, then Terraform with a rehearsed rollback."

Show: `git log --oneline -3` and the repo URL.

## Recording notes

- Terminal font ≥ 16pt, window ~100×30, dark theme.
- Pre-warm the model: run `$PY answer.py "test"` once before recording so the first call isn't slow.
- Do not cut the refusal answer short — the "Missing: …" list *is* the feature.
- If a call errors, say so and move on; a retried take reads worse than an honest hiccup.
