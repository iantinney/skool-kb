#!/usr/bin/env python3
"""
skool_dump.py — Dump Skool community posts + video URLs into a local knowledge base.

Strategy: Skool is a Next.js app, so every page embeds its full data as JSON in
<script id="__NEXT_DATA__">. We don't guess the schema — we walk the JSON
generically, harvesting (a) any "content"-like text fields into markdown files,
and (b) any video URLs (Loom / YouTube / Vimeo / Wistia / native Skool) into
batch files for yt-dlp.

Usage:
  python3 skool_dump.py --cookies cookies.txt --out kb --pages 30 \
      https://www.skool.com/yourgroup \
      https://www.skool.com/yourgroup/classroom

Outputs:
  kb/posts/*.md        — post/lesson text, one file per page
  video_urls.txt       — Loom/YouTube/Vimeo/Wistia links (feed straight to yt-dlp)
  native_videos.txt    — Skool-hosted (Mux/HLS) videos; these need a signed
                         token, see notes printed at the end.
"""

import argparse
import json
import re
import sys
import time
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

VIDEO_PATTERNS = [
    r"https?://(?:www\.)?loom\.com/(?:share|embed)/[A-Za-z0-9]+",
    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}",
    r"https?://(?:www\.)?youtube\.com/embed/[\w-]{11}",
    r"https?://youtu\.be/[\w-]{11}",
    r"https?://(?:www\.)?vimeo\.com/\d+",
    r"https?://player\.vimeo\.com/video/\d+",
    r"https?://[\w.-]*wistia\.(?:com|net)/(?:medias|embed/(?:iframe|medias))/[A-Za-z0-9]+",
]
VIDEO_RE = re.compile("|".join(f"(?:{p})" for p in VIDEO_PATTERNS))
NATIVE_RE = re.compile(r"https?://[\w.-]*video\.skool\.com/[^\s\"'\\]+")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
HREF_RE = re.compile(r'href="(/[^"#?]+[^"]*)"')
HEX32_RE = re.compile(r'"([0-9a-f]{32})"')

CONTENT_KEYS = {"content", "body", "description"}
TITLE_KEYS = ("title", "name", "label")


