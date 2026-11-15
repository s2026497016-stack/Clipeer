"""Automatic detection of new public creator uploads.

The first scan establishes a baseline and deliberately skips the back catalogue. New uploads
use the existing video job pipeline, so Gemini clipping and the existing clip-ready publishing
callback remain the single processing path.
"""
import json
import threading
import time
from pathlib import Path

from . import alerts, auth, config, creators, ctx, jobs

POLL_SECONDS = max(60, int(config.env("CLIPEER_UPLOAD_POLL_SECONDS", "300")))
LIST_LIMIT = 12
_state_lock = threading.RLock()
_started = False


def _listing_url(channel: str, platform: str) -> str:
    base = (channel or "").strip().rstrip("/")
    for suffix in ("/videos", "/streams", "/live", "/featured"):
        if base.lower().endswith(suffix):
            base = base[:-len(suffix)].rstrip("/")
    return base + "/videos" if platform in ("youtube", "twitch", "kick") else ""


def _entry_id(entry: dict) -> str:
    return str(entry.get("id") or entry.get("url") or entry.get("webpage_url") or "").strip()[:200]


def _entry_url(entry: dict, platform: str) -> str:
    url = str(entry.get("webpage_url") or entry.get("original_url") or "").strip()
    if url.startswith(("https://", "http://")):
        return url
    ident = _entry_id(entry)
    if not ident:
        return ""
    if platform == "youtube":
        return "https://www.youtube.com/watch?v=" + ident
    if platform == "twitch" and ident.isdigit():
        return "https://www.twitch.tv/videos/" + ident
    return ""


def _new_entries(entries, seen: set) -> list:
    """Return valid, unseen entries in chronological order (oldest first)."""
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        ident = _entry_id(entry)
        if ident and ident not in seen:
            out.append(entry)
    return list(reversed(out))


def _list_uploads(channel: str, platform: str) -> list:
    """Read a small flat list; discovery never downloads video media."""
    import yt_dlp
    url = _listing_url(channel, platform)
    if not url:
        return []
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist",
            "playlistend": LIST_LIMIT, "ignoreerrors": True, "socket_timeout": 15, "noplaylist": False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    entries = info.get("entries") if isinstance(info, dict) else None
    return [e for e in (entries or []) if isinstance(e, dict) and not e.get("is_live")]


def _state_path(cid: str) -> Path:
    return creators.root(cid) / "upload_state.json"


def _read_state(cid: str) -> dict:
    try:
        value = json.loads(_state_path(cid).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(cid: str, state: dict):
    path = _state_path(cid)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    tmp.replace(path)


def _scan_channel(c: dict, platform: str, channel: str):
    entries = _list_uploads(channel, platform)
    ids = [_entry_id(e) for e in entries if _entry_id(e)]
    if not ids:
        return
    with _state_lock:
        state = _read_state(c["id"])
        previous = state.get(platform) or {}
        if previous.get("channel") != channel or not previous.get("initialized"):
            state[platform] = {"channel": channel, "initialized": True, "seen": ids[:100],
                               "checked_at": time.time()}
            _write_state(c["id"], state)
            creators.log(c["id"], f"Upload monitor initialized for {platform.title()}; existing videos were skipped")
            return
        seen = set(previous.get("seen") or [])
        existing_jobs = jobs.list_jobs()
        for entry in _new_entries(entries, seen):
            ident = _entry_id(entry)
            url = _entry_url(entry, platform)
            if not url:
                continue
            title = str(entry.get("title") or "New creator upload")[:160]
            # Also check the durable job history in case the process stopped after creating a job
            # but before the upload cursor was saved.
            already_queued = any(j.get("creator") == c["id"] and
                                 (j.get("source") or {}).get("url") == url for j in existing_jobs)
            if not already_queued:
                job = jobs.create({"type": "url", "url": url, "name": title}, {}, creator=c["id"], kind="video")
                existing_jobs.append(job)
                creators.log(c["id"], f"New {platform.title()} upload detected: {title}; clipping queued")
                alerts.notify(f"{c['name']} uploaded a new video: {title}. Clipeer started making clips.")
            seen.add(ident)
            state[platform] = {"channel": channel, "initialized": True, "seen": list(seen)[-100:],
                               "checked_at": time.time()}
            _write_state(c["id"], state)
        state[platform] = {"channel": channel, "initialized": True, "seen": list(seen)[-100:],
                           "checked_at": time.time()}
        _write_state(c["id"], state)


def scan_user(uid: str):
    with ctx.as_user(uid):
        for c in creators.all_creators():
            if not c.get("auto_uploads"):
                continue
            for platform, channel in (c.get("channels") or {}).items():
                try:
                    _scan_channel(c, platform, channel)
                except Exception as e:  # noqa: BLE001 - one unavailable channel must not stop other creators
                    creators.log(c["id"], f"Upload check failed on {platform.title()}: {str(e)[-160:]}")


def _loop():
    time.sleep(12)
    while True:
        started = time.time()
        try:
            from concurrent.futures import ThreadPoolExecutor
            if config.ACCOUNTS:
                ids = auth.user_ids()
                if ids:
                    with ThreadPoolExecutor(max_workers=min(8, len(ids)), thread_name_prefix="uploads") as pool:
                        list(pool.map(scan_user, ids))
            else:
                scan_user("local")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(max(15, POLL_SECONDS - (time.time() - started)))


def start():
    global _started
    with _state_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="creator-upload-monitor", daemon=True).start()
