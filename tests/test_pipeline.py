"""Offline regressions: synthetic fixtures only, no cookies or paid API calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import report_videos
import skool_dump
import srt2txt
import transcribe
from video_utils import id_of, transcript_ids

REPO = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def workspace():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            yield Path(directory)
        finally:
            os.chdir(previous)


def page(data, authenticated=True):
    if authenticated:
        props = data.setdefault("props", {}).setdefault("pageProps", {})
        props.setdefault("self", {"id": "synthetic_user", "member": {"id": "synthetic_membership", "groupId": "synthetic_group"}})
        props.setdefault("currentGroup", {"id": "synthetic_group"})
    return SimpleNamespace(status_code=200, text="<script nonce='test' type='application/json' id='__NEXT_DATA__'>" + json.dumps(data) + "</script>")


def run_scrape(responses, *options):
    session = SimpleNamespace(get=lambda url, timeout: responses[url])
    with patch.object(skool_dump, "load_session", return_value=session), \
         patch("sys.argv", ["skool_dump.py", "--cookies", "unused", "--pages", "1", "--delay", "0", *options]), \
         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return skool_dump.main()


class VideoTests(unittest.TestCase):
    def test_supported_id_variants(self):
        for url, expected in (
            ("https://youtube.com/watch?t=12&v=abcdefghijk", "abcdefghijk"),
            ("https://youtube.com/shorts/abcdefghijk?feature=share", "abcdefghijk"),
            ("https://youtube.com/live/abcdefghijk", "abcdefghijk"),
            ("https://youtu.be/abcdefghijk?t=3", "abcdefghijk"),
            ("https://fast.wistia.net/embed/iframe/abc123xyz", "abc123xyz"),
            ("https://player.vimeo.com/video/12345?token=example", "12345"),
            ("https://loom.com/share/abc123", "abc123"),
        ):
            with self.subTest(url=url):
                self.assertEqual(id_of(url), expected)

    def test_exact_readable_transcripts_only(self):
        with workspace() as directory:
            (directory / "A [1234].txt").write_text("Actual transcript")
            (directory / "Empty [empty].txt").write_text(" \n")
            (directory / "Other [other].json").write_text('{"transcript":"no"}')
            (directory / "Folder [folder].txt").mkdir()
            (directory / "A [caption].en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
            (directory / "A [no_text].vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\n")
            self.assertEqual(transcript_ids(directory), {"1234", "caption"})

    def test_punctuation_only_is_missing_but_short_unicode_speech_counts(self):
        with workspace() as directory:
            (directory / "Punctuation [dot].txt").write_text(". … !")
            (directory / "Punctuation [caption].srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n...\n")
            for identity, text in (("short", "Yes."), ("unicode", "你好。"), ("number", "7")):
                (directory / f"Speech [{identity}].txt").write_text(text)
            self.assertEqual(transcript_ids(directory), {"short", "unicode", "number"})
            self.assertFalse(transcribe.already_done(directory, "Punctuation [dot]"))

    def test_ledger_entries_not_in_download_feed_remain_visible(self):
        with workspace():
            Path("videos.tsv").write_text("kind\tprovider\tid\ttitle\turl\nexternal\tWistia\tabc123\tExample\thttps://fast.wistia.net/embed/iframe/abc123\n")
            self.assertEqual([video["id"] for video in report_videos.load_videos()], ["abc123"])

    def test_report_rejects_substring_matches_and_empty_transcripts(self):
        with workspace():
            Path("kb/transcripts").mkdir(parents=True)
            Path("kb/transcripts/A [1234].txt").write_text("A real transcript")
            Path("video_urls.txt").write_text("https://vimeo.com/123\nhttps://vimeo.com/1234\n")
            with patch("sys.argv", ["report_videos.py", "kb"]), contextlib.redirect_stdout(io.StringIO()):
                report_videos.main()
            report = Path("kb/VIDEO_REPORT.md").read_text()
            self.assertIn("1 of 2 videos", report)
            self.assertIn("Crawl coverage is unknown", report)


class ScraperTests(unittest.TestCase):
    def test_next_data_accepts_attribute_order_and_single_quotes(self):
        self.assertEqual(skool_dump.parse_next_data(page({"props": {}}, authenticated=False).text), {"props": {}})

    def test_next_data_rejects_missing_or_invalid_payload(self):
        for html in ("<html>Login</html>", "<script id='__NEXT_DATA__'>bad</script>"):
            with self.subTest(html=html), self.assertRaises(ValueError):
                skool_dump.parse_next_data(html)

    def test_short_comments_and_rich_lesson_text_are_kept(self):
        rich = '[v2][{"type":"paragraph","content":[{"type":"text","text":"Read","marks":[{"type":"link","attrs":{"href":"https://example.com"}}]}]}]'
        records = []
        skool_dump.harvest_text({"title": "Lesson", "desc": rich, "comments": [{"content": "Good tip."}]}, records)
        self.assertIn(("Lesson", "Read (https://example.com)"), records)
        self.assertIn(("Lesson", "Good tip."), records)

    def test_classroom_follows_course_paths_and_nested_module_ids(self):
        data = {"props": {"pageProps": {
            "allCourses": [{"id": "unrelated_course_id", "name": "abcd1234", "metadata": {"hasAccess": 1}}],
            "currentUser": {"id": "unrelated_user_id"},
            "course": {"course": {"unitType": "course"}, "children": [
                {"course": {"unitType": "set"}, "children": [
                    {"course": {"unitType": "module", "id": "lesson_id", "metadata": {"hasAccess": 1}}, "children": []}]}]},
        }}}
        self.assertEqual(set(skool_dump.classroom_links(data, "https://www.skool.com/example/classroom/abcd1234")), {
            "https://www.skool.com/example/classroom/abcd1234",
            "https://www.skool.com/example/classroom/abcd1234?md=lesson_id",
        })

    def test_metadata_video_link_gets_url_and_id(self):
        found = []
        skool_dump.harvest_videos({"metadata": {"title": "Lesson", "videoLink": "https://youtu.be/abcdefghijk"}}, found, "https://www.skool.com/example/classroom/course?md=lesson", "Classroom lesson")
        self.assertEqual(found[0]["id"], "abcdefghijk")
        self.assertEqual(found[0]["title"], "Lesson")

    def test_unlisted_vimeo_hash_and_query_are_preserved(self):
        url = "https://vimeo.com/123456789/abcdef1234?fl=tl&fe=ec"
        self.assertEqual(skool_dump.VIDEO_RE.search(json.dumps({"videoLink": url})).group(), url)

    def test_locked_modules_are_not_requested(self):
        data = {"props": {"pageProps": {"course": {"course": {"unitType": "module", "id": "locked", "metadata": {"title": "Locked"}}}}}}
        self.assertEqual(list(skool_dump.classroom_links(data, "https://www.skool.com/example/classroom/course")), [])

    def test_crawl_reaches_real_course_and_selected_lesson(self):
        with workspace():
            root = "https://www.skool.com/example/classroom"
            course = root + "/abcd1234"
            lesson = course + "?md=lesson_id"
            tree = {"course": {"unitType": "course"}, "children": [{"course": {"unitType": "module", "id": "lesson_id", "metadata": {"title": "Lesson", "hasAccess": 1}}, "children": []}]}
            responses = {
                root: page({"props": {"pageProps": {"allCourses": [{"name": "abcd1234", "description": "Sidebar only", "metadata": {"hasAccess": 1}}]}}}),
                course: page({"props": {"pageProps": {"course": tree}}}),
                lesson: page({"props": {"pageProps": {"course": {"course": {"unitType": "module", "id": "lesson_id", "metadata": {"title": "Lesson", "hasAccess": 1, "desc": "Actual lesson", "videoLink": "https://youtu.be/abcdefghijk"}}}}}}),
            }
            self.assertEqual(run_scrape(responses, root), 0)
            report = json.loads(Path("kb/CRAWL_REPORT.json").read_text())
            self.assertEqual(len(report["successful_pages"]), 3)
            self.assertFalse(report["coverage_verified"])
            posts = " ".join(path.read_text() for path in Path("kb/posts").glob("*.md"))
            self.assertIn("Actual lesson", posts)
            self.assertNotIn("Sidebar only", posts)
            self.assertIn("abcdefghijk", Path("video_urls.txt").read_text())

    def test_failed_crawl_keeps_previous_ledger_and_returns_failure(self):
        with workspace():
            Path("video_urls.txt").write_text("# from: https://www.skool.com/example/post\nhttps://youtu.be/abcdefghijk\n")
            Path("videos.tsv").write_text("kind\tprovider\tid\ttitle\tsource_type\tcommunity\tsource_url\turl\nnative\tSkool\texisting\tPrior lesson\tClassroom lesson\texample\thttps://www.skool.com/example/classroom\t\n")
            root = "https://www.skool.com/example"
            self.assertEqual(run_scrape({root: SimpleNamespace(status_code=403)}, root), 1)
            self.assertIn("existing", Path("videos.tsv").read_text())
            self.assertIn("false", Path("videos.tsv").read_text())
            self.assertIn("abcdefghijk", Path("video_urls.txt").read_text())
            self.assertEqual(json.loads(Path("kb/CRAWL_REPORT.json").read_text())["failed_pages"][0]["error"], "HTTP 403")

    def test_fetch_cap_records_pending_pages_and_returns_failure(self):
        with workspace():
            first, second = "https://www.skool.com/example", "https://www.skool.com/example/classroom"
            self.assertEqual(run_scrape({first: page({"props": {}})}, "--max-fetch", "1", first, second), 1)
            report = json.loads(Path("kb/CRAWL_REPORT.json").read_text())
            self.assertEqual(report["pending_pages"], [second])

    def test_missing_next_data_is_a_recorded_failure(self):
        with workspace():
            root = "https://www.skool.com/example"
            self.assertEqual(run_scrape({root: SimpleNamespace(status_code=200, text="Login")}, root), 1)
            self.assertEqual(len(json.loads(Path("kb/CRAWL_REPORT.json").read_text())["failed_pages"]), 1)

    def test_duplicate_provider_urls_use_one_complete_download_url(self):
        with workspace():
            root = "https://www.skool.com/example"
            full_url = "https://vimeo.com/123456789/privatehash?fl=tl"
            data = {"props": {"pageProps": {"content": "https://vimeo.com/123456789", "metadata": {"videoLink": full_url}}}}
            self.assertEqual(run_scrape({root: page(data)}, root), 0)
            feed = [line for line in Path("video_urls.txt").read_text().splitlines() if line.startswith("http")]
            self.assertEqual(feed, [full_url])
            self.assertIn("true", Path("videos.tsv").read_text())

    def test_native_singular_video_id_is_catalogued(self):
        hits = []
        skool_dump.harvest_videos({"metadata": {"title": "Lesson", "videoId": "native123"}}, hits, "https://www.skool.com/example/classroom/course?md=lesson", "Classroom lesson")
        self.assertEqual(hits[0]["id"], "native123")
        self.assertEqual(hits[0]["kind"], "native")

    def test_logged_out_next_data_and_wrong_membership_are_failures(self):
        for props in ({"self": {}}, {"self": {"id": "user", "member": {"id": "member", "groupId": "wrong"}}, "currentGroup": {"id": "requested"}}):
            with self.subTest(props=props), workspace():
                root = "https://www.skool.com/example"
                self.assertEqual(run_scrape({root: page({"props": {"pageProps": props}}, authenticated=False)}, root), 1)
                report = json.loads(Path("kb/CRAWL_REPORT.json").read_text())
                self.assertEqual(report["successful_pages"], [])
                self.assertEqual(report["failed_pages"][0]["error"], "authenticated membership not confirmed")

    def test_locked_courses_are_recorded_without_fetching(self):
        with workspace():
            root = "https://www.skool.com/example/classroom"
            data = {"props": {"pageProps": {"allCourses": [{"name": "locked_course", "metadata": {"title": "Locked course"}}]}}}
            response = page(data)
            response.text += '<a href="/example/classroom/locked_course">Locked course</a>'
            self.assertEqual(run_scrape({root: response}, root), 0)
            report = json.loads(Path("kb/CRAWL_REPORT.json").read_text())
            self.assertEqual(len(report["inaccessible_courses"]), 1)
            self.assertEqual(len(report["successful_pages"]), 1)


class TranscriptionTests(unittest.TestCase):
    def test_empty_or_prefix_collision_does_not_skip_transcription(self):
        with workspace() as directory:
            (directory / "Lesson [123].txt").write_text("")
            (directory / "Lesson [123] extended.txt").write_text("Another transcript")
            self.assertFalse(transcribe.already_done(directory, "Lesson [123]"))
            (directory / "Lesson [123].en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
            self.assertTrue(transcribe.already_done(directory, "Lesson [123]"))

    def test_failed_or_empty_transcription_does_not_claim_success(self):
        for outcome in ("", ".", "… !", RuntimeError("synthetic backend failure")):
            with self.subTest(outcome=str(outcome)), workspace():
                Path("audio").mkdir()
                Path("audio/Lesson [id].m4a").write_bytes(b"synthetic audio")
                options = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                with patch.dict(os.environ, {"GROQ_API_KEY": ""}), patch("sys.argv", ["transcribe.py"]), \
                     patch.object(transcribe, "duration_seconds", return_value=1), patch.object(transcribe, "fw_transcribe", **options), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(transcribe.main(), 1)
                self.assertFalse(Path("kb/transcripts/Lesson [id].txt").exists())

    def test_short_vtt_timestamps_are_removed(self):
        with workspace():
            path = Path("captions.vtt")
            path.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello world\n\n00:01.000 --> 00:02.000\nworld again\n")
            self.assertEqual(srt2txt.clean(path), "Hello world again")

    def test_caption_pass_succeeds_with_only_en_orig_track(self):
        with workspace() as directory:
            shutil.copy(REPO / "run.sh", directory)
            Path("kb/transcripts").mkdir(parents=True)
            Path("kb/transcripts/Lesson [id].en-orig.srt").write_text("Caption text")
            Path("cookies.txt").write_text("synthetic cookies; stub downloader never reads this")
            Path("video_urls.txt").write_text("https://youtu.be/abcdefghijk\n")
            Path("bin").mkdir()
            downloader = Path("bin/yt-dlp")
            downloader.write_text("#!/bin/sh\nexit 0\n")
            downloader.chmod(0o700)
            result = subprocess.run(["bash", "run.sh", "captions"], env={**os.environ, "PATH": str(directory / "bin") + os.pathsep + os.environ["PATH"]}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(Path("kb/transcripts/Lesson [id].en-orig.srt").exists())


if __name__ == "__main__":
    unittest.main()
