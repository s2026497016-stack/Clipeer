"""Fast, offline checks for the live monitoring primitives.

No platform or AI service is contacted.  A real stream smoke test belongs in deployment because stream
availability and platform access are external conditions.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="clipeer-live-")
os.environ["PEAKCUT_DIRECT_STREAM_HOSTS"] = "stream.example"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import creators, jobs, live  # noqa: E402

fails = []


def check(name, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   got {got!r}"))
    if not ok:
        fails.append(name)


check("configured direct HLS URL is allowed", live.url_allowed("https://stream.example/live.m3u8"))
check("unconfigured direct host is refused", live.url_allowed("https://other.example/live.m3u8"), False)
check("direct resolver keeps the original URL", live.resolve("https://stream.example/live.m3u8")["urls"],
      ["https://stream.example/live.m3u8"])

job = {"id": "test", "dir": tempfile.mkdtemp(), "creator": None, "clips": []}
s = live.Session(job, dict(creators.DEFAULTS))
s.part = 1
s.seg_clock = 0
s.buf.mkdir(exist_ok=True)
(s.buf / "p01.csv").write_text("p01_00000.ts,0.000000,6.000000\np01_00001.ts,0.000000,6.000000\n")
s._scan_segments()
check("buffer timestamps are continuous", [(round(x[1], 1), round(x[2], 1)) for x in s.segments], [(0.0, 6.0), (6.0, 12.0)])
check("overlapping moments are deduplicated", s._overlaps({"start": 10, "end": 30}, {"start": 15, "end": 25}))
check("separate moments are retained", s._overlaps({"start": 10, "end": 20}, {"start": 30, "end": 40}), False)

print("ALL PASSED" if not fails else f"{len(fails)} failed")
raise SystemExit(1 if fails else 0)
