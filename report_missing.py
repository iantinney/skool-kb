#!/usr/bin/env python3
"""
report_missing.py — Build kb/MISSING_VIDEOS.md: the list of native Skool-hosted
videos that are NOT (yet) in your knowledge base.

Native Skool videos are Mux HLS streams behind short-lived signed tokens, so they
can't be auto-downloaded like YouTube. This report tells you exactly which lessons
are missing and how to add them, and marks any you've already added manually.

A native video counts as "in the KB" if a transcript file whose name contains the
video id exists in kb/transcripts/ (that's what add_native.sh produces).

Usage:  python3 report_missing.py [kb_dir]   (default: kb)
Reads:  native_videos.txt   Writes:  <kb_dir>/MISSING_VIDEOS.md
"""
import sys
from pathlib import Path


def load_natives(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append({"id": parts[0].strip(), "title": parts[1].strip(), "url": parts[2].strip()})
    return rows


def main():
    kb = Path(sys.argv[1] if len(sys.argv) > 1 else "kb")
    tdir = kb / "transcripts"
    kb.mkdir(parents=True, exist_ok=True)

    natives = load_natives(Path("native_videos.txt"))
    transcript_names = " ".join(p.name for p in tdir.glob("*")) if tdir.is_dir() else ""

    done, missing = [], []
    for n in natives:
        (done if n["id"] and n["id"] in transcript_names else missing).append(n)

    out = kb / "MISSING_VIDEOS.md"
    if not natives:
        out.write_text(
            "# Missing videos\n\nNo native Skool-hosted videos were found in these "
            "communities — everything discovered is external (YouTube/Loom/Vimeo) and "
            "handled automatically. Nothing to do. ✅\n",
            encoding="utf-8",
        )
        print("report_missing: no native videos; wrote clean MISSING_VIDEOS.md")
        return

    L = []
    L.append("# Missing videos — native Skool-hosted content not in this KB")
    L.append("")
    L.append(f"**{len(missing)} of {len(natives)} native videos are NOT transcribed** "
             f"({len(done)} added manually so far).")
    L.append("")
    L.append("Native Skool videos are Mux HLS streams protected by short-lived signed "
             "tokens, so — unlike YouTube/Loom/Vimeo — they can't be downloaded "
             "automatically. Everything else in these communities *is* in the KB; this "
             "page is the honest list of what's missing and how to fill it.")
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
    L.append("   That downloads it, transcribes it, and drops the transcript into the KB.")
    L.append("4. Re-run `./run.sh index` (or `python3 report_missing.py kb`) to refresh "
             "this list.")
    L.append("")
    L.append("Full walkthrough: [docs/NATIVE_VIDEOS.md](../docs/NATIVE_VIDEOS.md).")
    L.append("")
    L.append(f"## ❌ Not in the KB ({len(missing)})")
    L.append("")
    if missing:
        for n in missing:
            L.append(f"- **{n['title']}** — {n['url']}  \n  `id: {n['id']}`")
    else:
        L.append("_None — every native video has been added. 🎉_")
    if done:
        L.append("")
        L.append(f"## ✅ Already added ({len(done)})")
        L.append("")
        for n in done:
            L.append(f"- {n['title']} — `id: {n['id']}`")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"report_missing: {len(missing)} missing / {len(natives)} native videos "
          f"-> {out}")


if __name__ == "__main__":
    main()
