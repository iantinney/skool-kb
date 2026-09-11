"""Shared video identity and transcript checks (no network access)."""
import re
from pathlib import Path

from srt2txt import clean


def id_of(url):
    for pattern in (
        r"(?:[?&]v=|youtu\.be/|youtube(?:-nocookie)?\.com/(?:embed|shorts|live)/)([\w-]{11})(?![\w-])",
        r"loom\.com/(?:share|embed)/([A-Za-z0-9]+)",
        r"vimeo\.com/(?:video/)?(\d+)",
        r"wistia\.(?:com|net)/(?:medias|(?:embed/)?(?:iframe|medias))/([A-Za-z0-9]+)",
    ):
        match = re.search(pattern, url or "")
        if match:
            return match.group(1)
    return ""


def has_text_content(text):
    """Require a Unicode letter or number; punctuation alone is not transcript text."""
    return any(character.isalnum() for character in text)


def has_transcript_text(path):
    if not path.is_file() or path.suffix.lower() not in {".txt", ".srt", ".vtt"}:
        return False
    text = clean(path) if path.suffix.lower() != ".txt" else path.read_text(encoding="utf-8", errors="ignore")
    return has_text_content(text)


def transcript_ids(directory):
    """Require the exact [video_id] suffix and actual text, not a substring match."""
    found = set()
    for path in Path(directory).glob("*"):
        match = re.search(r"\[([^\[\]]+)\](?:\.[A-Za-z][A-Za-z-]*)?\.(?:txt|srt|vtt)$", path.name)
        if match and has_transcript_text(path):
            found.add(match.group(1))
    return found


if __name__ == "__main__":
    import sys

    # Print the download feed entries that still lack readable transcripts.
    done = transcript_ids(sys.argv[1])
    for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if url.startswith(("https://", "http://")) and id_of(url) not in done:
            print(url)
