"""Turns a time range into a rendered clip.

The renderer accepts the original ``style``/``layout`` options as well as a
validated ``render`` object.  Keeping the normalization here means callers
can safely pass old saved jobs and newer editor configurations alike.
"""
from dataclasses import dataclass
import re
import shutil
import subprocess
from pathlib import Path

from . import config
from .media import NO_WINDOW, run

W, H = config.OUT_W, config.OUT_H

# ASS colours are &HBBGGRR. `size` is the ASS font size (line height); _Font turns it into real pixels.
STYLES = {
    "bounce": {"label": "Bounce", "font": "Poppins ExtraBold", "size": 132, "base": "FFFFFF", "active": "00F0FF",
               "strong": "FFFFFF", "outline": 7, "pop": 112, "upper": True, "per": 3},
    "hype": {"label": "Hype", "font": "Anton", "size": 152, "base": "FFFFFF", "active": "3C3CFF",
             "strong": "00D7FF", "outline": 7, "pop": 114, "upper": True, "per": 2},
    "clean": {"label": "Clean", "font": "Poppins ExtraBold", "size": 100, "base": "FFFFFF", "active": "6BD7FF",
              "strong": "FFFFFF", "outline": 5, "pop": 106, "upper": False, "per": 4},
}
HOOK = {"font": "Poppins ExtraBold", "size": 96, "ink": "14100E", "box": "FFFFFF", "pad_x": 36, "pad_y": 22, "radius": 26,
        "max_w": 900}
FONT_FILES = {"Poppins ExtraBold": "Poppins-ExtraBold.ttf", "Anton": "Anton-Regular.ttf", "Archivo Black": "ArchivoBlack-Regular.ttf"}
CAP_MAX_W = 960   # captions never run wider than this, whatever is said


class _Font:
    """Measures text exactly as the renderer will draw it, so every word can be placed by hand: the highlighted
    word can grow without pushing its neighbours, and the heading box fits its text."""
    _cache: dict = {}

    def __init__(self, name):
        import struct
        path = Path(__file__).resolve().parent / "fonts" / FONT_FILES.get(name, FONT_FILES["Poppins ExtraBold"])
        d = path.read_bytes()
        tables = {}
        for i in range(struct.unpack(">H", d[4:6])[0]):
            tag, _, off, _ = struct.unpack(">4sIII", d[12 + 16 * i: 28 + 16 * i])
            tables[tag] = off
        self.upm = struct.unpack(">H", d[tables[b"head"] + 18: tables[b"head"] + 20])[0]
        o = tables[b"OS/2"]
        self.asc, self.desc = struct.unpack(">HH", d[o + 74: o + 78])      # what the renderer sizes the font by
        self.cap = struct.unpack(">h", d[o + 88: o + 90])[0] or int(self.upm * 0.7)
        self.path = str(path)
        self._pil = {}

    @classmethod
    def get(cls, name):
        if name not in cls._cache:
            cls._cache[name] = cls(name)
        return cls._cache[name]

    def em(self, size):
        return size * self.upm / (self.asc + self.desc)

    def width(self, text, size):
        """Pixels wide at this ASS size."""
        try:
            from PIL import ImageFont
            if "f" not in self._pil:
                self._pil["f"] = ImageFont.truetype(self.path, 200)
            return self._pil["f"].getlength(text) * self.em(size) / 200
        except Exception:  # noqa: BLE001 - no measuring library: a fair estimate keeps clips rendering
            return len(text) * self.em(size) * 0.62

    def cap_shift(self, size):
        """How far below the anchor the middle of a capital letter sits when text is centred on a point."""
        return ((self.asc - self.desc) / 2 - self.cap / 2) * size / (self.asc + self.desc)


CAPTION_LEAD = 0.0  # measured: word stamps are within 0.15 s of the voice, so no shift is needed
def install_fonts():
    """Copy the bundled caption fonts next to the data, so captions look the same on every machine and server."""
    src = Path(__file__).resolve().parent / "fonts"
    for f in src.glob("*.ttf"):
        if not (config.FONTS_DIR / f.name).exists():
            shutil.copyfile(f, config.FONTS_DIR / f.name)


LAYOUTS = {"blur": "Full frame + blurred fill", "zoom": "Zoomed in + blurred fill", "crop": "Fill the screen (centre crop)",
           "split-screen": "Split screen", "gaming-facecam": "Gaming facecam", "podcast": "Podcast"}
