from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiKey, ApiProvider, User
from app.security import decrypt_api_key
from app.services.shorts_prompt import SHORTS_SYSTEM_PROMPT, SHORTS_USER_PREFIX


def _get_user_openrouter_key(db: Session, user: User) -> str | None:
    row = db.scalar(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == ApiProvider.openrouter,
        )
    )
    if row:
        return decrypt_api_key(row.key_encrypted)
    return get_settings().openrouter_api_key or None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _scene_plan(duration_seconds: int) -> list[tuple[str, int]]:
    """(role, süre_sn) — Shorts ritmi."""
    if duration_seconds <= 15:
        return [("hook", 3), ("problem", 4), ("twist", 4), ("cta", 4)]
    if duration_seconds <= 30:
        return [
            ("hook", 3),
            ("problem", 5),
            ("twist", 5),
            ("demo", 7),
            ("cta", 5),
        ]
    if duration_seconds <= 45:
        return [
            ("hook", 3),
            ("problem", 6),
            ("twist", 7),
            ("demo", 8),
            ("proof", 8),
            ("cta", 6),
        ]
    return [
        ("hook", 3),
        ("problem", 7),
        ("twist", 8),
        ("demo", 10),
        ("proof", 10),
        ("cta", 7),
    ]


def _topic_seed(raw_input: str) -> str:
    """Brief'ten kısa konu çekirdeği — tekrar için değil, bağlam için."""
    cleaned = re.sub(r"\s+", " ", raw_input.strip())
    return cleaned[:90]


def _mock_script(
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
) -> dict[str, Any]:
    """Tekrar etmeyen, Shorts ritminde mock senaryo."""
    en = language.lower().startswith("en")
    topic = _topic_seed(raw_input)
    who = audience or ("viewers" if en else "izleyici")
    plan = _scene_plan(duration_seconds)

    if en:
        beats = {
            "hook": (
                f"Stop scrolling — {topic.split('.')[0][:50]}",
                "Extreme close-up, snap zoom, high contrast",
                "WAIT.",
                "zoom-punch",
            ),
            "problem": (
                f"Most {who} waste time guessing instead of a clear system.",
                "Handheld frustration montage, quick jump cuts",
                "The real problem",
                "hard-cut",
            ),
            "twist": (
                f"The fix isn't more effort — it's a tighter {style} edit.",
                "Match-cut to clean desk / product insert",
                "Here's the shift",
                "match-cut",
            ),
            "demo": (
                "Watch one clean move: setup → proof → payoff in seconds.",
                "POV screen + kinetic captions, 3 beat inserts",
                "Do this",
                "whip",
            ),
            "proof": (
                "Same idea, sharper cut — retention jumps when every second earns its place.",
                "Before/after split, punch-in on result",
                "Proof",
                "hard-cut",
            ),
            "cta": (
                "Save this. Try it on your next Short. Follow for more edit systems.",
                "End card, bold text pop, subtle push-in",
                "Save + try",
                "zoom-punch",
            ),
        }
        lang_title = title or "Shorts Cut"
        hook = beats["hook"][0]
        music = "100–110bpm dry punchy, no soft pad"
        cta = "Save this · try it on your next Short"
        edit_notes = "Hard cuts every 2–4s, captions always on, never hold a static wide."
    else:
        beats = {
            "hook": (
                f"Dur. {topic.split('.')[0][:50]} — bunu yanlış yapıyorsun.",
                "Aşırı close-up, ani zoom-punch, yüksek kontrast",
                "DUR.",
                "zoom-punch",
            ),
            "problem": (
                f"Çoğu {who} aynı hatayı tekrar ediyor: fikir var, ritim yok.",
                "El kamerası montaj, hızlı jump-cut'lar",
                "Asıl sorun",
                "hard-cut",
            ),
            "twist": (
                f"Çözüm daha çok çekim değil — {style} bir Shorts kurgusu.",
                "Match-cut ile temiz insert / ürün detayı",
                "Kırılma noktası",
                "match-cut",
            ),
            "demo": (
                "Tek net hareket: kurulum → kanıt → payoff. Her saniye iş yapsın.",
                "POV + kinetik caption, 3 vuruşluk insert",
                "Bunu yap",
                "whip",
            ),
            "proof": (
                "Aynı fikir, daha sert kesim — her kare hak edince izlenme uzar.",
                "Önce/sonra split, sonuca punch-in",
                "Kanıt",
                "hard-cut",
            ),
            "cta": (
                "Kaydet. Bir sonraki Short'unda dene. Daha fazla kurgu sistemi için takip et.",
                "End card, kalın text-pop, hafif push-in",
                "Kaydet + dene",
                "zoom-punch",
            ),
        }
        lang_title = title or "Shorts Kurgu"
        hook = beats["hook"][0]
        music = "100–110bpm kuru vuruşlu, yumuşak pad yok"
        cta = "Kaydet · bir sonraki Short'unda dene"
        edit_notes = "2–4 sn'de bir hard-cut, caption hep açık, statik wide tutma."

    scenes: list[dict[str, Any]] = []
    t = 0
    narrations: list[str] = []
    for i, (role, dur) in enumerate(plan):
        narration, visual, on_screen, cut = beats[role]
        # Son sahnenin süresini toplam süreye oturt
        if i == len(plan) - 1:
            dur = max(2, duration_seconds - t)
        end = t + dur
        scenes.append(
            {
                "index": i + 1,
                "role": role,
                "timecode": f"{t}-{end}s",
                "visual": visual,
                "narration": narration,
                "on_screen_text": on_screen,
                "cut": cut,
            }
        )
        narrations.append(narration)
        t = end

    return {
        "title": lang_title,
        "format": "shorts_9x16",
        "hook": hook,
        "voiceover_full": " ".join(narrations),
        "music_mood": music,
        "cta": cta,
        "edit_notes": edit_notes,
        "scenes": scenes,
        "_mock": True,
    }


async def professionalize_prompt(
    db: Session,
    user: User,
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
) -> dict[str, Any]:
    settings = get_settings()
    api_key = _get_user_openrouter_key(db, user)

    if settings.mock_ai:
        return _mock_script(
            language=language,
            title=title,
            duration_seconds=duration_seconds,
            style=style,
            audience=audience,
            raw_input=raw_input,
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "OpenRouter API anahtarı bulunamadı. "
                "Ayarlardan kaydedin veya MOCK_AI=true kullanın."
            ),
        )

    user_payload = {
        "language": language,
        "title": title,
        "duration_seconds": duration_seconds,
        "style": style,
        "audience": audience,
        "format": "youtube_shorts_9x16",
        "user_brief": raw_input,
        "editor_mandate": (
            "Brief'i tekrar etme. Shorts uzmanı + video editörü gibi "
            "hook→problem→twist→demo→cta ritminde yeniden yaz."
        ),
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
            {"role": "system", "content": SHORTS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SHORTS_USER_PREFIX
                + "\n\n"
                + json.dumps(user_payload, ensure_ascii=False, indent=2),
            },
        ],
        "temperature": 0.75,
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

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
        script = _extract_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter yanıtı parse edilemedi",
        ) from exc

    if not isinstance(script, dict) or "scenes" not in script:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Senaryo şeması geçersiz",
        )
    script.setdefault("format", "shorts_9x16")
    return script
