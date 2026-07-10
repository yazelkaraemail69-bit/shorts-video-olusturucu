"""AI 3 — Kurgu / Birleştirici (FFmpeg + sahne görselleri + ses)."""

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


def _font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _parse_start(timecode: str | None) -> float:
    import re

    if not timecode:
        return 0.0
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


def _load_bg(job_dir: Path, scene: dict[str, Any] | None) -> Image.Image:
    if scene and scene.get("image"):
        p = job_dir / str(scene["image"])
        if p.exists():
            img = Image.open(p).convert("RGB")
            return img.resize((W, H), Image.Resampling.LANCZOS)
    return Image.new("RGB", (W, H), (14, 18, 16))


def _compose_frame(job_dir: Path, scene: dict[str, Any] | None, t: float, duration: float) -> np.ndarray:
    base = _load_bg(job_dir, scene)
    # Kenar karartma
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, int(H * 0.55), W, H], fill=(0, 0, 0, 150))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    prog = 0.0 if duration <= 0 else min(1.0, t / duration)
    draw.rounded_rectangle([24, 24, W - 24, 32], radius=4, fill=(255, 255, 255))
    draw.rounded_rectangle([24, 24, 24 + int((W - 48) * prog), 32], radius=4, fill=(226, 168, 74))

    role = str((scene or {}).get("role") or "scene").upper()
    bf = _font(20)
    draw.rounded_rectangle([24, 48, 24 + 20 + int(draw.textlength(role, font=bf)), 78], radius=14, fill=(0, 0, 0))
    draw.text((34, 52), role, font=bf, fill=(226, 168, 74))

    caption = str((scene or {}).get("on_screen_text") or (scene or {}).get("narration") or "")
    tf = _font(48)
    words = caption.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=tf) <= W - 80:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    y = int(H * 0.68)
    for line in lines[:4]:
        tw = draw.textlength(line, font=tf)
        draw.text(((W - tw) / 2, y), line, font=tf, fill=(246, 242, 233))
        y += 56

    return np.asarray(base)


def _mux(silent: Path, audio: Path, out: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", str(silent),
        "-i", str(audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(proc.stderr[-500:] if proc.stderr else "AI3 mux failed")


def run_editor_agent(
    *,
    job_dir: Path,
    script: dict[str, Any],
    audio_path: Path,
    duration_seconds: int,
) -> dict[str, Any]:
    """Sahne görselleri + caption + ses → video.mp4"""
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes = list(script.get("scenes") or [])
    duration = max(3.0, float(duration_seconds or 15))
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
            frame = _compose_frame(job_dir, _scene_at(scenes, t), t, duration)
            writer.append_data(frame)
    finally:
        writer.close()

    if audio_path.exists():
        try:
            _mux(silent, audio_path, out)
            silent.unlink(missing_ok=True)
        except Exception:
            if silent.exists():
                silent.replace(out)
    else:
        silent.replace(out)

    return {
        "agent": "AI3_editor",
        "video_file": "video.mp4",
        "path": str(out),
        "frames": n_frames,
        "duration": duration,
    }