ASPECTS = {"vertical": (1080, 1920), "9:16": (1080, 1920), "square": (1080, 1080), "1:1": (1080, 1080),
           "landscape": (1920, 1080), "16:9": (1920, 1080)}
CAPTION_POSITIONS = {"top", "center", "bottom"}


@dataclass(frozen=True)
class RenderConfig:
    """Safe, serializable render settings used by the layout phase."""
    aspect: str = "vertical"
    layout: str = "blur"
    background: str = "blur"
    video_x: float = 0.5
    video_y: float = 0.5
    video_scale: float = 1.0
    facecam_x: float = 0.78
    facecam_y: float = 0.78
    facecam_scale: float = 0.28
    caption_position: str = "bottom"
    caption_font: str = "Poppins ExtraBold"
    caption_size: int | None = None
    caption_color: str | None = None
    caption_active_color: str | None = None
    caption_background: str | None = None
    caption_outline: int | None = None
    preview: bool = False


def validate_render_config(value=None, *, legacy=None) -> dict:
    """Normalize and validate a render configuration without mutating input.

    Unknown keys are ignored for forward compatibility; malformed known values
    are rejected, while a non-object is rejected.
    """
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Render configuration must be an object.")
    if legacy:
        value = {**legacy, **value}
    out = dict(RenderConfig().__dict__)
    aliases = {"format": "aspect", "caption": "caption_position", "font": "caption_font"}
    for k, v in value.items():
        k = aliases.get(k, k)
        if k in out:
            out[k] = v
    aspect = str(out["aspect"]).lower()
    if aspect not in ASPECTS:
        raise ValueError("Unsupported render aspect.")
    layout = str(out["layout"]).lower()
    if layout not in LAYOUTS:
        raise ValueError("Unsupported render layout.")
    background = str(out["background"]).lower()
    if background not in {"blur", "solid", "none"}:
        raise ValueError("Unsupported render background.")
    pos = str(out["caption_position"]).lower()
    if pos not in CAPTION_POSITIONS:
        raise ValueError("Unsupported caption position.")
    for k in ("video_x", "video_y", "facecam_x", "facecam_y"):
        out[k] = max(0.0, min(1.0, float(out[k])))
    for k in ("video_scale", "facecam_scale"):
        out[k] = max(0.05, min(4.0, float(out[k])))
    if out["caption_size"] is not None:
        out["caption_size"] = max(24, min(240, int(float(out["caption_size"]))))
    if out["caption_outline"] is not None:
        out["caption_outline"] = max(0, min(30, int(float(out["caption_outline"]))))
    for k in ("caption_color", "caption_active_color", "caption_background"):
        if out[k] is not None:
            s = str(out[k]).lstrip("#")
            if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
                raise ValueError("Caption colours must be six-digit hex values.")
            out[k] = s.upper()
    out["aspect"], out["layout"], out["background"], out["caption_position"] = aspect, layout, background, pos
    out["caption_font"] = str(out["caption_font"]) if str(out["caption_font"]) in FONT_FILES else RenderConfig.caption_font
    out["preview"] = bool(out["preview"])
    return out


def preview_config(value=None, src_w=1920, src_h=1080) -> dict:
    """Return layout metadata for an editor preview without invoking FFmpeg."""
    rc = validate_render_config(value)
    width, height = ASPECTS[rc["aspect"]]
    layout, fg_h, hook_y, cap_y = geometry(src_w, src_h, rc["layout"], width, height)
    return {"config": rc, "width": width, "height": height, "foreground_height": fg_h,
            "hook_y": hook_y, "caption_y": cap_y, "layout": layout}


def _ts(t):
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def _clean(text):
    return re.sub(r"[\x00-\x1f\x7f]+", " ", re.sub(r"[{}\\]", "", str(text))).strip()


def _key(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _groups(words, per):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= per or sum(len(x["w"]) for x in cur) + len(w["w"]) > 16
                    or w["s"] - cur[-1]["e"] > 0.45 or cur[-1]["w"][-1:] in ".?!"):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def geometry(src_w, src_h, layout, width=W, height=H):
    """Where the video sits in the 1080x1920 frame, and where hook and captions go."""
    if src_h >= src_w and layout != "crop":
        layout = "crop"  # already vertical or square: nothing to gain from a blurred fill
    if layout == "blur":
        fg_h = min(height, int(round(width * src_h / src_w / 2)) * 2)
    elif layout == "zoom":
        fg_h = int(height * 0.52)
    else:
        fg_h = H
    top = (height - fg_h) // 2
    if layout == "crop":
        return layout, fg_h, int(height * .16), int(height * .72)
    return layout, fg_h, max(int(height * .12), top - int(height * .1)), min(int(height * .86), top + fg_h + int(height * .1))


