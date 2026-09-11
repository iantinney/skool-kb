# skool-kb

**Turn the Skool communities you're a member of into a local, searchable knowledge base you can ask questions — instead of scrolling feeds and watching hours of video.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Agent-ready](https://img.shields.io/badge/agent-ready-8A2BE2.svg)](AGENTS.md)

It scrapes text from the community pages it reaches, attempts captions or transcription for discovered external videos, and stores a plain-text knowledge base. Native videos currently need a separate import. Then you point an AI coding agent (Claude Code, Codex, Cursor, …) at that folder and ask real questions:

> *"Has anyone covered TikTok Shop affiliate approval timelines?"*
> → searches the transcripts + posts, reads the hits, and answers **with the source filenames** so you can go straight to the original video or post.

**Deliberately boring by design:** no vector database, no embeddings, no RAG pipeline. Even 50+ hours of video is only a few MB of text — an agent greps and reads its way to answers faster than you could build a retrieval stack.

---

## The easiest way to use this: just ask your agent

You don't have to read this README. Clone the repo and paste this to **Claude Code** or **Codex** inside it:

```
Read AGENTS.md and set this project up with me. Ask me for whatever you need.
```

The agent will walk you through everything — which cookies to export and how, whether to add a Groq key, and then it runs the pipeline for you. That's what [`AGENTS.md`](AGENTS.md) is for: a script for the agent so onboarding is a conversation, not a manual.

