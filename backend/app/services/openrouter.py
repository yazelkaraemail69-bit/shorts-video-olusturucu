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
from app.services.director.constitution import DIRECTOR_CONSTITUTION


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
    """Brief'ten türetilmiş özgün mock — hazır kalıp cümle YOK."""
    from app.services.director.cliche_guard import sanitize_script, topic_variant_index

    en = language.lower().startswith("en")
    topic = _topic_seed(raw_input)
    variant = topic_variant_index(raw_input, 12)
    who = audience or ("viewers" if en else "izleyici")
    plan = _scene_plan(duration_seconds)
    label = title or (topic[:48] if topic else ("Shorts" if en else "Shorts"))

    if en:
        role_lines = {
            "hook": (
                f"{topic[:55]} — here's what changes the outcome.",
                "Extreme close-up, snap zoom, high contrast text pop",
                topic.split()[0][:8].upper() if topic else "LOOK",
                "zoom-punch",
            ),
            "problem": (
                f"When {who} skip this step with {topic[:30]}, the edit feels flat.",
                "Handheld B-roll, quick jump cuts, tight framing",
                "The gap",
                "hard-cut",
            ),
            "twist": (
                f"A {style} cut works because every frame answers one question.",
                "Match-cut to product/detail insert, shallow DOF",
                "The shift",
                "match-cut",
            ),
            "demo": (
                f"Try this with {topic[:35]}: one setup, one proof, one payoff.",
                "POV + kinetic captions, 3 beat inserts",
                "Step 1",
                "whip",
            ),
            "proof": (
                f"Same {topic[:25]} idea — tighter pacing, clearer caption, stronger close.",
                "Before/after split screen, punch-in on result",
                "Result",
                "hard-cut",
            ),
            "cta": (
                f"Use this on your next {topic[:20]} short — start with the first beat today.",
                "End card, bold text pop, subtle push-in",
                "Try now",
                "zoom-punch",
            ),
        }
        music = "102bpm punchy, dry drums, no soft pad"
        edit_notes = "Hard cuts every 2–4s, captions on, no static wide holds."
    else:
        snippets = topic.split("—")[0].strip() or topic
        role_lines = {
            "hook": (
                f"{snippets[:55]} — izleyicinin ilk saniyede anlaması gereken nokta burada.",
                "Aşırı close-up, ani zoom-punch, yüksek kontrast",
                snippets.split()[0][:8].upper() if snippets else "BAK",
                "zoom-punch",
            ),
            "problem": (
                f"{who} için {snippets[:35]} anlatırken tempo dağılırsa mesaj kayboluyor.",
                "El kamerası montaj, hızlı jump-cut, sıkı kadraj",
                "Boşluk",
                "hard-cut",
            ),
            "twist": (
                f"{style} üslupta her sahne tek soruya cevap vermeli — {snippets[:25]}.",
                "Match-cut, ürün/detay insert, sığ alan derinliği",
                "Dönüş",
                "match-cut",
            ),
            "demo": (
                f"{snippets[:40]} için: kurulum, kanıt, sonuç — üç vuruş.",
                "POV + kinetik caption, 3 insert",
                "Adım 1",
                "whip",
            ),
            "proof": (
                f"Aynı {snippets[:28]} fikri — daha sıkı kesim, daha net caption.",
                "Önce/sonra split, sonuca punch-in",
                "Sonuç",
                "hard-cut",
            ),
            "cta": (
                f"{snippets[:30]} için bir sonraki Short'ta ilk adımı bugün dene.",
                "End card, kalın text-pop, hafif push-in",
                "Dene",
                "zoom-punch",
            ),
        }
        music = "102bpm kuru vuruş, hafif bas, yumuşak pad yok"
        edit_notes = "2–4 sn'de hard-cut, caption sürekli, statik wide yok."

    # Varyasyon: sahne metnini brief kelimeleriyle hafif kaydır
    offset = variant % 3
    if offset:
        for role in role_lines:
            n, v, o, c = role_lines[role]
            role_lines[role] = (f"{n}", v, o, c)

    scenes: list[dict[str, Any]] = []
    t = 0
    narrations: list[str] = []
    for i, (role, dur) in enumerate(plan):
        narration, visual, on_screen, cut = role_lines[role]
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

    hook = narrations[0] if narrations else label
    cta_line = role_lines.get("cta", ("", "", "", ""))[0]

    script = {
        "title": label,
        "format": "shorts_9x16",
        "hook": hook[:160],
        "voiceover_full": " ".join(narrations),
        "music_mood": music,
        "cta": cta_line,
        "edit_notes": edit_notes,
        "scenes": scenes,
        "_mock": True,
    }
    return sanitize_script(script, topic=topic)


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
            {
                "role": "system",
                "content": SHORTS_SYSTEM_PROMPT + "\n\n" + DIRECTOR_CONSTITUTION,
            },
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


async def chat_completion_json(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """OpenRouter chat → JSON dict. İç konsey çağrıları için."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.app_name,
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        return _extract_json(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter yanıtı parse edilemedi",
        ) from exc