def load_session(cookies_path: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.skool.com/"})
    jar = MozillaCookieJar(cookies_path)
    jar.load(ignore_discard=True, ignore_expires=True)
    s.cookies = jar  # type: ignore[assignment]
    return s


def harvest_text(node, out, current_title=None):
    """Recursively collect (title, content) pairs from arbitrary JSON."""
    if isinstance(node, dict):
        title = current_title
        for tk in TITLE_KEYS:
            v = node.get(tk)
            if isinstance(v, str) and 0 < len(v) < 200:
                title = v
                break
        for ck in CONTENT_KEYS:
            v = node.get(ck)
            if isinstance(v, str) and len(v.strip()) > 40:
                out.append((title, v.strip()))
        for v in node.values():
            harvest_text(v, out, title)
    elif isinstance(node, list):
        for v in node:
            harvest_text(v, out, current_title)


def slugify(url: str) -> str:
    p = urlparse(url)
    slug = (p.path.strip("/") + ("_" + p.query if p.query else "")).replace("/", "_")
    return re.sub(r"[^\w\-.]", "_", slug)[:120] or "index"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+", help="Skool start URLs (group root, classroom, courses, posts)")
    ap.add_argument("--cookies", required=True, help="Netscape-format cookies.txt (logged-in Skool session)")
    ap.add_argument("--out", default="kb", help="Output dir for markdown (default: kb)")
    ap.add_argument("--pages", type=int, default=20, help="Feed pages to paginate per group root (default: 20)")
    ap.add_argument("--max-fetch", type=int, default=400, help="Safety cap on total page fetches (default: 400)")
    ap.add_argument("--delay", type=float, default=0.6, help="Seconds between requests (default: 0.6)")
    args = ap.parse_args()

    sess = load_session(args.cookies)
    out_dir = Path(args.out)
    posts_dir = out_dir / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    groups = set()
    queue: list[str] = []
    for u in args.urls:
        u = u.rstrip("/")
        queue.append(u)
        seg = urlparse(u).path.strip("/").split("/")
        if seg and seg[0]:
            groups.add(seg[0])
        # Paginate community feed if this is a bare group root
        if len(seg) == 1:
            queue.extend(f"{u}?p={i}" for i in range(2, args.pages + 1))

    seen: set[str] = set()
    videos: dict[str, str] = {}   # url -> first page it appeared on
    natives: dict[str, str] = {}
    fetched = 0

    while queue and fetched < args.max_fetch:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            r = sess.get(url, timeout=30)
        except Exception as e:
            print(f"[warn] {url}: {e}", file=sys.stderr)
            continue
        fetched += 1
        if r.status_code != 200:
            print(f"[warn] {url}: HTTP {r.status_code}", file=sys.stderr)
            continue
        html = r.text
        if "__NEXT_DATA__" not in html:
            print(f"[warn] {url}: no __NEXT_DATA__ (login wall? bad cookies?)", file=sys.stderr)
            continue

        m = NEXT_DATA_RE.search(html)
        try:
            data = json.loads(m.group(1)) if m else {}
        except json.JSONDecodeError:
            data = {}
        # Re-serialize so /-style escapes become literal chars before regexing
        blob = json.dumps(data, ensure_ascii=False)

        for vm in VIDEO_RE.finditer(blob):
            videos.setdefault(vm.group(0), url)
        for nm in NATIVE_RE.finditer(blob):
            natives.setdefault(nm.group(0), url)

        records: list = []
        harvest_text(data, records)
        # Dedupe identical content blocks on this page
        uniq, seen_c = [], set()
        for t, c in records:
            if c not in seen_c:
                seen_c.add(c)
                uniq.append((t, c))
        if uniq:
            fp = posts_dir / f"{slugify(url)}.md"
            with fp.open("w", encoding="utf-8") as f:
                f.write(f"# Source: {url}\n\n")
                for t, c in uniq:
                    if t:
                        f.write(f"## {unescape(t)}\n\n")
                    f.write(unescape(c) + "\n\n---\n\n")

        # Discover more same-group pages: rendered anchors + classroom module ids
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        for hm in HREF_RE.finditer(html):
            link = hm.group(1)
            if link.strip("/").split("/")[0] in groups:
                full = urljoin("https://www.skool.com", link)
                if full not in seen:
                    queue.append(full)
        if "classroom" in parts:
            base = url.split("?")[0]
            for hx in set(HEX32_RE.findall(blob)):
                cand = f"{base}?md={hx}"
                if cand not in seen:
                    queue.append(cand)

        print(f"[{fetched}] {url}  (queue={len(queue)}, videos={len(videos)}, native={len(natives)})")
        time.sleep(args.delay)

    with open("video_urls.txt", "w") as f:
        for v, src in sorted(videos.items()):
            f.write(f"# from: {src}\n{v}\n")
    with open("native_videos.txt", "w") as f:
        for v, src in sorted(natives.items()):
            f.write(f"# from: {src}\n{v}\n")

    print(f"\nDone. {fetched} pages fetched.")
    print(f"  {len(list(posts_dir.glob('*.md')))} markdown files in {posts_dir}/")
    print(f"  {len(videos)} external video URLs -> video_urls.txt (yt-dlp ready)")
    print(f"  {len(natives)} native Skool video URLs -> native_videos.txt")
    if natives:
        print("\nNOTE: native Skool videos use short-lived signed HLS tokens. If the URLs in")
        print("native_videos.txt fail, grab fresh .m3u8?token=... URLs from DevTools > Network")
        print('while playing, then: yt-dlp --referer "https://www.skool.com/" -o name.mp4 "<m3u8-url>"')


if __name__ == "__main__":
    main()
