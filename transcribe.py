#!/usr/bin/env python3
"""
transcribe.py — Turn downloaded audio into text transcripts for the KB.

Linux-friendly replacement for mlx-whisper (which is Apple-Silicon only).

Two backends, auto-selected:
  * Groq API  — used automatically if GROQ_API_KEY is set. ~100x realtime,
                ~$0.04/audio-hour, whisper-large-v3-turbo. Files >24MB are split
                with ffmpeg into ~15-min chunks and stitched back together.
  * faster-whisper (CPU) — the default when no key is set. No GPU here, so keep
                the model small. WHISPER_MODEL env overrides (tiny|base|small|
                medium). Default: "small" (good accuracy, ~1-2x realtime on 4 CPUs).

Skips any audio file that already has a transcript, so it is Ctrl-C / resume safe.

Usage:
  python3 transcribe.py                 # audio/  -> kb/transcripts/
  python3 transcribe.py --audio audio --out kb/transcripts
  WHISPER_MODEL=base python3 transcribe.py
  GROQ_API_KEY=gsk_... python3 transcribe.py
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from video_utils import has_text_content, has_transcript_text

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".webm", ".opus", ".ogg", ".mp4", ".mkv"}
GROQ_MAX_BYTES = 24 * 1024 * 1024  # stay under Groq's 25MB request cap


def find_audio(audio_dir: Path):
    return sorted(p for p in audio_dir.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def already_done(out_dir: Path, stem: str) -> bool:
    # A caption grab (.srt/.vtt) or a prior run (.txt) both count as "done".
    return any((path.stem == stem or path.stem.startswith(stem + "."))
               and has_transcript_text(path) for path in out_dir.iterdir())


def duration_seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


# ---------- Groq backend ----------

def groq_transcribe_file(path: Path, api_key: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    with path.open("rb") as f:
        resp = client.audio.transcriptions.create(
            file=(path.name, f.read()),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
    return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))


def groq_transcribe(path: Path, api_key: str) -> str:
    if path.stat().st_size <= GROQ_MAX_BYTES:
        return groq_transcribe_file(path, api_key)
    # Too big: split into 15-minute mono 16kHz chunks and stitch.
    print(f"    splitting {path.name} (>{GROQ_MAX_BYTES // (1024*1024)}MB) for Groq...")
    with tempfile.TemporaryDirectory() as td:
        pattern = os.path.join(td, "chunk_%03d.m4a")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
             "-f", "segment", "-segment_time", "900", "-ac", "1", "-ar", "16000",
             "-c:a", "aac", "-b:a", "48k", pattern],
            check=True)
        parts = sorted(Path(td).glob("chunk_*.m4a"))
        texts = []
        for i, chunk in enumerate(parts):
            print(f"    chunk {i + 1}/{len(parts)}")
            texts.append(groq_transcribe_file(chunk, api_key))
        return "\n".join(texts)


# ---------- faster-whisper backend ----------

_FW_MODEL = None


def fw_transcribe(path: Path, model_name: str) -> str:
    global _FW_MODEL
    if _FW_MODEL is None:
        from faster_whisper import WhisperModel
        print(f"    loading faster-whisper '{model_name}' (int8, CPU)...")
        _FW_MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = _FW_MODEL.transcribe(str(path), vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default="audio", help="Input audio dir (default: audio)")
    ap.add_argument("--out", default="kb/transcripts", help="Output dir (default: kb/transcripts)")
    args = ap.parse_args()

    audio_dir = Path(args.audio)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not audio_dir.is_dir():
        print(f"No audio dir '{audio_dir}'. Nothing to transcribe (captions may already cover it).")
        return

    files = find_audio(audio_dir)
    if not files:
        print(f"No audio files in '{audio_dir}'.")
        return

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model_name = os.environ.get("WHISPER_MODEL", "small").strip()
    backend = "Groq API (whisper-large-v3-turbo)" if api_key else f"faster-whisper '{model_name}' (CPU)"
    print(f"Backend: {backend}")
    print(f"{len(files)} audio file(s) found.\n")

    done = skipped = failed = 0
    for path in files:
        stem = path.stem
        if already_done(out_dir, stem):
            skipped += 1
            continue
        mins = duration_seconds(path) / 60
        print(f"[{done + failed + 1}] {path.name}  (~{mins:.0f} min)")
        try:
            text = (groq_transcribe(path, api_key) if api_key
                    else fw_transcribe(path, model_name))
            if not has_text_content(text):
                raise ValueError("Transcription returned no readable text; audio retained for retry")
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            failed += 1
            continue
        (out_dir / f"{stem}.txt").write_text(text.strip() + "\n", encoding="utf-8")
        done += 1

    print(f"\nDone. {done} transcribed, {skipped} skipped (already had text/captions), {failed} failed.")
    print(f"Transcripts in {out_dir}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
