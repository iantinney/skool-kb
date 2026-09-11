# Manual Runbook

Step-by-step setup for doing this by hand (no agent). Budget ~15 minutes of attention,
then unattended download + transcription. Works on macOS and Linux. (Windows: use WSL.)

> **Run this on your own computer if you can.** YouTube bot-checks datacenter/VPS IPs, so a
> home machine (residential IP) gives the most reliable video downloads.

---

## 0. Prerequisites

- **Python 3.10+** — `python3 --version`
- **git** — `git --version`
- **ffmpeg** (for transcription) — macOS `brew install ffmpeg`, Ubuntu `sudo apt install ffmpeg`
- Membership in the Skool communities you want to include (you must be logged in).

---

## 1. Clone + bootstrap

```bash
git clone https://github.com/iantinney/skool-kb.git
cd skool-kb
./bootstrap.sh
```

`bootstrap.sh` creates a virtualenv, installs Python deps, checks ffmpeg, installs **Deno**
(the JS runtime yt-dlp needs for YouTube), and creates `communities.txt` + `.env` from the
examples.

---

## 2. List your communities

Edit **`communities.txt`** — one community root URL per line:

```
https://www.skool.com/your-community
https://www.skool.com/another-community
```

(The pipeline automatically also crawls each community's `/classroom` section.)

---

## 3. Cookies

Full detail in **[COOKIES.md](COOKIES.md)**. Short version:

1. Install the **"Get cookies.txt LOCALLY"** browser extension (Chrome/Edge/Brave) — *not*
   the older "Get cookies.txt" without LOCALLY. (Firefox: the **"cookies.txt"** add-on.)
2. Visit **skool.com** logged in → extension → **Export** → save as `cookies.txt` here.
3. Recommended: also export **youtube.com** cookies (from an incognito window you then close
   without logging out) and append them to the same `cookies.txt`.

Verify the session works:
```bash
.venv/bin/python - <<'PY'
from skool_dump import load_session
r = load_session("cookies.txt").get("https://www.skool.com", timeout=30)
print("HTTP", r.status_code, "| __NEXT_DATA__ present:", "__NEXT_DATA__" in r.text)
PY
```
Expect `HTTP 200` and `__NEXT_DATA__ present: True`.

---

## 4. (Optional) Transcription key

For fast cloud transcription, get a free key at **https://console.groq.com/keys** and add it
to `.env`:
```
GROQ_API_KEY=gsk_your_key_here
```
Skip this to use local CPU transcription (`faster-whisper`). See [TRANSCRIPTION.md](TRANSCRIPTION.md).

---

## 5. Run the pipeline

All at once:
```bash
./run.sh
```

Or one pass at a time (useful to watch progress / debug):
```bash
./run.sh scrape        # posts + lessons + comments -> kb/posts/*.md ; video URLs -> video_urls.txt
./run.sh captions      # free YouTube/Vimeo captions -> kb/transcripts/*.srt
./run.sh audio         # download audio ONLY for caption-less videos -> audio/
./run.sh transcribe    # Whisper the audio -> kb/transcripts/*.txt
./run.sh clean         # dedupe/clean all captions -> kb/transcripts/*.txt
./run.sh index         # build kb/INDEX.md
./run.sh report        # build kb/VIDEO_REPORT.md + kb/MISSING_VIDEOS.md
```

**Review what was captured.** `kb/VIDEO_REPORT.md` is the full ledger: how many videos
made it into the KB vs not, broken down by community, source (feed post / classroom lesson),
and provider (YouTube / Loom / Vimeo / native Skool), plus an explicit list of everything
missing. **Native Skool-hosted videos** need a separate import in this pipeline; they're
listed in `kb/MISSING_VIDEOS.md` and you can add any in ~1 minute with `./add_native.sh` — see
[NATIVE_VIDEOS.md](NATIVE_VIDEOS.md).

Inspect `kb/CRAWL_REPORT.json` after scraping. Failed requests or a reached fetch cap return nonzero; the prior video catalogue is retained with `seen_in_latest_crawl=false` for historical entries. Counts are limited to discovered videos. The default pipeline saves text and audio, not full playable videos; compare the lesson inventory and media backup with Skool before cancelling access.

**What to expect:**
- `scrape` prints a running count of pages, videos, and native videos found.
- `captions` covers the large majority of YouTube/Vimeo with zero transcription.
- `audio` + `transcribe` handle the rest. Native Skool videos are **not** downloaded here —
  see [NATIVE_VIDEOS.md](NATIVE_VIDEOS.md).

Everything is **resumable**: `--download-archive` skips downloaded audio, and transcription
skips files that already have a transcript or caption. Re-run weekly to pick up new content
in minutes.

---

## 6. Query it

```bash
cd kb
claude        # or: codex   — then just ask
```

Example: *"Has anyone explained how to get approved for TikTok Shop affiliate? Cite sources."*
The agent reads `INDEX.md`, greps `posts/` + `transcripts/`, and answers with filenames that
point back to the original video/post.

No agent handy? It's just text — `grep -ri "your topic" kb/` works too.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no __NEXT_DATA__ (login wall?)` | Cookies missing/stale → re-export `cookies.txt`. |
| `Sign in to confirm you're not a bot` | Add fresh youtube.com cookies; run on a home machine; heavy cases: [bgutil PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) (not guaranteed). |
| `Only images are available` (YouTube) | Deno missing → re-run `./bootstrap.sh`. |
| Transcription very slow | Add `GROQ_API_KEY`, or set `WHISPER_MODEL=base` in `.env`. |
| A few Loom/Vimeo failures | Normal (auth/impersonation). |
| Native Skool videos missing | Expected → listed in `kb/MISSING_VIDEOS.md`; add with `./add_native.sh` ([NATIVE_VIDEOS.md](NATIVE_VIDEOS.md)). |

---

## What lands where

```
skool-kb/
├── communities.txt        # your input: which communities
├── cookies.txt            # your input: session (gitignored)
├── .env                   # your input: optional GROQ_API_KEY (gitignored)
├── video_urls.txt         # external video links found (gitignored)
├── videos.tsv            # discovered video catalogue (gitignored)
├── audio/                 # downloaded audio, pre-transcription (gitignored)
└── kb/                    # ← the knowledge base you query
    ├── posts/*.md         #    post/lesson/comment text
    ├── transcripts/*.txt  #    clean video transcripts
    ├── INDEX.md           #    one-line-per-file map
    ├── CRAWL_REPORT.json  #    failed/pending pages and crawl limits
    ├── VIDEO_REPORT.md    #    full video accounting (in KB vs missing, by source)
    ├── MISSING_VIDEOS.md  #    native videos NOT in the KB (+ how to add them)
    └── CLAUDE.md          #    how an agent should answer questions here
```
