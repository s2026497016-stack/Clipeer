"""User-scoped render presets.

Presets are intentionally kept outside job files so changing a preset never
changes an existing clip or saved project.
"""
import json
import re
import secrets
import threading
import time

from . import config, ctx, render

_lock = threading.RLock()


def _file():
    d = config.user_dir(ctx.uid())
    d.mkdir(parents=True, exist_ok=True)
    return d / "render-presets.json"


def _load():
    try:
        value = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _save(value):
    f = _file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1), encoding="utf-8")
    tmp.replace(f)
    ctx.bump()


def _name(value):
    value = re.sub(r"\s+", " ", str(value or "")).strip()[:80]
    if not value:
        raise ValueError("Give the preset a name.")
    return value


def list_presets():
    return [{"id": p["id"], "name": p["name"], "render": p["render"], "created": p["created"], "updated": p["updated"]}
            for p in _load()]


def create(name, value):
    render_value = render.validate_render_config(value)
    now = time.time()
    preset = {"id": secrets.token_hex(8), "name": _name(name), "render": render_value,
              "created": now, "updated": now}
    with _lock:
        presets = _load()
        if any(p.get("name", "").casefold() == preset["name"].casefold() for p in presets):
            raise ValueError("A preset with that name already exists.")
        presets.append(preset)
        _save(presets)
    return preset


def remove(pid):
    with _lock:
        presets = _load()
        kept = [p for p in presets if p.get("id") != pid]
        if len(kept) == len(presets):
            raise KeyError(pid)
        _save(kept)
