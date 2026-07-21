# Transcription options

Most YouTube and Vimeo videos ship with **captions**, which the `captions` pass grabs for
free — no transcription needed. Transcription only kicks in for what's left (Loom, native
Skool videos you've downloaded, and the occasional caption-less YouTube video).

`transcribe.py` auto-selects a backend:

## Groq API (fast, cheap) — used when `GROQ_API_KEY` is set
- Model: **`whisper-large-v3-turbo`** (multilingual). `whisper-large-v3` also exists (a bit
  more accurate, more expensive).
- Speed: ~100x realtime. Cost: **~$0.04 per audio-hour** for turbo (approximate; a 10-second
  minimum is billed per request, and prices change — see [groq.com/pricing](https://groq.com/pricing)).
- Limits: **25 MB/request** on the free tier (100 MB on the paid/dev tier). `transcribe.py`
  automatically splits longer audio into ~15-minute chunks with ffmpeg and stitches the text.
- Get a free key: **https://console.groq.com/keys** → put `GROQ_API_KEY=gsk_...` in `.env`.

## faster-whisper (free, local, CPU) — the default fallback
- No key, no cloud. Runs on CPU via CTranslate2 with int8 quantization.
- Model via `WHISPER_MODEL` in `.env`: `tiny | base | small | medium | large-v3`
  (default `small`). On CPU, `tiny`/`base` are near realtime; `large-v3` is slow.
- Good default for a laptop with no API key: `WHISPER_MODEL=base`.

## mlx-whisper (Apple Silicon, optional)
If you're on an M-series Mac and want fast *local* transcription, `mlx-whisper` uses the
Apple GPU:
```bash
pip install mlx-whisper
mlx_whisper "audio/clip.m4a" --model mlx-community/whisper-large-v3-turbo \
  --output-dir kb/transcripts --output-format txt
```
(Apple Silicon only — it will not run on Linux or Intel Macs.) `transcribe.py` doesn't call
it automatically, but you can transcribe with it and drop the `.txt` into `kb/transcripts/`.

## Which should I pick?
- **Have a few dollars and want it done tonight?** Groq. It's the fast path and pennies for
  most communities.
- **Want zero cost / fully offline?** faster-whisper with `base` or `small`.
- **On an M-series Mac and want local + fast?** mlx-whisper.

Either way, run `./run.sh transcribe` — it skips anything already transcribed or captioned,
so it's safe to re-run.
