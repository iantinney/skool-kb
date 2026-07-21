#!/usr/bin/env bash
# run.sh — end-to-end Skool -> knowledge base pipeline.
#
#   ./run.sh                 # full pipeline: scrape -> captions -> audio -> transcribe -> clean
#   ./run.sh scrape          # just the Skool text + video-URL scrape
#   ./run.sh captions        # just grab free YouTube/Vimeo captions
#   ./run.sh audio           # just download audio for videos without captions
#   ./run.sh transcribe      # just Whisper the downloaded audio -> text
#   ./run.sh clean           # dedupe/clean captions into plain text
#
# Config:
#   communities.txt   one Skool community root URL per line (see communities.example.txt)
#   cookies.txt       exported browser cookies (see docs/COOKIES.md)
#   .env              optional: GROQ_API_KEY=... for fast cloud transcription
#
# Everything is resumable: re-running skips already-downloaded audio and
# existing transcripts.
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv
COOKIES=cookies.txt
COMMUNITIES=communities.txt
PAGES=${PAGES:-30}

[ -d "$VENV" ] && source "$VENV/bin/activate"
[ -f .env ] && set -a && source .env && set +a          # GROQ_API_KEY, etc.
# Put a local Deno (installed by bootstrap.sh) on PATH for yt-dlp's YouTube extractor.
[ -d "$HOME/.deno/bin" ] && export PATH="$HOME/.deno/bin:$PATH"

die() { echo "!! $*" >&2; exit 1; }

# Build the crawl URL list from communities.txt: each root plus its /classroom.
load_urls() {
  [ -s "$COMMUNITIES" ] || die "Missing $COMMUNITIES — copy communities.example.txt to communities.txt and add your community URLs."
  SKOOL_URLS=()   # NB: never name this GROUPS — that is a reserved bash builtin (user's GIDs).
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(echo "$line" | xargs)"   # strip comments + whitespace
    [ -z "$line" ] && continue
    line="${line%/}"
    SKOOL_URLS+=("$line" "$line/classroom")
  done < "$COMMUNITIES"
  [ "${#SKOOL_URLS[@]}" -gt 0 ] || die "No community URLs found in $COMMUNITIES."
}

need_cookies() {
  [ -s "$COOKIES" ] || die "Missing $COOKIES — see docs/COOKIES.md (export with the 'Get cookies.txt LOCALLY' browser extension)."
}

do_scrape() {
  need_cookies; load_urls
  echo "== Scraping Skool posts + collecting video URLs =="
  python3 skool_dump.py --cookies "$COOKIES" --out kb --pages "$PAGES" "${SKOOL_URLS[@]}"
}

do_captions() {
  [ -s video_urls.txt ] || { echo "(no video_urls.txt yet — run './run.sh scrape' first)"; return; }
  need_cookies
  echo "== Pass A: grabbing free captions (no transcription needed) =="
  # --ignore-no-formats-error: YouTube forces SABR streaming (no plain media
  # formats), which would otherwise abort the video before the subtitle is written.
  yt-dlp --cookies "$COOKIES" --skip-download --ignore-no-formats-error \
    --sleep-requests 1 --extractor-retries 3 --ignore-errors \
    --write-subs --write-auto-subs --sub-langs "en.*" --convert-subs srt \
    -o "kb/transcripts/%(title).120B [%(id)s]" -a video_urls.txt || true
  # Drop the redundant en-orig track when a plain en track exists.
  for f in kb/transcripts/*.en-orig.srt; do
    [ -e "$f" ] || continue
    [ -e "${f%.en-orig.srt}.en.srt" ] && rm -f "$f"
  done
}

do_audio() {
  [ -s video_urls.txt ] || { echo "(no video_urls.txt yet — run './run.sh scrape' first)"; return; }
  need_cookies
  echo "== Pass B: downloading audio for anything without captions =="
  # Only fetch audio for videos that did NOT already get a caption file. Derive
  # the video id from the URL locally (no extra network probes) and skip it if a
  # transcript file already carries that id in its "[id]" suffix.
  local need; need="$(mktemp)"
  while read -r url; do
    case "$url" in \#*|"") continue;; esac
    id=$(printf '%s\n' "$url" | grep -oE '[A-Za-z0-9_-]{11}$|[A-Za-z0-9_-]{11}(&|$)|/[0-9]+$|[A-Za-z0-9]+$' | head -1 | tr -d '/&')
    if [ -n "$id" ] && ls kb/transcripts/*"$id"* >/dev/null 2>&1; then continue; fi
    echo "$url" >> "$need"
  done < video_urls.txt
  n=$(grep -c . "$need" || true)
  echo "   ${n:-0} video(s) lack captions -> downloading audio"
  if [ "${n:-0}" -gt 0 ]; then
    # --remote-components ejs:github: fetch yt-dlp's JS challenge solver so YouTube
    # SABR-forced formats become downloadable (Deno runs it).
    yt-dlp --cookies "$COOKIES" --referer "https://www.skool.com/" \
      --remote-components ejs:github --ignore-no-formats-error \
      --sleep-requests 1 --min-sleep-interval 1 --max-sleep-interval 4 \
      --extractor-retries 3 --ignore-errors \
      -f "ba/worst" -x --audio-format m4a --audio-quality 48k \
      --download-archive done.txt \
      -o "audio/%(title).120B [%(id)s].%(ext)s" -a "$need" || true
  fi
  rm -f "$need"
}

do_transcribe() {
  echo "== Pass C: transcribing audio -> text =="
  python3 transcribe.py --audio audio --out kb/transcripts
}

do_clean() {
  echo "== Cleaning captions -> deduplicated plain text =="
  python3 srt2txt.py kb/transcripts
}

do_index() {
  echo "== Building kb/INDEX.md =="
  python3 build_index.py kb
}

case "${1:-all}" in
  scrape)     do_scrape ;;
  captions)   do_captions ;;
  audio)      do_audio ;;
  transcribe) do_transcribe ;;
  clean)      do_clean ;;
  index)      do_index ;;
  all)        do_scrape; do_captions; do_audio; do_transcribe; do_clean; do_index
              echo; echo "== Pipeline complete =="
              echo "Posts:       $(find kb/posts -type f ! -name .gitkeep 2>/dev/null | wc -l) files"
              echo "Transcripts: $(find kb/transcripts -type f ! -name .gitkeep 2>/dev/null | wc -l) files"
              echo "Query it:    cd kb && claude   (or: codex)" ;;
  *) echo "usage: $0 [all|scrape|captions|audio|transcribe|clean|index]"; exit 1 ;;
esac