Prefer to do it by hand? See the [Manual quickstart](#manual-quickstart) and the full [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## What it can and cannot do

### ✅ It can
- Scrape **post / lesson / comment text** from communities you're logged into, to markdown.
- Collect discovered video links (YouTube, Loom, Vimeo, Wistia, and native Skool).
- Grab **free captions** for YouTube/Vimeo videos (no transcription cost or time).
- **Transcribe** the rest via [Groq Whisper](https://console.groq.com/docs/speech-to-text) (fast, ~$0.04/audio-hour) or **local `faster-whisper`** on CPU (free, slower).
- Produce a clean, de-duplicated, **plain-text knowledge base** + an `INDEX.md` map.
- **Account for discovered videos** — `kb/VIDEO_REPORT.md` shows readable transcripts vs missing text, broken down by community, source, and provider. `kb/CRAWL_REPORT.json` records failed requests, pending pages, inaccessible modules, and crawl limits. Native videos needing import appear in `kb/MISSING_VIDEOS.md`.
- Re-run incrementally: already-downloaded audio and existing transcripts are skipped.

### ❌ It cannot (be honest with yourself)
- **Access content you're not a member of.** It uses *your* logged-in session. It is not a way around paywalls or private communities you haven't joined.
- **Auto-download native Skool-hosted videos in this pipeline.** Discovered native videos appear in **`kb/MISSING_VIDEOS.md`**; **`./add_native.sh`** accepts an authorized stream URL. See [docs/NATIVE_VIDEOS.md](docs/NATIVE_VIDEOS.md).
- **Prove a complete account backup.** It does not discover all your memberships. Feed pagination is bounded; comments and other lazy-loaded content may be absent. Review failed/pending pages and compare the lesson inventory against Skool before cancelling access.
- **Archive playable videos.** The default pipeline saves captions and/or audio for a text KB, not full video files. A transcript can omit on-screen demonstrations and attachments; keep a separate media backup if you need those.
- **Guarantee YouTube downloads from a cloud server / VPS.** As of 2026, YouTube aggressively bot-checks datacenter IPs ("Sign in to confirm you're not a bot"). Logged-in cookies help but are **not a guaranteed bypass**. **Run this on your own computer (residential IP) for best results.** See [Troubleshooting](#troubleshooting).
- **Bypass Skool's Terms.** This is for personal use of content you legitimately have access to. See [Legal & ethics](#legal--ethics).

---

## How it works

```
communities.txt ─┐
                 │   skool_dump.py            yt-dlp                 transcribe.py         srt2txt.py
cookies.txt ─────┼─▶ scrape __NEXT_DATA__ ─▶ captions + audio ─▶  Whisper (Groq/CPU) ─▶  clean text ─▶ kb/
                 │   posts + video URLs        (free subs first)     (only caption-less)   dedupe
.env (Groq) ─────┘
                                                                                          kb/ ─▶ cd kb && claude
```

`skool_dump.py` reads the `__NEXT_DATA__` JSON served with a page. Classroom discovery follows course paths and accessible lesson ids; lesson text includes Skool's `[v2]` rich-text descriptions. Other text is collected recursively. Pages do not necessarily contain every comment or lesson, so a successful HTTP request alone does not establish completeness. Output includes `kb/posts/*.md`, `video_urls.txt`, and `videos.tsv`.

`run.sh` orchestrates the passes: **scrape → captions → audio → transcribe → clean → index → report**. Each is also runnable on its own (`./run.sh <step>`).

---

## Manual quickstart

**Prerequisites:** Python 3.10+, `git`, and `ffmpeg` (for transcription). macOS: `brew install ffmpeg`. Ubuntu: `sudo apt install ffmpeg`.

```bash
git clone https://github.com/iantinney/skool-kb.git
cd skool-kb
./bootstrap.sh                     # venv + deps + Deno + config files
```

Then three quick edits:

1. **`communities.txt`** — add the Skool community URLs you're a member of (one per line).
2. **`cookies.txt`** — export your logged-in browser session → see **[docs/COOKIES.md](docs/COOKIES.md)**.
3. *(optional)* **`.env`** — add `GROQ_API_KEY` for fast transcription ([free key](https://console.groq.com/keys)). Skip it to use local CPU Whisper.

Build it, then query it:

```bash
./run.sh                           # scrape → captions → audio → transcribe → clean → index
cd kb && claude                    # or: codex  — then ask your questions
```

Re-runs preserve previously discovered video entries and skip readable transcripts. A failed request or exhausted fetch budget returns a nonzero status; inspect `kb/CRAWL_REPORT.json` and rerun the needed pass. `PAGES=100 MAX_FETCH=0 ./run.sh scrape` raises the feed-page limit and disables the fetch cap; this can take a long time and still does not prove all content was discovered.

---

## Transcription: Groq vs. local

| Option | Speed | Cost | Setup |
|---|---|---|---|
| **Groq API** (default if `GROQ_API_KEY` set) | ~100x realtime | ~$0.04/audio-hour¹ | free key from [console.groq.com/keys](https://console.groq.com/keys) |
| **faster-whisper** (fallback, CPU) | ~1–2x realtime | free | nothing extra |
| **mlx-whisper** (Apple Silicon, optional) | very fast on M-series | free | `pip install mlx-whisper` |

Most YouTube/Vimeo videos already have captions, which cost **zero** transcription either way — so the transcription backend only matters for Loom, native, and caption-less videos. Details: [docs/TRANSCRIPTION.md](docs/TRANSCRIPTION.md).

<sub>¹ Approximate; Groq bills a 10-second minimum per request and prices change — check [groq.com/pricing](https://groq.com/pricing).</sub>

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `no __NEXT_DATA__ (login wall?)` | Cookies are missing or stale. Re-export `cookies.txt` (see [docs/COOKIES.md](docs/COOKIES.md)). |
| YouTube: `Sign in to confirm you're not a bot` | The IP is bot-flagged (common on VPS/datacenter). Add fresh cookies; **run on your home machine** if possible. Heavy cases may need a [PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — still not guaranteed. |
| YouTube: `Only images are available` / no audio | yt-dlp needs a JS runtime for YouTube. `./bootstrap.sh` installs Deno; the audio pass uses `--remote-components ejs:github`. |
| Native Skool videos didn't download | Expected — they need signed HLS tokens. They're listed in `kb/MISSING_VIDEOS.md`; add any with `./add_native.sh` ([docs/NATIVE_VIDEOS.md](docs/NATIVE_VIDEOS.md)). |
| Transcription is slow | You're on local CPU Whisper. Add a `GROQ_API_KEY`, or set `WHISPER_MODEL=base` in `.env`. |

---

## Legal & ethics

This tool is for **personal use of content you already have legitimate access to** — communities you pay for or have joined. A few ground rules baked into the design and the docs:

- It only ever uses **your own** logged-in session; it cannot reach content you can't.
- **Don't redistribute** scraped content. The `.gitignore` keeps your `kb/`, cookies, and keys out of git by default — keep it that way.
- Scraping sits against Skool's Terms of Service even for content you can access; the polite request delay is on by default. Use responsibly and at your own risk.
- This project is **not affiliated with Skool, Google/YouTube, Groq, or Mux.**

See [SECURITY.md](SECURITY.md) for how the tool handles your cookies and keys.

---

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md). Good first contributions: more video hosts, better native-video handling, Windows support notes, additional languages for caption grabbing.

## License

[MIT](LICENSE) © 2026 Ian Tinney. Built on the shoulders of [yt-dlp](https://github.com/yt-dlp/yt-dlp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and [Groq](https://groq.com/).
