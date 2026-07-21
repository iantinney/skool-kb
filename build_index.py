#!/usr/bin/env python3
"""
build_index.py — Generate kb/INDEX.md: one line per file so an agent can pick
which files to open instead of blind-grepping the whole corpus.

Fast and LLM-free: titles come from filenames, topic hints from the first words
of each file. Re-run any time the KB changes.

Usage:  python3 build_index.py [kb_dir]   (default: kb)
"""
import re
import sys
from pathlib import Path


def strip_id(name: str) -> str:
    return re.sub(r"\s*\[[A-Za-z0-9_-]+\]\s*$", "", name).strip()


def main():
    kb = Path(sys.argv[1] if len(sys.argv) > 1 else "kb")
    tdir, pdir = kb / "transcripts", kb / "posts"

    lines = [
        "# Knowledge Base Index",
        "",
        "One line per file. Search here first to pick which files to open.",
        "Files live in `transcripts/` (video transcripts) and `posts/` (posts, lessons, comments).",
        "",
    ]

    tx = sorted(tdir.glob("*.txt")) if tdir.is_dir() else []
    lines.append(f"## Video transcripts ({len(tx)})\n")
    for f in tx:
        words = f.read_text(encoding="utf-8", errors="ignore").split()
        snippet = " ".join(words[:18])
        lines.append(f"- **{strip_id(f.stem)}** — {snippet}… `transcripts/{f.name}`")

    ps = sorted(pdir.glob("*.md")) if pdir.is_dir() else []
    lines.append(f"\n## Posts & lessons ({len(ps)})\n")
    for f in ps:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"# Source: (\S+)", txt)
        src = m.group(1) if m else ""
        h = re.search(r"^## (.+)$", txt, re.M)
        heading = h.group(1).strip() if h else ""
        body = re.sub(r"^#.*$", "", txt, flags=re.M)
        body = re.sub(r"-{3,}", "", body)
        snippet = " ".join(body.split()[:18])
        label = heading or (src.split("/")[-1] if src else f.stem)
        lines.append(f"- **{label}** — {snippet}… `posts/{f.name}`")

    (kb / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {kb}/INDEX.md: {len(tx)} transcripts + {len(ps)} posts = {len(tx) + len(ps)} entries")


if __name__ == "__main__":
    main()
