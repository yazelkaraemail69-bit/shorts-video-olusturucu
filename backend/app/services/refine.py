from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.integration import resolve_openrouter_key

from app.services.director.constitution import DIRECTOR_CONSTITUTION

REFINE_SYSTEM = f"""
SEN: YouTube Shorts uzmanı + profesyonel video editörüsün.
Mevcut senaryoyu ve kullanıcının düzeltmesini alacaksın.
SADECE ilgili alanları değiştir; geri kalanını koru.
Brief/tekrar yapıştırma YASAK. Shorts ritmini (hook→problem→twist→demo→cta) bozma.

{DIRECTOR_CONSTITUTION}

Yanıt SADECE JSON:
{{
  "script": {{ ...güncellenmiş tam senaryo... }},
  "changed_fields": ["scenes[2].narration", "cta"],
  "summary": "kısa Türkçe özet"
}}
""".strip()


def _get_openrouter_key(db: Session, user: User) -> str | None:
    return resolve_openrouter_key(db, user)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _mock_refine(script: dict[str, Any], instruction: str) -> dict[str, Any]:
    """Kural tabanlı kısmi güncelleme (mock)."""
    updated = json.loads(json.dumps(script))  # deep copy
    changed: list[str] = []
    lower = instruction.lower()

    # CTA
    if any(k in lower for k in ("cta", "çağrı", "call to action", "kapanış")):
        updated["cta"] = instruction.strip()[:200]
        changed.append("cta")

    # Hook
    if any(k in lower for k in ("hook", "açılış", "giriş", "ilk saniye")):
        updated["hook"] = instruction.strip()[:200]
        changed.append("hook")

    # Müzik
    if any(k in lower for k in ("müzik", "music", "atmosfer")):
        updated["music_mood"] = instruction.strip()[:160]
        changed.append("music_mood")

    # Belirli sahne: "sahne 2", "scene 3"
    scene_match = re.search(r"(?:sahne|scene)\s*#?\s*(\d+)", lower)
    if scene_match and updated.get("scenes"):
        idx = int(scene_match.group(1))
        for scene in updated["scenes"]:
            if int(scene.get("index") or 0) == idx:
                if any(k in lower for k in ("görsel", "visual", "görüntü")):
                    scene["visual"] = instruction.strip()[:300]
                    changed.append(f"scenes[{idx}].visual")
                elif any(k in lower for k in ("ekran", "on_screen", "yazı")):
                    scene["on_screen_text"] = instruction.strip()[:80]
                    changed.append(f"scenes[{idx}].on_screen_text")
                else:
                    scene["narration"] = instruction.strip()[:400]
                    changed.append(f"scenes[{idx}].narration")
                break

    # Genel seslendirme
    if not changed and any(k in lower for k in ("ses", "voice", "anlatım", "narration", "metin")):
        note = f" [{instruction.strip()[:120]}]"
        updated["voiceover_full"] = (updated.get("voiceover_full") or "") + note
        changed.append("voiceover_full")

    # Fallback: hook'a not ekle
    if not changed:
        updated["hook"] = f"{updated.get('hook') or ''} · {instruction.strip()[:100]}".strip(" ·")
        changed.append("hook")
        # voiceover'ı da hafifçe işaretle ki ses yeniden üretilsin
        updated["voiceover_full"] = updated.get("voiceover_full") or ""
        if instruction.strip() not in updated["voiceover_full"]:
            updated["voiceover_full"] = updated["voiceover_full"] + f" ({instruction.strip()[:80]})"
            changed.append("voiceover_full")

    return {
        "script": updated,
        "changed_fields": changed,
        "summary": f"Mock düzenleme uygulandı: {', '.join(changed)}",
    }


async def refine_script(
    db: Session,
    user: User,
    *,
    script: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    settings = get_settings()

    if settings.mock_ai:
        return _mock_refine(script, instruction)

    api_key = _get_openrouter_key(db, user)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter anahtarı gerekli (veya MOCK_AI=true).",
        )

    payload = {
        "current_script": script,
        "instruction": instruction,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.app_name,
    }
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": REFINE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter hata ({resp.status_code}): {resp.text[:400]}",
        )

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        data = _extract_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Düzenleme yanıtı parse edilemedi",
        ) from exc

    if "script" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Düzenleme şeması geçersiz",
        )
    data.setdefault("changed_fields", [])
    data.setdefault("summary", "")
    return data


def needs_audio_regen(changed_fields: list[str]) -> bool:
    audio_keys = ("voiceover", "narration", "hook", "cta", "scenes")
    return any(any(k in f for k in audio_keys) for f in changed_fields) or not changed_fields
