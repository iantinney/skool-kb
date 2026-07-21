#!/usr/bin/env python3
"""
report_videos.py — Full video accounting for your knowledge base.

Reads videos.tsv (written by skool_dump.py: every attached video + its source)
and cross-references kb/transcripts/ to determine which videos actually made it
into the KB. Writes two reports:

  kb/VIDEO_REPORT.md    — the complete ledger: totals + breakdown by community,
                          source type (feed post vs classroom lesson) and provider,
                          and an explicit list of everything NOT in the KB.
  kb/MISSING_VIDEOS.md  — the native Skool-hosted videos not in the KB, with the
                          per-item steps to add them via ./add_native.sh.

A video counts as "in the KB" if a transcript file in kb/transcripts/ contains
its id (that's how captions and add_native.sh name their output).

Usage:  python3 report_videos.py [kb_dir]   (default: kb)
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

TSV = Path("videos.tsv")
FEED = Path("video_urls.txt")

PROVIDER_HOSTS = (("youtu", "YouTube"), ("loom.com", "Loom"),
                  ("vimeo", "Vimeo"), ("wistia", "Wistia"))
ID_PATTERNS = (
    r"(?:v=|youtu\.be/|embed/)([\w-]{11})",         # YouTube
    r"loom\.com/(?:share|embed)/([A-Za-z0-9]+)",    # Loom
    r"vimeo\.com/(?:video/)?(\d+)",                  # Vimeo
    r"wistia\.[a-z]+/(?:medias|iframe)/([A-Za-z0-9]+)",  # Wistia
)


def provider_of(url):
    u = (url or "").lower()
    for host, name in PROVIDER_HOSTS:
        if host in u:
            return name
    return "Other"


def community_of(url):
    return url.split("skool.com/")[1].split("/")[0].split("?")[0] if "skool.com/" in (url or "") else "?"


def id_of(url):
    for pat in ID_PATTERNS:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


def load_tsv():
    rows = []
    if not TSV.exists():
        return rows
    lines = TSV.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return rows
    header = lines[0].split("\t")
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("\t")
        rows.append({header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))})
    return rows


def load_external_feed():
    """External videos actually fed to yt-dlp: (url, source_page) from video_urls.txt."""
    out, src = [], ""
    if not FEED.exists():
        return out
    for line in FEED.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("# from:"):
            src = line.split("# from:", 1)[1].strip()
        elif line.startswith("http"):
            out.append((line, src))
    return out


def load_videos():
    """Unify the external download feed (video_urls.txt) with structured metadata
    (videos.tsv). External universe = what we tried to download; native = videos.tsv."""
    tsv = load_tsv()
    by_id = {r["id"]: r for r in tsv if r.get("id")}

    videos, seen = [], set()
    for url, page in load_external_feed():
        vid = id_of(url)
        dedup_key = vid or url
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        meta = by_id.get(vid, {})
        stype = meta.get("source_type") or ("Classroom lesson" if "classroom" in page else "Feed post")
        videos.append({
            "kind": "external",
            "provider": meta.get("provider") or provider_of(url),
            "id": vid,
            "title": meta.get("title") or "(referenced link)",
            "url": url,
            "source_type": stype,
            "community": meta.get("community") or community_of(page or url),
            "source_url": meta.get("source_url") or page,
        })
    for r in tsv:
        if r.get("kind") == "native":
            videos.append(r)
    return videos


def main():
    kb = Path(sys.argv[1] if len(sys.argv) > 1 else "kb")
    tdir = kb / "transcripts"
    kb.mkdir(parents=True, exist_ok=True)

    videos = load_videos()
    names = " ".join(p.name for p in tdir.glob("*")) if tdir.is_dir() else ""

    for v in videos:
        v["in_kb"] = bool(v.get("id")) and v["id"] in names

    total = len(videos)
    in_kb = [v for v in videos if v["in_kb"]]
    missing = [v for v in videos if not v["in_kb"]]
    missing_ext = [v for v in missing if v.get("kind") == "external"]
    missing_nat = [v for v in missing if v.get("kind") == "native"]

    # ---- kb/VIDEO_REPORT.md ----
    if not videos:
        (kb / "VIDEO_REPORT.md").write_text(
            "# Video report\n\nNo videos catalogued yet. Run `./run.sh scrape` first.\n",
            encoding="utf-8")
    else:
        grp = defaultdict(lambda: [0, 0])  # (community, source_type, provider) -> [total, in_kb]
        for v in videos:
            key = (v.get("community", "?"), v.get("source_type", "?"), v.get("provider", "?"))
            grp[key][0] += 1
            grp[key][1] += 1 if v["in_kb"] else 0

        L = ["# Video report — what's in your knowledge base", ""]
        pct = (100 * len(in_kb) // total) if total else 0
        L.append(f"**{len(in_kb)} of {total} videos are in the knowledge base ({pct}%).** "
                 f"{len(missing)} are not: {len(missing_ext)} external (download/transcription "
                 f"failed) and {len(missing_nat)} native Skool videos (can't be auto-downloaded).")
        L.append("")
        L.append("A video is \"in the KB\" if it has a transcript in `transcripts/` "
                 "(from captions, Whisper, or `./add_native.sh`).")
        L.append("")
        L.append("## Breakdown by community, source, and provider")
        L.append("")
        L.append("| Community | Source | Provider | Total | In KB | Missing |")
        L.append("|---|---|---|--:|--:|--:|")
        for key in sorted(grp):
            tot, ok = grp[key]
            L.append(f"| {key[0]} | {key[1]} | {key[2]} | {tot} | {ok} | {tot - ok} |")
        L.append(f"| **All** | | | **{total}** | **{len(in_kb)}** | **{len(missing)}** |")
        L.append("")

        if missing_ext:
            L.append(f"## ❌ External videos NOT in the KB ({len(missing_ext)})")
            L.append("")
            L.append("These have captions/audio that failed to download or transcribe "
                     "(often Loom/Vimeo auth, or a caption-less private video). Re-run "
                     "`./run.sh captions && ./run.sh audio && ./run.sh transcribe`; if one "
                     "keeps failing, open its source URL to check access.")
            L.append("")
            for v in sorted(missing_ext, key=lambda x: (x.get("provider", ""), x.get("title", "").lower())):
                L.append(f"- **{v.get('title', '?')}** — {v.get('provider', '?')} · "
                         f"{v.get('source_type', '?')} · {v.get('community', '?')}  \n"
                         f"  {v.get('url') or v.get('source_url', '')}")
            L.append("")

        if missing_nat:
            L.append(f"## ❌ Native Skool videos NOT in the KB ({len(missing_nat)})")
            L.append("")
            L.append("Native Skool videos are Mux HLS with signed tokens and can't be "
                     "auto-downloaded. Add any of them with `./add_native.sh` — the full "
                     "list with instructions is in [MISSING_VIDEOS.md](MISSING_VIDEOS.md).")
            L.append("")

        L.append(f"## ✅ In the KB ({len(in_kb)})")
        L.append("")
        L.append("See [INDEX.md](INDEX.md) for the per-file map of everything that's searchable.")
        (kb / "VIDEO_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # ---- kb/MISSING_VIDEOS.md (native, drives add_native.sh) ----
    total_native = len([v for v in videos if v.get("kind") == "native"])
    write_missing_natives(kb, missing_nat, total_native)

    print(f"report_videos: {len(in_kb)}/{total} videos in KB · "
          f"{len(missing_ext)} external + {len(missing_nat)} native missing "
          f"-> kb/VIDEO_REPORT.md, kb/MISSING_VIDEOS.md")


def write_missing_natives(kb, missing_nat, total_native):
    out = kb / "MISSING_VIDEOS.md"
    if total_native == 0:
        out.write_text(
            "# Missing videos\n\nNo native Skool-hosted videos were found — everything "
            "is external (YouTube/Loom/Vimeo) and handled automatically. ✅\n",
            encoding="utf-8")
        return
    added = total_native - len(missing_nat)
    L = ["# Missing videos — native Skool-hosted content not in this KB", ""]
    L.append(f"**{len(missing_nat)} of {total_native} native videos are NOT transcribed** "
             f"({added} added manually so far).")
    L.append("")
    L.append("Native Skool videos are Mux HLS streams protected by short-lived signed "
             "tokens, so — unlike YouTube/Loom/Vimeo — they can't be downloaded "
             "automatically. This page is the honest list of what's missing and how to "
             "fill it. (See kb/VIDEO_REPORT.md for the full video accounting.)")
    L.append("")
    L.append("## How to add one (≈1 minute each)")
    L.append("")
    L.append("1. Open the lesson/post in your browser and start playing the video.")
    L.append("2. Open **DevTools → Network**, filter for `m3u8`, and copy the request "
             "URL (it looks like `…/….m3u8?token=…`).")
    L.append("3. From the project root, run (the `id` is shown next to each item below):")
    L.append("   ```bash")
    L.append("   ./add_native.sh \"<paste the m3u8 URL>\" \"Video Title\" <video_id>")
    L.append("   ```")
    L.append("4. Re-run `./run.sh report` to refresh this list.")
    L.append("")
    L.append("Full walkthrough: [docs/NATIVE_VIDEOS.md](../docs/NATIVE_VIDEOS.md).")
    L.append("")
    L.append(f"## ❌ Not in the KB ({len(missing_nat)})")
    L.append("")
    if missing_nat:
        for v in sorted(missing_nat, key=lambda x: x.get("title", "").lower()):
            L.append(f"- **{v.get('title', '?')}** — {v.get('source_url', '')}  \n"
                     f"  `id: {v.get('id', '')}`")
    else:
        L.append("_None — every native video has been added. 🎉_")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
