#!/usr/bin/env python3
"""Narration for the demo video, synthesised with Gemini TTS (edge was 403).

Each block: (id, on-screen command key, narration text).
PCM 24 kHz s16le from the API -> wrapped as WAV, so ffmpeg reads it without a decoder game.
"""
import json
import os
import subprocess
import urllib.request
import wave
from pathlib import Path

OUT = Path("/tmp/demo/audio")
VOICE = "Kore"
MODEL = "gemini-2.5-flash-preview-tts"

BLOCKS = [
    (
        "b1",
        "tree",
        "A compliance RAG assistant over seven public regulatory documents: EU AI Act, GDPR, PSD2, the EBA rules on strong customer authentication, NIST, and Basel three. Sixteen hundred chunks, and fifty eval questions: forty answerable, ten deliberately not. The interesting part isn't that it answers. It's that it refuses when the document isn't there, and that the refusal rate is measured.",
    ),
    (
        "b2",
        "eval",
        "Retrieval first. Recall at five, on the forty answerable questions: BM25 seventy-five percent, dense and hybrid eighty-two. Two weeks ago I reported seventy-one percent for all three. That was a seventeen-question set, and it was wrong. The number I would quote today is eighty-two at n equals forty, and every report states the sample size next to the figure.",
    ),
    (
        "b3",
        "guarded",
        "Now the arm that matters. I ask about the UK Data Protection Act. It is not in the corpus. The guarded prompt answers: insufficient evidence, and lists exactly what is missing. No figure. No guess.",
    ),
    (
        "b4",
        "naive",
        "Same retrieval, same model, no guardrail. It hedges, quote, the context does not contain UK DPA provisions, and then gives the seventeen point five million figure from memory. That is the failure a compliance reviewer cannot see by reading. Which is why it has to be measured, not trusted.",
    ),
    (
        "b5",
        "metrics",
        "Ten impossible questions. The keyword classifier reports fifty percent for the unguarded arm; hand-reading all ten answers finds six. That gap is a finding in itself: three of them open with the context does not cover this, and then answer from memory anyway. With the guardrail: zero. All forty answerable answers carried a citation to a chunk that was actually retrieved. Prompt injection: four of eight cases passed before, seven of eight after. The one that still fails is an instruction hidden inside a retrieved document, which needs content sanitisation, not a better prompt.",
    ),
    (
        "b6",
        "git",
        "The cost is length: about one point eight times the output tokens, because every answer carries its citations and the missing-evidence list. Next three weeks: dockerise it, put the eval in CI so a regression is a red build, then Terraform with a rehearsed rollback.",
    ),
]


def synth(text: str, path: Path) -> None:
    key = os.environ["GOOGLE_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    d = json.load(urllib.request.urlopen(req, timeout=120))
    part = d["candidates"][0]["content"]["parts"][0]
    inline = part.get("inlineData") or part.get("inline_data")
    import base64

    pcm = base64.b64decode(inline["data"])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for bid, key, text in BLOCKS:
        wav = OUT / f"{bid}.wav"
        if not wav.exists():
            synth(text, wav)
        dur = float(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                text=True,
            ).strip()
        )
        meta.append({"id": bid, "cmd_key": key, "text": text, "file": str(wav), "dur": round(dur, 2)})
        print(f"{bid}: {dur:5.1f}s  {len(text.split()):3d} words")
    total = sum(m["dur"] for m in meta)
    print(f"narration total: {total:.1f}s (+pauses)")
    Path("/tmp/demo/narration.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
