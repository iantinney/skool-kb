# Repository validation

- [x] Inspect scraping, transcription, reporting, orchestration, documentation, and CI.
- [x] Add offline regressions using synthetic fixtures and mocked services.
- [x] Follow actual classroom course paths and accessible lesson ids; retain rich text, short comments, and full external video URLs.
- [x] Record partial crawl failures and pending pages, retain prior video catalogue entries, and return a failure status when work remains.
- [x] Require exact video ids and readable transcript text before counting or skipping a video.
- [x] Surface transcription failures and empty results; prevent native import from reporting an absent transcript as success.
- [x] State the distinction between discovered text coverage, complete account coverage, and playable media backups.

## Review

The original classroom traversal guessed arbitrary JSON ids and omitted the real course URL segment. It also ignored lesson `desc` / `videoLink` metadata. The corrected traversal uses the current course tree shape, decodes rich text, preserves unlisted-video URL hashes, and excludes sidebar descriptions from classroom output. Locked courses and modules are recorded without requesting their lesson pages. Authenticated identity and matching community membership are required; a logged-out page with valid Next.js JSON is recorded as a failure. Singular native `videoId` metadata is supported.

Video reports previously treated an id substring anywhere in any filename as success, including empty files. Reporting and audio selection now share exact `[id]` matching and readable-text checks. A failed transcription returns nonzero and does not create an empty completion marker. Punctuation-only results also remain incomplete: reporting, resume checks, and new transcription results share a Unicode letter-or-number check that retains short speech and non-Latin text. Existing video catalogue entries survive partial reruns.

Validation: 24 offline unit/integration regressions, Python compilation/imports, CLI help, ShellCheck, and `git diff --check`. Tests do not perform network requests, send content to transcription providers, or include private course data. A separate authorized live classroom smoke test fetched 10 pages with zero failures/pending requests, extracted 9 distinct lesson bodies and 9 external video entries, preserved an unlisted-video hash, and generated an index/report. Its private output stays outside this repository. Media-download validation remains separate operational work.

Remaining limits: membership discovery, exhaustive feed/comment traversal, native download automation, attachment retrieval, and full playable-video archiving are not supplied by this pipeline. Transcript presence does not prove duration coverage or transcription quality. Treat the project as a best-effort text KB importer, and do not advertise it as a complete account backup or a guarantee that cancellation is safe.
