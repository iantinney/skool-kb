# Knowledge Base — query instructions

This folder is a personal knowledge base built from Skool communities the user is a
member of: course-video transcripts plus the text of posts, lessons, and comments.

- `posts/*.md` — post / lesson / comment text. Each file starts with `# Source: <url>`.
- `transcripts/*.txt` — one file per video; the filename is the video title.
- `INDEX.md` — one line per file summarizing its topic. Read this first to route a query.

## How to answer questions here

1. Consult `INDEX.md`, then search the folder (ripgrep/grep across `posts/` and `transcripts/`) for the topic.
2. Read the files that hit.
3. Answer directly, and **cite the source filename(s)** — the filename maps back to the
   original post URL or video title so the user can go watch/read the source.
4. If nothing matches, say so plainly ("not covered in these communities") rather than
   guessing. Don't answer from general knowledge unless the user asks you to.

If `INDEX.md` is missing or stale after new content is added, regenerate it from the repo
root with `python3 build_index.py kb`.
