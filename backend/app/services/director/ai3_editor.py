"""AI 3 — Kurgu / Birleştirici (FFmpeg + sahne görselleri + ses + efektler)."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Yüksek çözünürlük: 1080×1920 (Full HD 9:16)
W, H = 1080, 1920
FPS = 24
TRANSITION_DURATION = 0.35  # saniye cinsinden geçiş süresi
ZOOM_INTENSITY = 0.06       # zoom-in efekt şiddeti


def _font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\impact.ttf",
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


def _scene_index_at(scenes: list[dict[str, Any]], t: float) -> int:
    """Verilen zamandaki sahne index'ini döndür."""
    if not scenes:
        return 0
    idx = 0
    for i, s in enumerate(scenes):
        if t >= _parse_start(s.get("timecode")):
            idx = i
    return idx


def _load_bg(job_dir: Path, scene: dict[str, Any] | None) -> Image.Image:
    if scene and scene.get("image"):
        p = job_dir / str(scene["image"])
        if p.exists():
            img = Image.open(p).convert("RGB")
            return img.resize((W, H), Image.Resampling.LANCZOS)
    # Fallback gradient
    bg = Image.new("RGB", (W, H), (14, 18, 16))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        r = y / max(1, H - 1)
        c = tuple(int(14 * (1 - r) + 22 * r) for _ in range(3))
        draw.line([(0, y), (W, y)], fill=c)
    return bg


def _apply_zoom(img: Image.Image, t: float, scene_start: float, scene_duration: float) -> Image.Image:
    """Sahne içinde yavaş zoom-in efekti (Ken Burns)."""
    if scene_duration <= 0:
        return img
    progress = min(1.0, (t - scene_start) / scene_duration)
    # progress 0'dan 1'e → zoom 1.0'dan (1+ZOOM_INTENSITY)'e
    scale = 1.0 + (ZOOM_INTENSITY * progress)
    new_w = int(W * scale)
    new_h = int(H * scale)
    zoomed = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    # ortadan kırp
    left = (new_w - W) // 2
    top = (new_h - H) // 2
    return zoomed.crop((left, top, left + W, top + H))


def _crossfade(frame1: np.ndarray, frame2: np.ndarray, alpha: float) -> np.ndarray:
    """İki kare arasında crossfade (alpha: 0→1)."""
    return ((1.0 - alpha) * frame1 + alpha * frame2).astype(np.uint8)


def _draw_animated_caption(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    progress: float,
    color: tuple = (246, 242, 233),
    shadow: bool = True,
) -> int:
    """Kinetik caption: kelime kelime animasyonlu görüntüleme."""
    words = text.split()
    if not words:
        return y

    total_chars = len(text)
    visible_chars = int(total_chars * min(1.0, progress))
    visible_text = ""
    count = 0
    for w in words:
        for _ in w:
            if count >= visible_chars:
                break
            count += 1
        else:
            visible_text += w + " "
            continue
        break

    visible_text = visible_text.strip()
    if not visible_text:
        return y

    lines: list[str] = []
    cur = ""
    for w in visible_text.split():
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    line_h = int(font.size * 1.25)
    for line in lines[:3]:
        tw = draw.textlength(line, font=font)
        lx = x + (max_width - tw) / 2

        if shadow:
            # Gölge
            draw.text((lx + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))

        # Ana metin
        draw.text((lx, y), line, font=font, fill=color)
        y += line_h

    return y


def _draw_neon_subtitle(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    progress: float,
) -> int:
    """Neon stil alt yazı — parlak kenarlı."""
    words = text.split()
    if not words:
        return y

    total_chars = sum(len(w) for w in words) + len(words) - 1
    visible_chars = int(total_chars * min(1.0, progress))
    visible_text = ""
    count = 0
    for w in words:
        for c in w:
            if count >= visible_chars:
                break
            visible_text += c
            count += 1
        else:
            visible_text += " "
            continue
        break
    visible_text = visible_text.strip()
    if not visible_text:
        return y

    lines: list[str] = []
    cur = ""
    for w in visible_text.split():
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    line_h = int(font.size * 1.3)
    for line in lines[:3]:
        tw = draw.textlength(line, font=font)
        lx = x + (max_width - tw) / 2

        # Neon parlaması (dış katmanlar)
        glow_color = (226, 168, 74)
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((lx + ox, y + oy), line, font=font, fill=(*glow_color, 60))

        # Orta katman
        draw.text((lx + 1, y + 1), line, font=font, fill=(60, 60, 60))
        # Ana metin
        draw.text((lx, y), line, font=font, fill=(255, 255, 255))
        y += line_h

    return y