def _hook_events(hook, dur, y, width=W):
    """The heading: dark text in a white rounded box that fits it, on one line or two balanced ones."""
    f, size = _Font.get(HOOK["font"]), HOOK["size"]
    words = hook.split()
    if not words:
        return []
    lines = [" ".join(words)]
    if f.width(lines[0], size) > HOOK["max_w"] and len(words) > 1:      # two lines, split where they come out most even
        cut = min(range(1, len(words)), key=lambda i: max(f.width(" ".join(words[:i]), size), f.width(" ".join(words[i:]), size)))
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
    widest = max(f.width(l, size) for l in lines)
    if widest > HOOK["max_w"]:
        size = max(40, int(size * HOOK["max_w"] / widest))
        widest = max(f.width(l, size) for l in lines)
    line_h = f.em(size) * 1.16
    bw, bh = widest + 2 * HOOK["pad_x"], line_h * len(lines) + 2 * HOOK["pad_y"]
    x0, y0, r = (width - bw) / 2, y - bh / 2, min(HOOK["radius"], bh / 2)
    x1, y1 = x0 + bw, y0 + bh
    n = lambda v: f"{v:.0f}"                                                         # noqa: E731
    box = (f"m {n(x0 + r)} {n(y0)} l {n(x1 - r)} {n(y0)} b {n(x1)} {n(y0)} {n(x1)} {n(y0)} {n(x1)} {n(y0 + r)} "
           f"l {n(x1)} {n(y1 - r)} b {n(x1)} {n(y1)} {n(x1)} {n(y1)} {n(x1 - r)} {n(y1)} "
           f"l {n(x0 + r)} {n(y1)} b {n(x0)} {n(y1)} {n(x0)} {n(y1)} {n(x0)} {n(y1 - r)} "
           f"l {n(x0)} {n(y0 + r)} b {n(x0)} {n(y0)} {n(x0)} {n(y0)} {n(x0 + r)} {n(y0)}")
    span = f"{_ts(0)},{_ts(dur)}"
    ev = [f"Dialogue: 3,{span},Hook,,0,0,0,,{{\\an7\\pos(0,0)\\fad(160,0)\\c&H{HOOK['box']}&\\p1}}{box}{{\\p0}}"]
    for i, line in enumerate(lines):
        cy = y - line_h * (len(lines) - 1) / 2 + i * line_h - f.cap_shift(size)
        ev.append(f"Dialogue: 4,{span},Hook,,0,0,0,,{{\\an5\\pos({width // 2},{cy:.0f})\\fad(160,0)\\fs{size}}}{line}")
    return ev


