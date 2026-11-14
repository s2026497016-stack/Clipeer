"""Focused checks for the new render and publishing safety primitives."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="clipeer-features-")
os.environ["PEAKCUT_PUBLISHING_KEY"] = "feature-test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import ctx, presets, render
from studio.publishing.base import decrypt_token, encrypt_token


fails = []


def check(name, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   got {got!r}"))
    if not ok:
        fails.append(name)


check("all supported aspects validate", [render.validate_render_config({"aspect": x})["aspect"]
      for x in ("vertical", "square", "landscape")], ["vertical", "square", "landscape"])
check("custom caption and facecam settings validate",
      render.validate_render_config({"aspect": "square", "layout": "gaming-facecam",
                                     "caption_position": "top", "caption_size": 88,
                                     "facecam_x": 0.2})["facecam_x"], 0.2)
check("preview returns target dimensions", render.preview_config({"aspect": "landscape"})["width"], 1920)
try:
    render.validate_render_config({"aspect": "bad"})
except ValueError:
    check("invalid aspect is rejected", True)
else:
    check("invalid aspect is rejected", False)

with ctx.as_user("feature_user"):
    p = presets.create("Shorts", {"aspect": "square", "layout": "blur"})
    check("preset is user scoped", presets.list_presets()[0]["name"], "Shorts")
    presets.remove(p["id"])
    check("preset removal works", presets.list_presets(), [])

sealed = encrypt_token("refresh-token")
check("publishing token is encrypted", sealed.startswith("enc:v2:"))
check("publishing token decrypts", decrypt_token(sealed), "refresh-token")

print("ALL PASSED" if not fails else f"{len(fails)} failed")
raise SystemExit(1 if fails else 0)