def _compose_frame(
    job_dir: Path,
    scene: dict[str, Any] | None,
    t: float,
    duration: float,
    scene_start: float = 0.0,
    scene_duration: float = 3.0,
) -> np.ndarray:
    base = _load_bg(job_dir, scene)
    # Kenar karartma (sinematik letterbox)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    bar_h = int(H * 0.04)
    od.rectangle([0, 0, W, bar_h], fill=(0, 0, 0, 140))
    od.rectangle([0, int(H * 0.88), W, H], fill=(0, 0, 0, 180))

    # Alt caption alanı karartma
    od.rectangle([0, int(H * 0.55), W, int(H * 0.88)], fill=(0, 0, 0, 100))

    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    # Zoom efekti uygula
    base = _apply_zoom(base, t, scene_start, scene_duration)

    draw = ImageDraw.Draw(base)

    # --- İlerleme çubuğu (ince, şık) ---
    prog = 0.0 if duration <= 0 else min(1.0, t / duration)
    bar_margin = int(W * 0.04)
    bar_y = int(H * 0.035)
    bar_h_px = 4
    bar_w = W - 2 * bar_margin

    draw.rounded_rectangle(
        [bar_margin, bar_y, bar_margin + bar_w, bar_y + bar_h_px],
        radius=2, fill=(255, 255, 255, 60),
    )
    # Gradient efektli progress
    filled_w = int(bar_w * prog)
    if filled_w > 0:
        # Daha kalın ve parlak
        draw.rounded_rectangle(
            [bar_margin, bar_y - 1, bar_margin + filled_w, bar_y + bar_h_px + 1],
            radius=3, fill=(226, 168, 74),
        )
        # Parlama noktası
        draw.rounded_rectangle(
            [bar_margin + filled_w - 4, bar_y - 2, bar_margin + filled_w + 2, bar_y + bar_h_px + 2],
            radius=4, fill=(255, 215, 100),
        )

    # --- Sahne etiketi (sol üst) ---
    role = str((scene or {}).get("role") or "scene").upper()
    bf = _font(22)
    role_w = int(draw.textlength(role, font=bf)) + 24
    draw.rounded_rectangle(
        [bar_margin, bar_y + 30, bar_margin + role_w, bar_y + 30 + 34],
        radius=17, fill=(0, 0, 0, 160),
    )
    draw.text((bar_margin + 12, bar_y + 34), role, font=bf, fill=(226, 168, 74))

    # --- Kinetik Caption (canlı altyazı) ---
    caption = str((scene or {}).get("on_screen_text") or (scene or {}).get("narration") or "")
    tf = _font(54)

    # Caption progress: her sahne için 0→1
    caption_prog = 0.0 if scene_duration <= 0 else min(1.0, (t - scene_start) / max(0.1, scene_duration * 0.8))

    caption_y = int(H * 0.68)
    _draw_animated_caption(
        draw, caption,
        x=int(W * 0.05), y=caption_y,
        max_width=int(W * 0.9),
        font=tf,
        progress=caption_prog,
        color=(246, 242, 233),
        shadow=True,
    )

    # --- Alt bilgi (cut type / transition) ---
    cut_type = str((scene or {}).get("cut") or "").upper()
    if cut_type:
        cf = _font(16)
        draw.text((W - bar_margin - draw.textlength(cut_type, font=cf), H - int(H * 0.08)),
                  cut_type, font=cf, fill=(160, 166, 158, 180))

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
        "-crf", "18",  # Daha yüksek kalite
        "-preset", "medium",
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
    """
    Sahne görselleri + caption + ses → video.mp4
    Yeni özellikler:
    - 1080×1920 Full HD
    - 24 FPS (akıcı)
    - Crossfade geçişleri
    - Ken Burns zoom efekti
    - Kinetik kelime animasyonu
    - Gelişmiş progress bar
    """
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
        quality=10,
        macro_block_size=1,
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",
            "-crf", "18",
        ],
    )
    prev_frame: np.ndarray | None = None

    try:
        for i in range(n_frames):
            t = i / FPS
            scene_obj = _scene_at(scenes, t)
            scene_idx = _scene_index_at(scenes, t)

            # Her sahnenin başlangıç ve bitiş zamanını bul
            scene_start = 0.0
            scene_end = duration
            if scenes:
                if scene_idx < len(scenes):
                    scene_start = _parse_start(scenes[scene_idx].get("timecode"))
                    if scene_idx + 1 < len(scenes):
                        scene_end = _parse_start(scenes[scene_idx + 1].get("timecode"))
                    else:
                        scene_end = duration

            scene_dur = scene_end - scene_start

            frame = _compose_frame(
                job_dir, scene_obj, t, duration,
                scene_start=scene_start, scene_duration=scene_dur,
            )

            # Crossfade geçişi
            if prev_frame is not None and scene_start > 0:
                time_since_transition = t - scene_start
                if time_since_transition < TRANSITION_DURATION:
                    alpha = time_since_transition / TRANSITION_DURATION
                    frame = _crossfade(prev_frame, frame, alpha)

            writer.append_data(frame)
            prev_frame = frame

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
        "resolution": f"{W}x{H}",
        "fps": FPS,
    }