"""AI Thumbnail oluşturucu — AI2 görseli + metin bindirme."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

import imageio_ffmpeg

W, H = 1080, 1920  # 9:16 thumbnail (Short kapak)


def _font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _create_thumbnail_gradient(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    style: str = "cinematic",
) -> None:
    """Gradient overlay — thumbnail'ı daha çarpıcı yap."""
    style_overlays = {
        "cinematic": [(0, 0, 0, 0), (0, 0, 0, 180)],
        "punchy": [(226, 168, 74, 40), (0, 0, 0, 200)],
        "minimal": [(255, 255, 255, 20), (0, 0, 0, 150)],
        "egitici": [(0, 100, 200, 50), (0, 0, 30, 180)],
        "eglenceli": [(255, 200, 50, 60), (0, 0, 0, 160)],
        "hikaye": [(80, 40, 20, 80), (0, 0, 0, 200)],
    }
    overlay = style_overlays.get(style, style_overlays["cinematic"])
    top_color, bottom_color = overlay

    for y in range(h):
        r = y / max(1, h - 1)
        alpha = int(top_color[3] * (1 - r) + bottom_color[3] * r)
        color = tuple(
            int(top_color[i] * (1 - r) + bottom_color[i] * r) for i in range(3)
        )
        draw.line([(0, y), (w, y)], fill=(*color, alpha))


def _draw_thumbnail_accent(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    style: str = "cinematic",
) -> None:
    """Thumbnail'a görsel aksanlar ekle (çizgi, çerçeve, vurgu)."""
    accent_color = (226, 168, 74)  # Altın sarısı

    # Sol üst renk vurgusu
    draw.rectangle([0, 0, int(w * 0.05), int(h * 0.15)], fill=(*accent_color, 160))
    draw.rectangle([0, 0, int(w * 0.03), int(h * 0.12)], fill=(255, 215, 0))

    # Alt gradient çubuk
    for y in range(int(h * 0.75), h):
        r = (y - h * 0.75) / (h * 0.25)
        alpha = int(180 * r)
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    # İnce yatay çizgi (stil bağımsız)
    draw.rectangle(
        [int(w * 0.05), int(h * 0.72), int(w * 0.95), int(h * 0.72) + 2],
        fill=(*accent_color, 200),
    )


