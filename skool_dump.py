#!/usr/bin/env python3
"""
skool_dump.py — Dump Skool community posts + video URLs into a local knowledge base.

Strategy: Skool pages expose initial page data as JSON in
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
  videos.tsv           — full catalogue of every attached video (external + native
                         Skool-hosted) with title + source, for report_videos.py.
"""

import argparse
import csv
import json
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from video_utils import id_of

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

VIDEO_PATTERNS = [
    r"https?://(?:www\.)?loom\.com/(?:share|embed)/[A-Za-z0-9]+",
    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}",
    r"https?://(?:www\.)?youtube\.com/embed/[\w-]{11}",
    r"https?://(?:www\.)?youtube\.com/(?:shorts|live)/[\w-]{11}",
    r"https?://youtu\.be/[\w-]{11}",
    r"https?://(?:www\.)?vimeo\.com/\d+",
    r"https?://player\.vimeo\.com/video/\d+",
    r"https?://[\w.-]*wistia\.(?:com|net)/(?:medias|embed/(?:iframe|medias))/[A-Za-z0-9]+",
]
VIDEO_RE = re.compile("|".join(f"(?:{p})" + r'(?:[/?&][^\s"<>\\]*)?' for p in VIDEO_PATTERNS))
HREF_RE = re.compile(r'href="(/[^"#?]+[^"]*)"')
CONTENT_KEYS = {"content", "body", "description", "desc"}
TITLE_KEYS = ("title", "name", "label")


class _NextDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id") == "__NEXT_DATA__"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.chunks.append(data)


def parse_next_data(html):
    parser = _NextDataParser()
    parser.feed(html)
    data = json.loads("".join(parser.chunks))
    if not isinstance(data, dict) or not data:
        raise ValueError("empty or invalid __NEXT_DATA__ object")
    return data


def authenticated_member(data):
    """A Next.js payload alone also exists on logged-out/public pages."""
    props = data.get("props", {}).get("pageProps", {})
    user = props.get("self") or {}
    member = user.get("member") or {}
    group = props.get("currentGroup") or {}
    return bool(user.get("id") and member.get("id")
                and (not group.get("id") or member.get("groupId") == group["id"]))


def classroom_modules(data):
    props = data.get("props", {}).get("pageProps", {})

    def modules(node):
        if isinstance(node, dict):
            unit = node.get("course", {})
            if isinstance(unit, dict) and unit.get("unitType") == "module" and unit.get("id"):
                yield unit
            for child in node.get("children", []):
                yield from modules(child)

    yield from modules(props.get("course", {}))


def classroom_links(data, page_url):
    """Follow actual course paths and module ids, excluding unrelated JSON ids."""
    props = data.get("props", {}).get("pageProps", {})
    community = community_of(page_url)
    root = f"https://www.skool.com/{community}/classroom"
    for course in props.get("allCourses", []):
        if isinstance(course, dict) and course.get("name") and course.get("metadata", {}).get("hasAccess"):
            yield f"{root}/{course['name']}"

    for unit in classroom_modules(data):
        if unit.get("metadata", {}).get("hasAccess"):
            yield f"{page_url.split('?')[0]}?md={unit['id']}"


def readable_text(value):
    if not value.startswith("[v2]"):
        return value
    try:
        document = json.loads(value[4:])
    except ValueError:
        return value  # Preserve unfamiliar/malformed content rather than lose it.

    def render(node):
        if isinstance(node, list):
            return "".join(render(item) for item in node)
        if not isinstance(node, dict):
            return ""
        text = str(node.get("text", ""))
        for mark in node.get("marks", []):
            href = mark.get("attrs", {}).get("href") if isinstance(mark, dict) else None
            if href and href != text:
                text += f" ({href})"
        text += render(node.get("content", []))
        if node.get("type") in {"paragraph", "heading", "hardBreak", "listItem"}:
            text += "\n"
        return text

    return render(document).strip()


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
            if isinstance(v, str) and v.strip():
                out.append((title, readable_text(v.strip())))
        for v in node.values():
            harvest_text(v, out, title)
    elif isinstance(node, list):
        for v in node:
            harvest_text(v, out, current_title)


