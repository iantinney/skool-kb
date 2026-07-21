#!/usr/bin/env python3
"""
srt2txt.py — Convert .srt/.vtt caption files into clean, deduplicated plain text.

YouTube auto-captions use a rolling window, so a raw .srt repeats most lines 2-3x
and is littered with timestamps. For a grep/read knowledge base we want flat prose.
This strips cue numbers, timestamps, and tags, then collapses the rolling-window
duplication into readable paragraphs.

For each kb/transcripts/NAME.en.srt (or .vtt) it writes kb/transcripts/NAME.txt and
removes the caption file. Idempotent and safe to re-run.
"""
import re
import sys
from pathlib import Path

TS = re.compile(r"\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*")
TAG = re.compile(r"<[^>]+>")           # <c>, <00:00:00.000> inline timing tags
CUENUM = re.compile(r"^\d+$")


def clean(path: Path) -> str:
    words: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or TS.search(line) or CUENUM.match(line):
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        line = TAG.sub("", line).strip()
        if not line:
            continue
        # Rolling-window de-dup: skip if these words are already the tail of output.
        new = line.split()
        # find largest overlap between end of `words` and start of `new`
        max_ov = min(len(words), len(new))
        ov = 0
        for k in range(max_ov, 0, -1):
            if words[-k:] == new[:k]:
                ov = k
                break
        words.extend(new[ov:])
    text = " ".join(words)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def base_name(path: Path) -> str:
    # strip .en / .en-orig / language suffix before the extension
    stem = path.name
    for ext in (".srt", ".vtt"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    stem = re.sub(r"\.[A-Za-z]{2}(-[A-Za-z]+)?(-orig)?$", "", stem)
    return stem


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "kb/transcripts")
    caps = list(out_dir.glob("*.srt")) + list(out_dir.glob("*.vtt"))
    n = 0
    for cap in caps:
        txt = clean(cap)
        if len(txt) < 20:
            continue
        (out_dir / f"{base_name(cap)}.txt").write_text(txt + "\n", encoding="utf-8")
        cap.unlink()
        n += 1
    print(f"cleaned {n} caption file(s) -> plain .txt in {out_dir}/")


if __name__ == "__main__":
    main()
