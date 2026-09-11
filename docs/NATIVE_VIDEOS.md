# Native Skool-hosted videos

The current pipeline discovers native video ids and reports missing transcripts. It
does not automate playback-token retrieval. `add_native.sh` imports one authorized
HLS stream URL captured from your logged-in browser. Browser automation may also
obtain authorized playback data, but that integration is not included here.

## Check discovered-video coverage

- `kb/VIDEO_REPORT.md` compares discovered video ids with readable transcripts.
- `kb/MISSING_VIDEOS.md` lists discovered native videos without transcripts.
- `kb/CRAWL_REPORT.json` records failed requests, pending pages, inaccessible modules,
  and configured crawl limits.

These reports do not prove that every lesson or video was discovered. A transcript
does not constitute a playable video backup or preserve on-screen demonstrations.

## Import an authorized stream

1. Open the lesson/post in your logged-in browser and play the video.
2. In **DevTools → Network**, filter for **m3u8** and copy the playback request URL.
3. Run the command below promptly because signed URLs expire. Use the video id from
   `kb/MISSING_VIDEOS.md` so the report can match the resulting transcript.

   ```bash
   ./add_native.sh "<authorized m3u8 URL>" "Video Title" <video_id>
   ```

The importer asks yt-dlp to extract audio, runs the configured transcription backend,
and refreshes the index and reports. It returns a failure if no transcript is produced.
It does not save the full visual video. Browser/session or CDN restrictions may still
prevent yt-dlp from fetching a stream; inspect the actual error and keep the missing
item visible in the report.

Keep cookies and signed playback URLs private. Use only playback access already
authorized for your own account.
