#!/usr/bin/env bash
# add_native.sh — add ONE native Skool-hosted video to your knowledge base.
#
# Native Skool videos are Mux HLS streams behind short-lived signed tokens, so
# they can't be auto-downloaded. You capture the stream URL from your browser
# once (DevTools), and this script does the rest: download -> extract audio ->
# transcribe -> drop the transcript into kb/transcripts/.
#
#   ./add_native.sh "<m3u8 URL>" "Video Title" [video_id]
#
# How to get the <m3u8 URL>:
#   1. Play the lesson/post video in your browser.
#   2. DevTools (F12) -> Network tab -> filter "m3u8".
#   3. Copy the request URL (…/….m3u8?token=…). Tokens expire fast — do this
#      right before running the command.
#
# The optional [video_id] is the id shown in kb/MISSING_VIDEOS.md; passing it
# lets report_missing.py mark this video as done on the next refresh.
set -euo pipefail
cd "$(dirname "$0")"

URL="${1:-}"
TITLE="${2:-native video}"
VIDEO_ID="${3:-}"

[ -n "$URL" ] || { echo "usage: ./add_native.sh \"<m3u8 URL>\" \"Video Title\" [video_id]"; exit 1; }
case "$URL" in
  http://*|https://*) : ;;
  *) echo "!! Expected an http(s) URL — the .m3u8 stream captured from DevTools > Network."; exit 1 ;;
esac
printf '%s' "$URL" | grep -qi 'm3u8' || \
  echo "!! Heads up: that URL doesn't contain 'm3u8'. Skool HLS URLs normally do — trying anyway."

[ -d .venv ] && source .venv/bin/activate
[ -f .env ] && set -a && source .env && set +a
[ -d "$HOME/.deno/bin" ] && export PATH="$HOME/.deno/bin:$PATH"
command -v ffmpeg >/dev/null || { echo "!! ffmpeg is required (brew install ffmpeg / apt install ffmpeg)."; exit 1; }

mkdir -p audio kb/transcripts
# Sanitize the title for a filename; append [video_id] so it's traceable + de-dupeable.
safe=$(printf '%s' "$TITLE" | tr '/' '_' | tr -cd '[:alnum:] ._-' | cut -c1-120)
tag="${VIDEO_ID:-native}"
base="$safe [$tag]"

echo "== Downloading native video: $TITLE =="
# Skool's CDN requires the Skool referer. Grab audio only (smaller/faster for Whisper).
if ! yt-dlp --referer "https://www.skool.com/" \
      -f "ba/worst" -x --audio-format m4a --audio-quality 48k \
      -o "audio/${base}.%(ext)s" "$URL"; then
  echo
  echo "!! Download failed. The token has probably expired (they last only minutes)."
  echo "   Re-capture a fresh .m3u8 URL from DevTools and run this again immediately."
  exit 1
fi

echo "== Transcribing =="
python3 transcribe.py --audio audio --out kb/transcripts

echo "== Refreshing reports =="
python3 report_missing.py kb || true
python3 build_index.py kb || true

echo
echo "✅ Added '$TITLE' to the knowledge base."
echo "   Transcript: kb/transcripts/${base}.txt"
