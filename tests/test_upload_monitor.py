"""Offline tests for automatic creator upload discovery."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["CLIPEER_DATA"] = tempfile.mkdtemp(prefix="clipeer-upload-test-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import uploads  # noqa: E402

fails = []


def check(name, got, expected):
    ok = got == expected
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   got {got!r}"))
    if not ok:
        fails.append(name)


entries = [{"id": "newest", "title": "Newest"}, {"id": "middle"}, {"id": "oldest"}]
check("new uploads are returned oldest first", [e["id"] for e in uploads._new_entries(entries, {"oldest"})],
      ["middle", "newest"])
check("seen uploads are not repeated", uploads._new_entries(entries, {"newest", "middle", "oldest"}), [])
check("YouTube upload URL is built from video ID", uploads._entry_url({"id": "abcdefghijk"}, "youtube"),
      "https://www.youtube.com/watch?v=abcdefghijk")
check("Twitch VOD URL is built from numeric ID", uploads._entry_url({"id": "123456"}, "twitch"),
      "https://www.twitch.tv/videos/123456")
check("YouTube channel is converted to its videos tab", uploads._listing_url("https://youtube.com/@sample", "youtube"),
      "https://youtube.com/@sample/videos")
check("existing /videos suffix is not duplicated", uploads._listing_url("https://twitch.tv/sample/videos", "twitch"),
      "https://twitch.tv/sample/videos")

print("ALL PASSED" if not fails else f"{len(fails)} failed")
raise SystemExit(1 if fails else 0)
