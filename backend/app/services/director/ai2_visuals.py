"""AI 2 — Görsel Tasarımcı (OpenRouter image / Flux / DALL·E)."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.integration import resolve_openrouter_key, verify_openrouter

W_DEFAULT = 768
H_DEFAULT = 1344


def _font(size: int):
    for p in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _mock_scene_image(scene: dict[str, Any], out_path: Path, w: int, h: int) -> None:
    idx = int(scene.get("index") or 1)
    palettes = [
        ((30, 55, 45), (12, 18, 15)),
        ((55, 40, 22), (18, 12, 8)),
        ((28, 45, 60), (10, 16, 22)),
        ((50, 28, 48), (16, 10, 18)),
        ((35, 50, 30), (12, 16, 12)),
    ]
    top, bottom = palettes[(idx - 1) % len(palettes)]
    img = Image.new("RGB", (w, h), bottom)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = y / max(1, h - 1)
        color = tuple(int(top[i] * (1 - r) + bottom[i] * r) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)

    # cinematic bars
    draw.rectangle([0, 0, w, int(h * 0.08)], fill=(0, 0, 0))
    draw.rectangle([0, int(h * 0.92), w, h], fill=(0, 0, 0))

    role = str(scene.get("role") or "scene").upper()
    caption = str(scene.get("on_screen_text") or scene.get("narration") or "")[:80]
    visual = str(scene.get("visual") or "")[:120]
    title_f = _font(42)
    small_f = _font(22)
    draw.text((40, 40), f"AI2 · {role}", font=small_f, fill=(226, 168, 74))

    # center focal
    cx, cy = w // 2, int(h * 0.42)
    draw.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], outline=(226, 168, 74), width=4)

    y = int(h * 0.68)
    for line in _wrap(draw, caption, title_f, w - 80)[:4]:
        tw = draw.textlength(line, font=title_f)
        draw.text(((w - tw) / 2, y), line, font=title_f, fill=(245, 240, 230))
        y += 50
    y += 10
    for line in _wrap(draw, visual, small_f, w - 100)[:3]:
        tw = draw.textlength(line, font=small_f)
        draw.text(((w - tw) / 2, y), line, font=small_f, fill=(180, 186, 178))
        y += 28

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="JPEG", quality=90)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
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
    return lines


def _image_prompt(scene: dict[str, Any], style: str, language: str) -> str:
    visual = scene.get("visual") or ""
    role = scene.get("role") or "scene"
    text = scene.get("on_screen_text") or ""
    return (
        f"Vertical 9:16 cinematic still for YouTube Shorts. "
        f"Role: {role}. Style: {style}. "
        f"Shot description: {visual}. "
        f"Mood lighting, professional color grade, no watermark, no UI chrome. "
        f"Do not render long paragraphs of text; optional tiny title '{text}'. "
        f"Language context: {language}."
    )


async def _generate_via_openrouter(
    api_key: str,
    prompt: str,
    out_path: Path,
) -> None:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.app_name,
    }

    # 1) images/generations (DALL·E / bazı modeller)
    body_img = {
        "model": settings.openrouter_image_model,
        "prompt": prompt,
        "size": "1024x1792",
        "n": 1,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/images/generations",
            headers=headers,
            json=body_img,
        )

        if resp.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="OpenRouter görsel rate limit",
            )

        if resp.status_code < 400:
            data = resp.json()
            items = data.get("data") or []
            if items:
                item = items[0]
                if item.get("b64_json"):
                    out_path.write_bytes(base64.b64decode(item["b64_json"]))
                    return
                if item.get("url"):
                    img_resp = await client.get(item["url"])
                    img_resp.raise_for_status()
                    out_path.write_bytes(img_resp.content)
                    return

        # 2) chat + modalities fallback (Gemini image vb.)
        body_chat = {
            "model": settings.openrouter_image_model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        }
        resp2 = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=body_chat,
        )
        if resp2.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="OpenRouter görsel rate limit",
            )
        if resp2.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"AI2 görsel hatası ({resp.status_code}/{resp2.status_code}): "
                    f"{(resp2.text or resp.text)[:400]}"
                ),
            )
        data2 = resp2.json()
        message = (data2.get("choices") or [{}])[0].get("message") or {}
        images = message.get("images") or []
        if images:
            url = images[0].get("image_url", {}).get("url") or images[0].get("url")
            if url and url.startswith("data:"):
                b64 = url.split(",", 1)[1]
                out_path.write_bytes(base64.b64decode(b64))
                return
            if url:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                out_path.write_bytes(img_resp.content)
                return
        # content parts
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url")
                    if url and url.startswith("data:"):
                        out_path.write_bytes(base64.b64decode(url.split(",", 1)[1]))
                        return

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI2 görsel yanıtında image bulunamadı",
    )


async def run_visual_agent(
    db: Session,
    user: User,
    *,
    script: dict[str, Any],
    job_dir: Path,
    style: str = "cinematic",
    language: str = "tr",
    only_indices: list[int] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    w, h = settings.image_width, settings.image_height
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    api_key = resolve_openrouter_key(db, user)
    check = await verify_openrouter(api_key)

    scenes = list(script.get("scenes") or [])
    outputs: list[dict[str, Any]] = []
    mock = bool(settings.mock_ai)

    for scene in scenes:
        idx = int(scene.get("index") or 0)
        if only_indices is not None and idx not in only_indices:
            # mevcut dosyayı koru
            existing = scenes_dir / f"scene_{idx:02d}.jpg"
            if existing.exists():
                outputs.append({"index": idx, "path": str(existing), "kept": True})
            continue

        out_path = scenes_dir / f"scene_{idx:02d}.jpg"
        if mock or not api_key:
            _mock_scene_image(scene, out_path, w, h)
            outputs.append({"index": idx, "path": str(out_path), "mock": True})
        else:
            prompt = _image_prompt(scene, style, language)
            await _generate_via_openrouter(api_key, prompt, out_path)
            outputs.append({"index": idx, "path": str(out_path), "mock": False})

        scene["image"] = f"scenes/scene_{idx:02d}.jpg"

    return {
        "agent": "AI2_visual",
        "integration": check,
        "images": outputs,
        "script": script,
        "mock": mock or not api_key,
    }