PROVIDER_HOSTS = (
    ("youtu", "YouTube"), ("loom.com", "Loom"),
    ("vimeo", "Vimeo"), ("wistia", "Wistia"),
)


def provider_of(url: str) -> str:
    u = (url or "").lower()
    for host, name in PROVIDER_HOSTS:
        if host in u:
            return name
    return "Other"


def community_of(url: str) -> str:
    if "skool.com/" in (url or ""):
        return url.split("skool.com/")[1].split("/")[0].split("?")[0]
    return "?"


def harvest_videos(node, out, page_url, source_type):
    """Collect EVERY attached video (external + native) with metadata, for a full
    accounting of what was found and where. Appends dicts with keys:
        kind (external|native), provider, id, title, url, source_type, source_url.
    External videos carry `videoLinksData` (YouTube/Loom/Vimeo/Wistia); native
    Skool-hosted ones carry a bare `videoIds`. A given post is one or the other.
    The community/source come from `page_url` (the page actually being scraped) —
    never guess from a set of all groups, or every video gets one community."""
    if isinstance(node, dict):
        if "classroom" in page_url and node.get("unitType") == "module" and node.get("id"):
            page_url = f"{page_url.split('?')[0]}?md={node['id']}"
        md = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        title = str(md.get("title") or node.get("title") or node.get("name") or "(untitled)").strip()[:200]
        slug = node.get("name") if isinstance(node.get("name"), str) else None
        grp = community_of(page_url)
        # Classroom lesson pages ARE the lesson URL (…/classroom?md=…); for feed pages
        # build the direct post URL from the post's slug.
        if "classroom" in page_url or not (grp and slug):
            src = page_url
        else:
            src = f"https://www.skool.com/{grp}/{slug}"
        ext = md.get("videoLinksData") or node.get("videoLinksData")
        video_link = md.get("videoLink") or node.get("videoLink")
        if not ext and isinstance(video_link, str) and video_link.startswith(("https://", "http://")):
            ext = [{"url": video_link}]
        if isinstance(ext, str):  # Skool stores this as a JSON-encoded string
            try:
                ext = json.loads(ext)
            except (ValueError, TypeError):
                ext = None
        if isinstance(ext, list) and ext:
            for v in ext:
                if isinstance(v, dict) and v.get("url"):
                    out.append({"kind": "external", "provider": provider_of(v["url"]),
                                "id": str(v.get("video_id") or id_of(v["url"])).strip(),
                                "title": str(v.get("title") or title).strip()[:200],
                                "url": v["url"], "source_type": source_type, "source_url": src})
        else:
            raw = md.get("videoIds") or node.get("videoIds") or md.get("videoId") or node.get("videoId")
            if isinstance(raw, str) and raw.strip():
                for vid in (x.strip() for x in raw.split(",")):
                    if vid:
                        out.append({"kind": "native", "provider": "Skool", "id": vid,
                                    "title": title, "url": "", "source_type": source_type,
                                    "source_url": src})
        for v in node.values():
            harvest_videos(v, out, page_url, source_type)
    elif isinstance(node, list):
        for v in node:
            harvest_videos(v, out, page_url, source_type)


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
    ap.add_argument("--max-fetch", type=int, default=400, help="Safety cap on page attempts; 0 disables the cap (default: 400)")
    ap.add_argument("--delay", type=float, default=0.6, help="Seconds between requests (default: 0.6)")
    args = ap.parse_args()
    if args.pages < 1 or args.max_fetch < 0 or args.delay < 0:
        ap.error("--pages must be positive; --max-fetch and --delay must be nonnegative")

    sess = load_session(args.cookies)
    out_dir = Path(args.out)
    posts_dir = out_dir / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    groups = set()
    queue: list[str] = [u.rstrip("/") for u in args.urls]
    for u in args.urls:
        u = u.rstrip("/")
        seg = urlparse(u).path.strip("/").split("/")
        if seg and seg[0]:
            groups.add(seg[0])
        # Paginate community feed if this is a bare group root
        if len(seg) == 1:
            queue.extend(f"{u}?p={i}" for i in range(2, args.pages + 1))

    seen: set[str] = set()
    videos: dict[str, str] = {}      # external video url -> first page it appeared on
    catalog: dict[tuple, dict] = {}  # (kind, id_or_url) -> full video metadata
    # Preserve previously discovered entries during incremental/partial crawls.
    if Path("video_urls.txt").exists():
        source = ""
        for line in Path("video_urls.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("# from:"):
                source = line.split("# from:", 1)[1].strip()
            elif line.startswith(("https://", "http://")):
                videos.setdefault(line, source)
    if Path("videos.tsv").exists():
        with Path("videos.tsv").open(encoding="utf-8", newline="") as handle:
            for video in csv.DictReader(handle, delimiter="\t"):
                if video.get("kind") and (video.get("id") or video.get("url")):
                    video["seen_in_latest_crawl"] = "false"
                    catalog[(video["kind"], video.get("provider"), video.get("id") or video.get("url"))] = video
    current_video_keys = set()
    fetched = 0
    failures = []
    successful = []
    inaccessible = {}
    inaccessible_courses = {}

    while queue and (not args.max_fetch or fetched < args.max_fetch):
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        fetched += 1
        try:
            r = sess.get(url, timeout=30)
        except Exception as e:
            print(f"[warn] {url}: {e}", file=sys.stderr)
            failures.append({"url": url, "error": type(e).__name__})
            continue
        if r.status_code != 200:
            print(f"[warn] {url}: HTTP {r.status_code}", file=sys.stderr)
            failures.append({"url": url, "error": f"HTTP {r.status_code}"})
            continue
        html = r.text
        try:
            data = parse_next_data(html)
        except ValueError:
            print(f"[warn] {url}: missing/invalid __NEXT_DATA__ (login wall? bad cookies?)", file=sys.stderr)
            failures.append({"url": url, "error": "missing/invalid __NEXT_DATA__"})
            continue
        if not authenticated_member(data):
            print(f"[warn] {url}: authenticated community membership was not confirmed", file=sys.stderr)
            failures.append({"url": url, "error": "authenticated membership not confirmed"})
            continue
        successful.append(url)
        # Re-serialize so /-style escapes become literal chars before regexing
        is_classroom = "classroom" in urlparse(url).path.split("/")
        if is_classroom:
            for course in data.get("props", {}).get("pageProps", {}).get("allCourses", []):
                if isinstance(course, dict) and course.get("name") and not course.get("metadata", {}).get("hasAccess"):
                    inaccessible_courses[course["name"]] = {"name": course["name"], "title": course.get("metadata", {}).get("title", ""),
                                                             "url": f"https://www.skool.com/{community_of(url)}/classroom/{course['name']}"}
            for unit in classroom_modules(data):
                metadata = unit.get("metadata", {})
                if not metadata.get("hasAccess"):
                    inaccessible[unit["id"]] = {"id": unit["id"], "title": metadata.get("title", ""),
                                                "url": f"{url.split('?')[0]}?md={unit['id']}"}
        # Overview data includes sidebar descriptions from every course. Only the
        # requested course tree contains lesson content; keep overview pages for discovery.
        content_data = data.get("props", {}).get("pageProps", {}).get("course", {}) if is_classroom else data
        blob = json.dumps(content_data, ensure_ascii=False)

        raw_video_urls = [match.group(0) for match in VIDEO_RE.finditer(blob)]
        for video_url in raw_video_urls:
            videos.setdefault(video_url, url)
        source_type = "Classroom lesson" if "classroom" in urlparse(url).path else "Feed post"
        vid_hits: list = []
        harvest_videos(content_data, vid_hits, url, source_type)
        for v in vid_hits:
            key = (v["kind"], v["provider"], v["id"] or v["url"])
            if key not in current_video_keys:
                catalog[key] = {**v, "seen_in_latest_crawl": "true"}
                current_video_keys.add(key)
            if v["kind"] == "external":
                videos.setdefault(v["url"], v["source_url"])
        for video_url in raw_video_urls:
            provider, video_id = provider_of(video_url), id_of(video_url)
            key = ("external", provider, video_id or video_url)
            if key not in current_video_keys:
                catalog[key] = {"kind": "external", "provider": provider, "id": video_id,
                                "title": "(referenced link)", "source_type": source_type,
                                "source_url": url, "url": video_url, "seen_in_latest_crawl": "true"}
                current_video_keys.add(key)

        records: list = []
        harvest_text(content_data, records)
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
        inaccessible_urls = {item["url"] for item in (*inaccessible.values(), *inaccessible_courses.values())}
        for hm in HREF_RE.finditer(html):
            link = unescape(hm.group(1))
            if link.strip("/").split("/")[0] in groups:
                full = urljoin("https://www.skool.com", link)
                if full not in seen and full not in inaccessible_urls:
                    queue.append(full)
        if "classroom" in parts:
            for candidate in classroom_links(data, url):
                if candidate not in seen and candidate not in queue:
                    queue.append(candidate)

        n_native = sum(1 for k in catalog if k[0] == "native")
        print(f"[{fetched}] {url}  (queue={len(queue)}, videos={len(catalog)}, native={n_native})")
        time.sleep(args.delay)

    # video_urls.txt — the yt-dlp download feed (external videos only).
    canonical_videos = {}
    for video_url, source in videos.items():
        key = (provider_of(video_url), id_of(video_url) or video_url)
        # Preserve private Vimeo hashes/query parameters if a shorter variant
        # of the same video was also linked. yt-dlp needs the complete URL.
        if key not in canonical_videos or len(video_url) > len(canonical_videos[key][0]):
            canonical_videos[key] = (video_url, source)
    with open("video_urls.txt", "w") as f:
        for v, src in sorted(canonical_videos.values()):
            f.write(f"# from: {src}\n{v}\n")

    # videos.tsv — the full accounting of every attached video (external + native),
    # with source. Consumed by report_videos.py to build kb/VIDEO_REPORT.md and
    # kb/MISSING_VIDEOS.md. One row per video.
    cols = ["kind", "provider", "id", "title", "source_type", "community", "source_url", "url", "seen_in_latest_crawl"]
    with open("videos.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for _, v in sorted(catalog.items(),
                                key=lambda kv: (kv[1]["kind"], kv[1]["provider"], kv[1]["title"].lower())):
            row = {**v, "community": community_of(v["source_url"])}
            f.write("\t".join(str(row.get(c, "")).replace("\t", " ").replace("\n", " ") for c in cols) + "\n")

    n_native = sum(1 for k in catalog if k[0] == "native")
    n_ext = len(catalog) - n_native
    pending = sorted(set(queue) - seen)
    crawl_report = {
        "coverage_verified": False,
        "scope": "Discovered pages only; feed pagination is bounded and lesson/comment discovery is best-effort.",
        "queue_exhausted": not pending,
        "page_attempts": fetched,
        "successful_pages": successful,
        "failed_pages": failures,
        "pending_pages": pending,
        "feed_page_limit": args.pages,
        "max_fetch": args.max_fetch,
        "catalogue_is_cumulative": True,
        "inaccessible_modules": list(inaccessible.values()),
        "inaccessible_courses": list(inaccessible_courses.values()),
    }
    (out_dir / "CRAWL_REPORT.json").write_text(json.dumps(crawl_report, indent=2) + "\n", encoding="utf-8")
    print(f"\nDone. {fetched} pages fetched.")
    print(f"  {len(list(posts_dir.glob('*.md')))} markdown files in {posts_dir}/")
    print(f"  {len(videos)} external video URLs -> video_urls.txt (yt-dlp ready)")
    print(f"  {len(catalog)} videos catalogued -> videos.tsv ({n_ext} external, {n_native} native)")
    print(f"  Crawl: {len(successful)} successful, {len(failures)} failed, {len(pending)} pending -> {out_dir}/CRAWL_REPORT.json")
    print("  These counts do not prove all community lessons, posts, or comments were discovered.")
    if n_native:
        print("\nNOTE: this pipeline does not automate native Skool video downloads.")
        print("After the run, see kb/VIDEO_REPORT.md for the discovered-video")
        print("accounting and kb/MISSING_VIDEOS.md for the natives to add (docs/NATIVE_VIDEOS.md).")
    return 1 if failures or pending else 0


if __name__ == "__main__":
    sys.exit(main())