def build_ass(words, start, end, hook, style_name, highlight, hook_y, cap_y, render=None) -> str:
    st = STYLES.get(style_name, STYLES["bounce"])
    rc = validate_render_config(render)
    width, height = ASPECTS[rc["aspect"]]
    st = dict(st)
    if rc["caption_font"]:
        st["font"] = rc["caption_font"]
    for key, target in (("caption_size", "size"), ("caption_color", "base"),
                        ("caption_active_color", "active"), ("caption_outline", "outline")):
        if rc[key] is not None:
            st[target] = rc[key]
    if rc["caption_position"] == "top":
        cap_y = int(height * .22)
    elif rc["caption_position"] == "center":
        cap_y = int(height * .54)
    else:
        cap_y = int(height * .78)
    words = [dict(w, s=w["s"] - CAPTION_LEAD, e=w["e"] - CAPTION_LEAD) for w in words]
    strong = {_key(h) for h in highlight if _key(h)}
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},&H00{st['base']},&H00{st['base']},&H00000000,&H00{rc['caption_background'] or '000000'},0,0,0,0,100,100,0,0,1,{st['outline']},0,5,0,0,0,1
Style: Hook,{HOOK['font']},{HOOK['size']},&H00{HOOK['ink']},&H00{HOOK['ink']},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dur = end - start
    # Existing hook geometry is kept for vertical clips; other formats use a
    # proportional position so the same API works for every aspect.
    hook_y = int(hook_y * height / H)
    cap_y = int(cap_y)
    ev = _hook_events(_clean(hook), dur, hook_y, width)
    f = _Font.get(st["font"])
    inside = [dict(w, w=_clean(w["w"])) for w in words if w["s"] >= start - 0.05 and w["s"] < end]
    inside = [w for w in inside if w["w"]]
    groups = _groups(inside, st["per"])
    for gi, g in enumerate(groups):
        g_start = max(0.0, g[0]["s"] - start)
        g_end = min(g[-1]["e"] + 0.25, groups[gi + 1][0]["s"] if gi + 1 < len(groups) else end) - start
        if g_end - g_start < 0.02:
            continue
        texts = []
        for x in g:
            t = re.sub(r"[.,;:]+$", "", x["w"])
            texts.append(t.upper() if st["upper"] else t)
        size = st["size"]
        gap = f.width("n n", size) - 2 * f.width("n", size) + (2 * st["outline"] + 6) * size / st["size"]   # a space, plus room for both outlines
        total = sum(f.width(t, size) for t in texts) + gap * (len(texts) - 1)
        if total > CAP_MAX_W:                                  # a long phrase: shrink it to fit, never run off the frame
            size = max(36, int(size * CAP_MAX_W / total))
            gap = f.width("n n", size) - 2 * f.width("n", size) + (2 * st["outline"] + 6) * size / st["size"]   # a space, plus room for both outlines
            total = sum(f.width(t, size) for t in texts) + gap * (len(texts) - 1)
        cy = cap_y - f.cap_shift(size)
        x = (width - total) / 2
        p = st["pop"]
        for i, (w, t) in enumerate(zip(g, texts)):
            wd = f.width(t, size)
            p = max(104, min(st["pop"], 100 + int(2200 / max(wd, 1))))   # long words grow less, so they never touch their neighbours
            pos = f"\\an5\\pos({x + wd / 2:.0f},{cy:.0f})\\fs{size}"
            x += wd + gap
            a = max(g_start, w["s"] - start)
            b = (g[i + 1]["s"] - start) if i + 1 < len(g) else g_end
            base = st["strong"] if _key(w["w"]) in strong else st["base"]
            if a - g_start >= 0.02:                                                   # waiting to be said
                ev.append(f"Dialogue: 1,{_ts(g_start)},{_ts(a)},Cap,,0,0,0,,{{{pos}\\c&H{base}&}}{t}")
            if b - a >= 0.02:                                                         # being said: colour and a quick pop, in front
                ev.append(f"Dialogue: 2,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{{{pos}\\c&H{st['active']}&\\fscx94\\fscy94"
                          f"\\t(0,90,\\fscx{p}\\fscy{p})\\t(90,200,\\fscx{p - 5}\\fscy{p - 5})}}{t}")
            if g_end - b >= 0.02:                                                     # said
                ev.append(f"Dialogue: 1,{_ts(b)},{_ts(g_end)},Cap,,0,0,0,,{{{pos}\\c&H{base}&\\fscx{p - 5}\\fscy{p - 5}"
                          f"\\t(0,90,\\fscx100\\fscy100)}}{t}")
    return head + "\n".join(ev) + "\n"


