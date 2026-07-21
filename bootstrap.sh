#!/usr/bin/env bash
# bootstrap.sh — one-command setup. Creates a venv, installs Python deps, checks
# for ffmpeg, and installs Deno (the JS runtime yt-dlp needs for YouTube).
#
#   ./bootstrap.sh
#
# Safe to re-run; it skips anything already present.
set -euo pipefail
cd "$(dirname "$0")"

echo "== skool-kb bootstrap =="

# 1. Python
command -v python3 >/dev/null || { echo "!! python3 not found. Install Python 3.10+ first."; exit 1; }
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "-> python $PYV"

# 2. venv + deps
if [ ! -d .venv ]; then
  echo "-> creating .venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
echo "-> installing Python dependencies"
pip install -r requirements.txt

# 3. ffmpeg (needed to extract/convert audio for transcription)
if command -v ffmpeg >/dev/null; then
  echo "-> ffmpeg present"
else
  echo "!! ffmpeg NOT found — needed for audio transcription."
  echo "   macOS:  brew install ffmpeg"
  echo "   Ubuntu: sudo apt-get install -y ffmpeg"
  echo "   (You can still scrape posts + download captions without it.)"
fi

# 4. Deno (JS runtime for yt-dlp's YouTube extractor)
if command -v deno >/dev/null || [ -x "$HOME/.deno/bin/deno" ]; then
  echo "-> deno present"
else
  echo "-> installing Deno (JS runtime for yt-dlp)"
  curl -fsSL https://deno.land/install.sh | sh -s -- -y || {
    echo "!! Deno install failed. YouTube caption grab still works; audio download of"
    echo "   caption-less YouTube videos may not. Install manually: https://deno.land"
  }
fi

# 5. Config files
[ -f communities.txt ] || { cp communities.example.txt communities.txt; echo "-> created communities.txt (edit it: add your Skool community URLs)"; }
[ -f .env ] || { cp .env.example .env; echo "-> created .env (optional: add GROQ_API_KEY for fast transcription)"; }

echo
echo "== Bootstrap complete =="
echo "Next:"
echo "  1. Edit communities.txt   -> add the Skool communities you're a member of"
echo "  2. Add cookies.txt        -> see docs/COOKIES.md"
echo "  3. (optional) put GROQ_API_KEY in .env for fast transcription"
echo "  4. ./run.sh               -> build the knowledge base"
echo "  5. cd kb && claude        -> ask questions"
