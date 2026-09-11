# AGENTS.md — instructions for AI coding agents

You are an AI agent (Claude Code, Codex, Cursor, etc.) helping a user set up **skool-kb**:
a tool that turns their Skool communities into a searchable, plain-text knowledge base.
Assume the user may be **non-technical**. Drive the setup as a friendly conversation —
ask for what you need, do the mechanical work yourself, and explain each external step
(like installing a browser extension) in plain language.

This file is the onboarding runbook. `README.md` is the human reference; `docs/` has depth.

---

## Golden rules (do not violate)

1. **Never commit or transmit secrets.** `cookies.txt` and `.env` are gitignored — keep it that way. Never paste their contents into a commit, an issue, a PR, or any external service. If the user pastes cookies/keys into chat, write them straight to the file and don't echo them back.
2. **Cookies come from the user's own logged-in browser**, on the machine where they use Skool/YouTube. You cannot and should not obtain them any other way.
3. **Best results run on the user's personal computer** (residential IP), not a cloud VPS — YouTube bot-checks datacenter IPs. If you're running on a server, warn the user early (see Step 5 failure mode).
4. **Don't oversell.** If a step is unreliable (native videos, YouTube on a VPS), say so. Honesty is a feature here.
5. **Verify, don't assume.** External tools change. If something fails, read the actual error before recommending a fix. The commands below were verified in mid-2026; check current docs if they misbehave.

---

## Onboarding, step by step

### Step 1 — Environment + install
Run the bootstrapper. It creates a venv, installs Python deps, checks for `ffmpeg`, and installs Deno (the JS runtime yt-dlp needs for YouTube):

```bash
./bootstrap.sh
```