def generate_thumbnail(
    scene_image: Path | None,
    output_path: Path,
    title: str,
    subtitle: str = "",
    style: str = "cinematic",
    use_gradient: bool = True,
) -> Path:
    """
    Sahne görseli üzerine thumbnail oluştur.
    
    Args:
        scene_image: Kaynak görsel (None = gradient fallback)
        output_path: Çıktı yolu
        title: Ana başlık (2-3 kelime, büyük)
        subtitle: Alt başlık (5-8 kelime, küçük)
        style: Görsel stil
        use_gradient: Gradient overlay kullan
    
    Returns:
        Oluşturulan thumbnail yolu
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if scene_image and scene_image.exists():
        img = Image.open(scene_image).convert("RGBA")
        img = img.resize((W, H), Image.Resampling.LANCZOS)
    else:
        # Fallback gradient arkaplan
        img = Image.new("RGBA", (W, H), (14, 18, 16))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            r = y / max(1, H - 1)
            c = tuple(int(14 * (1 - r) + 30 * r) for _ in range(3))
            draw.line([(0, y), (W, y)], fill=(*c, 255))

    overlay_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay_layer)

    if use_gradient:
        _create_thumbnail_gradient(overlay_draw, W, H, style)
    _draw_thumbnail_accent(overlay_draw, W, H, style)

    img = Image.alpha_composite(img, overlay_layer)

    # Metin katmanı
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)

    # Ana başlık (büyük, bold)
    title_font = _font(96)
    title_lines = []
    cur = ""
    for w in title.split():
        trial = f"{cur} {w}".strip()
        if text_draw.textlength(trial, font=title_font) <= W - 120:
            cur = trial
        else:
            if cur:
                title_lines.append(cur)
            cur = w
    if cur:
        title_lines.append(cur)

    title_y = int(H * 0.55)
    for line in title_lines[:2]:
        tw = text_draw.textlength(line, font=title_font)
        tx = (W - tw) / 2
        # Gölge
        text_draw.text((tx + 4, title_y + 4), line, font=title_font, fill=(0, 0, 0, 200))
        # Ana metin
        text_draw.text((tx, title_y), line, font=title_font, fill=(246, 242, 233))
        title_y += 110

    # Alt başlık (küçük)
    if subtitle:
        sub_font = _font(42)
        sub_lines = []
        cur = ""
        for w in subtitle.split():
            trial = f"{cur} {w}".strip()
            if text_draw.textlength(trial, font=sub_font) <= W - 160:
                cur = trial
            else:
                if cur:
                    sub_lines.append(cur)
                cur = w
        if cur:
            sub_lines.append(cur)

        sub_y = title_y + 30
        for line in sub_lines[:2]:
            tw = text_draw.textlength(line, font=sub_font)
            tx = (W - tw) / 2
            text_draw.text((tx + 2, sub_y + 2), line, font=sub_font, fill=(0, 0, 0, 160))
            text_draw.text((tx, sub_y), line, font=sub_font, fill=(200, 206, 198))
            sub_y += 52

    # Stil etiketi (sağ alt)
    style_font = _font(28)
    style_label = style.upper()
    sw = text_draw.textlength(style_label, font=style_font)
    sx = W - 40 - sw
    sy = H - 80
    text_draw.text((sx + 2, sy + 2), style_label, font=style_font, fill=(0, 0, 0, 140))
    text_draw.text((sx, sy), style_label, font=style_font, fill=(226, 168, 74))

    img = Image.alpha_composite(img, text_layer)

    # Sonlandır
    final = img.convert("RGB")
    final.save(output_path, format="JPEG", quality=92)
    return output_path


def generate_thumbnail_grid(
    scene_images: list[Path],
    output_path: Path,
    title: str,
    style: str = "cinematic",
) -> Path:
    """
    Birden çok sahne görselinden kolaj thumbnail oluştur.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grid_w, grid_h = 1080, 1920
    collage = Image.new("RGBA", (grid_w, grid_h), (14, 18, 16))

    n = min(len(scene_images), 4)
    positions = [
        (20, 20, grid_w // 2 - 10, grid_h // 2 - 10),
        (grid_w // 2 + 10, 20, grid_w - 20, grid_h // 2 - 10),
        (20, grid_h // 2 + 10, grid_w // 2 - 10, grid_h - 20),
        (grid_w // 2 + 10, grid_h // 2 + 10, grid_w - 20, grid_h - 20),
    ]

    for i in range(n):
        if i < len(scene_images) and scene_images[i].exists():
            img = Image.open(scene_images[i]).convert("RGBA")
            x1, y1, x2, y2 = positions[i]
            area_w = x2 - x1
            area_h = y2 - y1
            img = img.resize((area_w, area_h), Image.Resampling.LANCZOS)
            collage.paste(img, (x1, y1))

    # Metin overlay (koyu gradient)
    overlay = Image.new("RGBA", (grid_w, grid_h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(int(grid_h * 0.55), grid_h):
        r = (y - grid_h * 0.55) / (grid_h * 0.45)
        alpha = int(200 * r)
        overlay_draw.line([(0, y), (grid_w, y)], fill=(0, 0, 0, alpha))

    collage = Image.alpha_composite(collage, overlay)

    # Başlık
    text_draw = ImageDraw.Draw(collage)
    tf = _font(72)
    tw = text_draw.textlength(title, font=tf)
    tx = (grid_w - tw) / 2
    text_draw.text((tx + 3, int(grid_h * 0.65) + 3), title, font=tf, fill=(0, 0, 0, 200))
    text_draw.text((tx, int(grid_h * 0.65)), title, font=tf, fill=(246, 242, 233))

    collage.convert("RGB").save(output_path, format="JPEG", quality=90)
    return output_path