def _filter(layout, fg_h, render=None):
    rc = validate_render_config(render)
    width, height = ASPECTS[rc["aspect"]]
    if rc["background"] == "none":
        background = f"color=c=black:s={width}x{height}:r={config.OUT_FPS}[bg];"
    elif rc["background"] == "solid":
        background = f"color=c=black:s={width}x{height}:r={config.OUT_FPS}[bg];"
    else:
        background = (f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
                      f"scale={width}:{height},eq=brightness=-0.14:saturation=1.15[bg];")
    if layout == "split-screen":
        return (f"[0:v]fps={config.OUT_FPS},split=2[a][b];"
                f"[a]scale={width}:{height // 2}:force_original_aspect_ratio=increase,crop={width}:{height // 2}[top];"
                f"[b]scale={width}:{height // 2}:force_original_aspect_ratio=increase,crop={width}:{height // 2}[bottom];"
                f"[top][bottom]vstack,setsar=1[v0];")
    if layout == "podcast":
        return (f"[0:v]fps={config.OUT_FPS},scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1[v0];")
    if layout == "gaming-facecam":
        fx, fy, fs = rc["facecam_x"], rc["facecam_y"], rc["facecam_scale"]
        return (f"[0:v]fps={config.OUT_FPS},split=3[a][b][c];{background}"
                f"[b]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[fg];"
                f"[c]scale={width}*{fs:.4f}:{height}*{fs:.4f}:force_original_aspect_ratio=increase,"
                f"crop={width}*{fs:.4f}:{height}*{fs:.4f}[face];"
                f"[bg][fg]overlay=0:0[base];[base][face]overlay=x=(W-w)*{fx:.4f}:y=(H-h)*{fy:.4f},setsar=1[v0];")
    if layout == "crop":
        return f"[0:v]fps={config.OUT_FPS},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[v0];"
    sx, sy, ss = rc["video_x"], rc["video_y"], rc["video_scale"]
    return (f"[0:v]fps={config.OUT_FPS},split=2[a][b];" + background +
            f"[b]scale={width}*{ss:.4f}:{fg_h}*{ss:.4f}:force_original_aspect_ratio=increase,"
            f"crop={width}*{ss:.4f}:{fg_h}*{ss:.4f}[fg];"
            f"[bg][fg]overlay=x=(W-w)*{sx:.4f}:y=(H-h)*{sy:.4f},setsar=1[v0];")


_qsv_ok = None


def render_clip(src: Path, out_dir: Path, name: str, clip: dict, words: list, src_w: int, src_h: int) -> dict:
    """Writes <name>.mp4, <name>.jpg and <name>.ass into out_dir. Returns file names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = clip["start"], clip["end"]
    render = validate_render_config(clip.get("render"), legacy=clip)
    width, height = ASPECTS[render["aspect"]]
    layout, fg_h, hook_y, cap_y = geometry(src_w, src_h, render["layout"], width, height)
    ass = build_ass(words, start, end, clip.get("hook", ""), clip.get("style", "bounce"),
                    clip.get("highlight_words", []), hook_y, cap_y, render)
    # The clip is made in a short work folder and moved into place afterwards. The caption step of ffmpeg cannot
    # open files whose full path is longer than 260 characters on Windows, which a data folder deep inside other
    # folders easily reaches. Inside the work folder every name is short and relative (a drive colon would also
    # break the filter syntax).
    work = config.TMP_DIR / f"render-{name}-{__import__('os').urandom(5).hex()}"
    work.mkdir(parents=True, exist_ok=False)
    try:
        return _render_in(work, src, out_dir, name, start, end, layout, fg_h, ass, render)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _render_in(work: Path, src: Path, out_dir: Path, name: str, start, end, layout, fg_h, ass: str, render=None) -> dict:
    global _qsv_ok
    (work / f"{name}.ass").write_text(ass, encoding="utf-8")
    (work / "f").mkdir()
    for f in config.FONTS_DIR.glob("*.ttf"):
        shutil.copyfile(f, work / "f" / f.name)
    rc = validate_render_config(render)
    width, height = ASPECTS[rc["aspect"]]
    fc = _filter(layout, fg_h, rc) + f"[v0]ass={name}.ass:fontsdir=f[v]"
    base = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", str(src),
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", "-pix_fmt"]
    encoders = []
    if _qsv_ok is not False:
        encoders.append(("qsv", ["nv12", "-c:v", "h264_qsv", "-global_quality", "23", "-preset", "fast"]))
    encoders.append(("x264", ["yuv420p", "-c:v", "libx264", "-crf", "21", "-preset", "veryfast"]))
    err = None
    for label, enc in encoders:
        p = subprocess.run(base + enc + [f"{name}.mp4"], cwd=work, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=NO_WINDOW, timeout=1800)
        if p.returncode == 0:
            if label == "qsv":
                _qsv_ok = True
            break
        err = p.stderr[-1200:]
        if label == "qsv":
            _qsv_ok = False
    else:
        raise RuntimeError(f"Render failed: {err}")
    cover_t = min(1.2, (end - start) / 2)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cover_t:.2f}", "-i", f"{name}.mp4", "-frames:v", "1",
         "-q:v", "3", f"{name}.jpg"], cwd=work)
    for ext in ("mp4", "jpg", "ass"):
        shutil.move(str(work / f"{name}.{ext}"), str(out_dir / f"{name}.{ext}"))
    return {"file": f"{name}.mp4", "cover": f"{name}.jpg", "layout": layout, "render": rc,
            "width": width, "height": height}
