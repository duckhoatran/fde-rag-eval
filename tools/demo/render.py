#!/usr/bin/env python3
"""Render the demo video: real captured terminal output + Gemini narration + burned-in captions.

No invented content: every line of output comes from /tmp/demo/capture.json, which was produced by
actually running the commands in DEMO.md.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900
FPS = 12
BG = (13, 17, 23)
WIN = (22, 27, 34)
BORDER = (48, 54, 61)
TEXT = (201, 209, 217)
DIM = (139, 148, 158)
GREEN = (126, 231, 135)
RED = (255, 123, 114)
BLUE = (121, 192, 255)
PROMPT = (110, 231, 183)
CAP_BG = (0, 0, 0)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
BODY = ImageFont.truetype(FONT_PATH, 21)
BODY_B = ImageFont.truetype(FONT_BOLD, 21)
TITLE = ImageFont.truetype(FONT_PATH, 17)
CAP = ImageFont.truetype(FONT_PATH, 25)
BIG = ImageFont.truetype(FONT_BOLD, 46)
SUB = ImageFont.truetype(FONT_PATH, 24)

CHAR_W = BODY.getlength("M")
MAX_CHARS = int((W - 160) / CHAR_W)
MAX_LINES = 16
BODY_TOP = 132
LINE_H = 32
CAP_CHARS = int((W - 120) / CAP.getlength("M"))
TYPING_CPS = 30.0
TAIL = 0.8

FILES = ["capture.json", "narration.json"]
CAPTURE = json.loads(Path("/tmp/demo/capture.json").read_text())
NARR = json.loads(Path("/tmp/demo/narration.json").read_text())

TITLES = {
    "tree": "eval set + repo layout",
    "eval": "python3 run_eval.py  # retrieval only, no LLM calls",
    "guarded": "python3 answer.py  # guarded arm",
    "naive": "python3 answer.py --naive  # same retrieval, no guardrail",
    "metrics": "reports/w47-guardrails.md",
    "git": "git log",
}


def wrap(text: str, width: int = MAX_CHARS) -> list[str]:
    out = []
    for raw in text.splitlines():
        raw = raw.replace("**", "").replace("`", "")
        if not raw.strip():
            out.append("")
            continue
        cur, first = raw, True
        while True:
            ind = "" if first else "  "          # continuation lines carry an indent —
            avail = width - len(ind)             # count it, or the line overruns the window
            if len(cur) <= avail:
                out.append(ind + cur)
                break
            cut = cur.rfind(" ", 0, avail)
            cut = cut if cut > avail * 0.5 else avail
            out.append(ind + cur[:cut])
            cur = cur[cut:].lstrip()
            first = False
    return out


def line_color(line: str) -> tuple[int, int, int]:
    low = line.lower()
    if "insufficient evidence" in low:
        return GREEN
    if "17.5 million" in low or "£17.5" in low:
        return RED
    if re.match(r"^[0-9a-f]{7} ", line):
        return BLUE
    if low.startswith("bm25 miss") or low.startswith("dense miss") or low.startswith("hybrid miss"):
        return DIM
    return TEXT


def draw_frame(cmd: str, typed: int, lines: list[str], caption: str, idx: int, total: int, title_card: bool = False) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    if title_card:
        d.text((90, 330), "fde-rag-eval — Phase 1", font=BIG, fill=(240, 246, 252))
        d.text((90, 400), "a compliance RAG assistant whose refusals are measured", font=SUB, fill=DIM)
        d.text((90, 470), "github.com/duckhoatran/fde-rag-eval", font=SUB, fill=BLUE)
        return img

    d.rounded_rectangle([40, 40, W - 40, H - 170], radius=12, fill=WIN, outline=BORDER, width=2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([64 + i * 26, 58, 76 + i * 26, 70], fill=c)
    d.text((160, 54), "khoa@fde-lab : ~/fde-lab/rag-eval", font=TITLE, fill=DIM)
    tag = f"{idx}/{total}"
    d.text((W - 140, 54), tag, font=TITLE, fill=DIM)
    d.line([40, 86, W - 40, 86], fill=BORDER, width=1)

    y = BODY_TOP
    d.text((70, y), "$", font=BODY_B, fill=PROMPT)
    d.text((70 + CHAR_W * 2, y), cmd[:typed], font=BODY, fill=(230, 237, 243))
    y += LINE_H + 8

    shown = lines[-MAX_LINES:]
    for line in shown:
        if line:
            d.text((70, y), line, font=BODY, fill=line_color(line))
        y += LINE_H

    if caption:
        cap_lines = wrap(caption, CAP_CHARS)[:2]
        box_h = 20 + (LINE_H + 6) * len(cap_lines)
        d.rectangle([0, H - box_h - 14, W, H - 14], fill=(0, 0, 0))
        cy = H - box_h - 4
        for cl in cap_lines:
            w = CAP.getlength(cl)
            d.text(((W - w) / 2, cy), cl, font=CAP, fill=(245, 245, 245))
            cy += LINE_H + 6
    return img


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def build() -> tuple[list[tuple[Path, float]], float, list[tuple[float, float, Path]]]:
    frames_dir = Path("/tmp/demo/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("*.png"):
        f.unlink()

    timeline: list[tuple[Path, float]] = []
    audio_events: list[tuple[float, float, Path]] = []
    t = 0.0
    total = len(NARR)

    # title card
    tc = draw_frame("", 0, [], "", 0, total, title_card=True)
    p = frames_dir / "f000000.png"
    tc.save(p)
    timeline.append((p, 2.2))
    t += 2.2

    n = 0
    for i, blk in enumerate(NARR, 1):
        cap = CAPTURE[blk["cmd_key"]]
        cmd = cap["cmd"]
        out_lines = wrap(cap["out"])
        seg = blk["dur"] + TAIL

        sents = sentences(blk["text"])
        weights = [max(len(s), 24) for s in sents]
        tot_w = sum(weights)
        cap_start = t
        cap_sched = []
        acc = 0.0
        for s, wgt in zip(sents, weights):
            st = cap_start + seg * acc / tot_w
            acc += wgt
            cap_sched.append((st, s))

        def cap_at(tt: float) -> str:
            cur = ""
            for st, s in cap_sched:
                if tt + 1e-6 >= st:
                    cur = s
            return cur

        # typing
        type_dur = min(len(cmd) / TYPING_CPS, seg * 0.45)
        n_chars = len(cmd)
        for i_char in range(0, n_chars + 1):
            ft = t + type_dur * i_char / max(n_chars, 1)
            n += 1
            img = draw_frame(cmd, i_char, [], cap_at(ft), i, total)
            p = frames_dir / f"f{n:06d}.png"
            img.save(p)
            timeline.append((p, type_dur / max(n_chars, 1) if i_char < n_chars else 0.0))

        # output lines reveal
        reveal_dur = max(seg * 0.45, 0.35 * len(out_lines))
        reveal_dur = min(reveal_dur, seg - type_dur - 0.2)
        steps = max(len(out_lines), 1)
        for k in range(1, steps + 1):
            ft = t + type_dur + reveal_dur * k / steps
            n += 1
            img = draw_frame(cmd, n_chars, out_lines[:k], cap_at(ft), i, total)
            p = frames_dir / f"f{n:06d}.png"
            img.save(p)
            timeline.append((p, reveal_dur / steps if k < steps else 0.0))

        # hold the final frame until the segment ends
        remain = seg - (type_dur + reveal_dur)
        if remain > 0.05:
            n += 1
            img = draw_frame(cmd, n_chars, out_lines, cap_at(t + seg - 0.01), i, total)
            p = frames_dir / f"f{n:06d}.png"
            img.save(p)
            timeline.append((p, remain))

        audio_events.append((t, seg, Path(blk["file"])))
        t += seg

    # zero-duration trailing entries break the concat demuxer — drop them
    timeline = [(p, max(d, 1 / (FPS * 2))) for p, d in timeline]
    return timeline, t, audio_events


def main() -> int:
    timeline, total, audio_events = build()
    print(f"frames: {len(timeline)}  video: {total:.1f}s")

    concat = Path("/tmp/demo/frames.txt")
    with concat.open("w") as fh:
        for p, d in timeline:
            fh.write(f"file '{p}'\nduration {d:.4f}\n")
        fh.write(f"file '{timeline[-1][0]}'\n")

    # audio: silence bed + each narration placed at its block start
    inputs, filt, labels = [], [], []
    inputs += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=24000:cl=mono"]
    # input 0 = frame sequence, input 1 = silence bed, inputs 2.. = narration wavs
    for i, (start, dur, path) in enumerate(audio_events, 2):
        inputs += ["-i", str(path)]
        ms = int(start * 1000)
        filt.append(f"[{i}:a]aresample=24000,adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    mix = "".join(labels) + f"[1:a]amix=inputs={len(labels) + 1}:normalize=0[mixed]"
    filt.append(mix)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        *inputs,
        "-filter_complex", ";".join(filt),
        "-map", "0:v", "-map", "[mixed]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "24000",
        "-t", f"{total:.2f}",
        "-movflags", "+faststart",
        "/tmp/demo/w47-demo.mp4",
    ]
    print("encoding…")
    subprocess.run(cmd, check=True)
    out = Path("/tmp/demo/w47-demo.mp4")
    print("ok", out, f"{out.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
