# Native Skool-hosted videos (the hard case)

Skool hosts its own videos on [**Mux**](https://www.mux.com/case-studies/skool), delivered as
**HLS (`.m3u8`) streams protected by short-lived signed tokens**. Those tokens expire quickly
and are minted per playback session, so there's no stable URL the scraper can batch-download.

`skool_dump.py` still records what it finds in `native_videos.txt` (you'll mostly see
`image.video.skool.com/.../thumbnail.png` entries — the thumbnails — which at least tell you
how many native videos exist). Getting the actual video/audio takes one of the methods below.

## Option A — Free, per-video, with your browser + ffmpeg (recommended)

1. Play the video in your browser. Open **DevTools → Network** and filter for `m3u8`.
2. Copy the request URL of the playlist (it looks like `…/something.m3u8?token=…`).
3. Download it with the Skool referer (the CDN requires it):
   ```bash
   yt-dlp --referer "https://www.skool.com/" -o "lesson.mp4" "<paste the .m3u8?token=... URL>"
   # or with ffmpeg:
   ffmpeg -headers "Referer: https://www.skool.com/" -i "<m3u8 url>" -c copy lesson.mp4
   ```
4. The token expires fast — grab a fresh URL per video, right before downloading.
5. To fold it into your KB, extract audio and transcribe:
   ```bash
   ffmpeg -i lesson.mp4 -vn -ac 1 -ar 16000 -b:a 48k "audio/Lesson Title.m4a"
   ./run.sh transcribe
   ```

## Option B — A paid browser extension (convenience, not free/open-source)

There is a maintained commercial extension, **"Downloader for Skool"** by SERP Apps
([github.com/serpapps/skool-downloader](https://github.com/serpapps/skool-downloader), also on
the Chrome Web Store), that automates the token dance and bulk-downloads Skool/Loom/Vimeo/
YouTube/Wistia videos to MP4.

Be aware, so you can decide with eyes open:
- It is **proprietary and freemium** — roughly **3 free downloads**, then it's paid.
- The GitHub repo is mostly **marketing/distribution**, not open source you can audit.

If you have a lot of native videos and value your time over a few dollars, it's an option.
For a free/auditable workflow, use **Option A**. After either, drop the resulting audio into
`audio/` and run `./run.sh transcribe`.

## Reality check

If your communities are mostly text + YouTube/Loom/Vimeo videos, you can safely **ignore
native videos** — the scraper + caption/Whisper passes already capture the large majority of
the content. Native-video handling is the one area where full automation isn't possible today.