If `ffmpeg` is missing, tell the user to install it (`brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu) — it's required for transcription but not for scraping/captions.

### Step 2 — Which communities?
Ask: **"Which Skool communities do you want to include? Paste the URLs — you must be a logged-in member of each."** Write one root URL per line into `communities.txt` (created from `communities.example.txt`). Use the community root (e.g. `https://www.skool.com/their-community`); the pipeline auto-crawls the `/classroom` section too.

### Step 3 — Cookies (the one genuinely manual step)
The scraper needs the user's logged-in session. Walk them through it:

1. In their browser, install the extension **"Get cookies.txt LOCALLY"** — this is the **safe, actively maintained** one (Chrome/Edge/Brave). ⚠️ *Not* the old "Get cookies.txt" without "LOCALLY" — that one was pulled from the store as malware. On Firefox, the recommended equivalent is the add-on named **"cookies.txt"**.
2. Have them visit **skool.com while logged in**, click the extension, and **Export**.
3. Get that file to the project as `cookies.txt`. If the user is on the same machine, that's a file move. If you're on a remote machine, have them **paste the file contents into chat** and you write it to `cookies.txt` (normalize whitespace to TABs — Netscape format is tab-delimited), or `scp` it over.

**For videos, YouTube cookies help too.** If the community has many YouTube videos, ask the user to *also* export **youtube.com** cookies and append them to `cookies.txt` (one file can hold cookies for multiple domains). yt-dlp's recommended reliable method for YouTube: export from a **private/incognito window** logged into YouTube, then close that window **without logging out** (keeps the session pinned). See [docs/COOKIES.md](docs/COOKIES.md).

**Verify cookies before crawling** — fetch one community page and confirm it's authenticated:
```bash
.venv/bin/python - <<'PY'
from skool_dump import load_session
import sys
r = load_session("cookies.txt").get(sys.argv[1] if len(sys.argv)>1 else "https://www.skool.com", timeout=30)
print("HTTP", r.status_code, "| __NEXT_DATA__:", "__NEXT_DATA__" in r.text, "| signed_in:", '"currentUser"' in r.text or '"authUser"' in r.text)
PY
```
If `__NEXT_DATA__` is False or it looks logged-out, the cookies are stale — ask for a fresh export.

### Step 4 — Transcription backend (ask, don't assume)
Ask: **"Do you want fast cloud transcription (Groq — a free API key, pennies per hour) or free local transcription (slower, uses your CPU)?"**
- **Groq:** send them to **https://console.groq.com/keys**, have them create a free key (starts with `gsk_`), and write `GROQ_API_KEY=...` into `.env`. Note the free tier caps uploads at 25 MB/request; the pipeline auto-splits longer audio.
- **Local:** nothing to do — it falls back to `faster-whisper` on CPU. Suggest `WHISPER_MODEL=base` in `.env` for a good speed/quality balance on CPU-only machines.
- Most YouTube/Vimeo videos have free captions anyway, so this only affects Loom/native/caption-less videos.

### Step 5 — Run the pipeline
Run it end to end, or pass by pass so you can report progress and catch issues early:

```bash
./run.sh scrape        # posts + video URLs   → report counts
./run.sh captions      # free YouTube/Vimeo captions
./run.sh audio         # audio for caption-less videos (needs Deno)
./run.sh transcribe    # Whisper the audio
./run.sh clean         # dedupe captions → clean plain text
./run.sh index         # build kb/INDEX.md
./run.sh report        # build kb/MISSING_VIDEOS.md (native videos not in the KB)
# ...or just: ./run.sh   (all of the above)
```

**Known failure modes — handle them, don't panic:**
- **`Sign in to confirm you're not a bot` (YouTube):** the IP is bot-flagged. This is common on VPS/servers. Fixes, in order: (a) ensure fresh youtube.com cookies are in `cookies.txt`; (b) **recommend running on the user's home computer instead**; (c) as a last resort, a [bgutil PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — but tell the user it's not guaranteed. Do **not** hammer the endpoint; the polite sleeps are already set.
- **`Only images are available` / no audio formats (YouTube):** Deno isn't installed or on PATH. Re-run `./bootstrap.sh`; the audio pass already passes `--remote-components ejs:github`.
- **Native Skool videos not downloaded:** expected and handled by design. This pipeline does not automate their download. After the run, open **`kb/MISSING_VIDEOS.md`** — it lists discovered native videos by title + URL + id. Tell the user the count, and explain the stream import workflow: play it, capture the `.m3u8` URL from DevTools → Network, then `./add_native.sh "<m3u8 URL>" "Title" <video_id>`. Offer to walk them through one. Don't promise bulk/headless native download; see [docs/NATIVE_VIDEOS.md](docs/NATIVE_VIDEOS.md).
- **A few Loom/Vimeo failures:** normal (auth/impersonation). Note them and move on.

### Step 6 — Verify it works
Inspect `kb/CRAWL_REPORT.json` for failed/pending pages and inaccessible modules. A completed queue does not prove every feed page or comment was discovered. `kb/VIDEO_REPORT.md` counts readable transcripts for discovered videos only; it does not establish a complete account or playable-video backup. Never advise cancelling access based on these counts alone.

After the run, prove the KB answers questions. From `kb/`, run a real query and confirm it cites filenames:
```bash
cd kb && claude -p "Using only these files, what topics are covered? Cite 3 filenames."
```
Then tell the user how they'll use it day to day: `cd kb && claude` (or `codex`) and just ask.

---

## Reference

**Layout:** `skool_dump.py` (scraper) · `transcribe.py` (audio→text) · `srt2txt.py` (caption cleanup) · `build_index.py` (INDEX.md) · `run.sh` (orchestrator) · `kb/` (the output you query, with its own `CLAUDE.md`).

**Verified external references (mid-2026):**
- Cookie extension (Chrome): "Get cookies.txt LOCALLY" · Firefox: "cookies.txt" add-on
- Groq keys: https://console.groq.com/keys · models: `whisper-large-v3-turbo`, `whisper-large-v3`
- Deno install (bootstrap handles it): `curl -fsSL https://deno.land/install.sh | sh`
- yt-dlp YouTube JS runtime / EJS: https://github.com/yt-dlp/yt-dlp/wiki/EJS
- Native Skool video uses signed playback; the current importer accepts one authorized stream URL at a time.

**Never do:** commit `cookies.txt`/`.env`; push the user's `kb/` content; recommend the deprecated non-"LOCALLY" cookie extension; promise a YouTube bot-check bypass on a VPS; or claim bulk native-video download works.
