from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
FPS = 12

PALETTES = [
    ((27, 42, 34), (14, 20, 17)),
    ((42, 31, 20), (18, 14, 10)),
    ((20, 34, 42), (10, 16, 20)),
    ((36, 24, 40), (16, 12, 18)),
    ((26, 36, 24), (12, 16, 12)),
    ((34, 32, 24), (16, 16, 12)),
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:6]


def _parse_start(timecode: str | None) -> float:
    if not timecode:
        return 0.0
    import re

    m = re.search(r"(\d+(?:\.\d+)?)", str(timecode))
    return float(m.group(1)) if m else 0.0


def _scene_at(scenes: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    if not scenes:
        return None
    chosen = scenes[0]
    for s in scenes:
        if t >= _parse_start(s.get("timecode")):
            chosen = s
    return chosen


def _draw_frame(scene: dict[str, Any] | None, t: float, duration: float) -> np.ndarray:
    idx = int((scene or {}).get("index") or 1)
    top, bottom = PALETTES[(idx - 1) % len(PALETTES)]
    img = Image.new("RGB", (W, H), bottom)
    draw = ImageDraw.Draw(img)

    # vertical gradient
    for y in range(H):
        r = y / max(1, H - 1)
        color = tuple(int(top[i] * (1 - r) + bottom[i] * r) for i in range(3))
        draw.line([(0, y), (W, y)], fill=color)

    # vignette-ish dark bottom for captions
    draw.rectangle([0, int(H * 0.55), W, H], fill=(8, 10, 9))

    # progress bar
    prog = 0.0 if duration <= 0 else min(1.0, t / duration)
    draw.rounded_rectangle([28, 28, W - 28, 36], radius=4, fill=(255, 255, 255, 40))
    draw.rounded_rectangle([28, 28, 28 + int((W - 56) * prog), 36], radius=4, fill=(226, 168, 74))

    role = str((scene or {}).get("role") or "shorts").upper()
    cut = str((scene or {}).get("cut") or "")
    badge_font = _font(22)
    draw.rounded_rectangle([28, 52, 28 + 18 + int(draw.textlength(role, font=badge_font)), 88], radius=16, fill=(0, 0, 0))
    draw.text((40, 58), role, font=badge_font, fill=(226, 168, 74))
    if cut:
        draw.text((W - 28 - draw.textlength(cut, font=badge_font), 58), cut, font=badge_font, fill=(170, 176, 168))

    caption = str((scene or {}).get("on_screen_text") or (scene or {}).get("narration") or "Shorts")
    title_font = _font(54)
    lines = _wrap(draw, caption, title_font, W - 100)
    y = int(H * 0.62)
    for line in lines:
        tw = draw.textlength(line, font=title_font)
        draw.text(((W - tw) / 2, y), line, font=title_font, fill=(246, 242, 233))
        y += 64

    visual = str((scene or {}).get("visual") or "")
    if visual:
        small = _font(24)
        vlines = _wrap(draw, visual, small, W - 120)
        y += 12
        for line in vlines[:3]:
            tw = draw.textlength(line, font=small)
            draw.text(((W - tw) / 2, y), line, font=small, fill=(170, 176, 168))
            y += 32

    # subtle center mark / "lens"
    cx, cy = W // 2, int(H * 0.38)
    draw.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], outline=(226, 168, 74), width=3)
    draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(226, 168, 74))

    return np.asarray(img)


def _mux_audio(silent_mp4: Path, audio_path: Path, out_mp4: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(silent_mp4),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_mp4.exists():
        raise RuntimeError(proc.stderr[-500:] if proc.stderr else "ffmpeg mux failed")


def render_shorts_mp4(
    *,
    job_dir: Path,
    script: dict[str, Any],
    audio_path: Path,
    duration_seconds: int,
) -> str:
    """
    9:16 gerçek MP4 üretir (caption + sahne geçişleri + ses).
    Dönüş: dosya adı (job_dir içinde), örn. video.mp4
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes = list(script.get("scenes") or [])
    duration = max(3.0, float(duration_seconds or 15))
    # Ses daha uzunsa videoyu sese yaklaştır
    n_frames = max(1, int(duration * FPS))

    silent = job_dir / "_silent.mp4"
    out = job_dir / "video.mp4"

    writer = imageio.get_writer(
        str(silent),
        fps=FPS,
        codec="libx264",
        quality=7,
        macro_block_size=1,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )
    try:
        for i in range(n_frames):
            t = i / FPS
            frame = _draw_frame(_scene_at(scenes, t), t, duration)
            writer.append_data(frame)
    finally:
        writer.close()

    if audio_path.exists():
        try:
            _mux_audio(silent, audio_path, out)
            silent.unlink(missing_ok=True)
        except Exception:
            # mux olmasa bile oynatılabilir video kalsın
            if silent.exists():
                silent.replace(out)
    else:
        silent.replace(out)

    return "video.mp4"
