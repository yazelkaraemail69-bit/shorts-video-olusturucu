"""Tartışma / Eleştiri modülü — AI yönetmen geri bildirimi."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.director.keys import resolve_openrouter_key
from app.models import User

CRITIQUE_SYSTEM = """
Sen Master AI Yönetmen'sin: Shorts kurgu yönetmeni + eleştirmen.
Verilen senaryo JSON'unu eleştir. SADECE JSON döndür:
{
  "score": 1-10,
  "summary": "2 cümle genel hüküm",
  "strengths": ["..."],
  "issues": [
    {"area": "pacing|visual|hook|cta|audio|copy", "scene_index": 2 veya null, "note": "...", "fix": "..."}
  ],
  "next_actions": ["kullanıcıya net öneri"]
}
""".strip()

DISCUSS_SYSTEM = """
Sen Master AI Yönetmen'sin. Kullanıcı eleştirisi geldi.
Mevcut senaryoyu SADECE ilgili yerlerden güncelle.
Yanıt SADECE JSON:
{
  "script": { ...tam güncel senaryo... },
  "changed_fields": ["scenes[2].visual", "cta"],
  "regen_visual_scenes": [2],
  "regen_audio": true,
  "summary": "ne değişti"
}
Kurallar: brief tekrar etme; Shorts ritmini koru; regen_visual_scenes yalnızca görsel değişen sahneler.
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _mock_critique(script: dict[str, Any]) -> dict[str, Any]:
    scenes = script.get("scenes") or []
    mid = scenes[len(scenes) // 2]["index"] if scenes else None
    return {
        "score": 7,
        "summary": "Hook net; orta bölüm biraz düz. CTA güçlendirilebilir.",
        "strengths": ["Hook scroll-stop potansiyeli", "Sahne rolleri ayrışmış"],
        "issues": [
            {
                "area": "pacing",
                "scene_index": mid,
                "note": "Orta sahne fazla uzun hissedilebilir",
                "fix": "Kesimi sıkılaştır veya görseli daha çarpıcı yap",
            },
            {
                "area": "cta",
                "scene_index": None,
                "note": "CTA biraz genel",
                "fix": "Tek net eylem: Kaydet / Dene / Takip et",
            },
        ],
        "next_actions": [
            "Orta sahneyi hızlandır",
            "CTA'yı tek aksiyona indir",
            "İstersen 'daha çarpıcı görsel' de",
        ],
        "mock": True,
    }


def _mock_discuss(script: dict[str, Any], message: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(script))
    lower = message.lower()
    changed: list[str] = []
    regen_visual: list[int] = []
    regen_audio = False

    scene_m = re.search(r"(?:sahne|scene)\s*#?\s*(\d+)", lower)
    if scene_m:
        idx = int(scene_m.group(1))
        for s in updated.get("scenes") or []:
            if int(s.get("index") or 0) == idx:
                if any(k in lower for k in ("görsel", "visual", "çarpıcı", "image")):
                    s["visual"] = f"Ultra çarpıcı sinematik 9:16: {message.strip()[:160]}"
                    changed.append(f"scenes[{idx}].visual")
                    regen_visual.append(idx)
                elif any(k in lower for k in ("yavaş", "hız", "pace", "tempo")):
                    s["cut"] = "hard-cut"
                    s["narration"] = (s.get("narration") or "") + " — tempo yukarı."
                    changed.append(f"scenes[{idx}].narration")
                    regen_audio = True
                else:
                    s["narration"] = message.strip()[:280]
                    changed.append(f"scenes[{idx}].narration")
                    regen_audio = True
                break

    if any(k in lower for k in ("cta", "çağrı")):
        updated["cta"] = message.strip()[:120]
        changed.append("cta")
        for s in updated.get("scenes") or []:
            if s.get("role") == "cta":
                s["on_screen_text"] = "ŞİMDİ DENE"
                s["narration"] = updated["cta"]
                changed.append(f"scenes[{s.get('index')}].narration")
                regen_audio = True

    if any(k in lower for k in ("yavaş", "hız")) and not changed:
        for s in updated.get("scenes") or []:
            if s.get("role") in ("demo", "twist", "proof"):
                s["cut"] = "whip"
                changed.append(f"scenes[{s.get('index')}].cut")
        regen_audio = True

    if any(k in lower for k in ("görsel", "çarpıcı")) and not regen_visual:
        for s in updated.get("scenes") or []:
            if s.get("role") in ("hook", "demo"):
                idx = int(s.get("index") or 0)
                s["visual"] = f"Daha çarpıcı sinematik kare — {message.strip()[:100]}"
                regen_visual.append(idx)
                changed.append(f"scenes[{idx}].visual")

    if not changed:
        updated["hook"] = f"{updated.get('hook') or ''} · {message.strip()[:80]}".strip(" ·")
        changed.append("hook")
        regen_audio = True

    # voiceover sync
    narrs = [s.get("narration") or "" for s in updated.get("scenes") or []]
    if narrs:
        updated["voiceover_full"] = " ".join(narrs)
        changed.append("voiceover_full")

    return {
        "script": updated,
        "changed_fields": changed,
        "regen_visual_scenes": sorted(set(regen_visual)),
        "regen_audio": regen_audio,
        "summary": f"Uygulandı: {', '.join(changed[:6])}",
    }


async def _chat_json(api_key: str, system: str, user_content: str) -> dict[str, Any]:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.app_name,
    }
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=body,
        )
    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenRouter rate limit (429) — eleştiri/tartışma beklemeli.",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter hata ({resp.status_code}): {resp.text[:300]}",
        )
    content = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


async def build_critique_report(
    db: Session,
    user: User,
    script: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    if settings.mock_ai:
        return _mock_critique(script)
    api_key = resolve_openrouter_key(db, user)
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter anahtarı yok")
    return await _chat_json(
        api_key,
        CRITIQUE_SYSTEM,
        json.dumps({"script": script}, ensure_ascii=False),
    )


async def apply_discussion(
    db: Session,
    user: User,
    script: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.mock_ai:
        return _mock_discuss(script, message)
    api_key = resolve_openrouter_key(db, user)
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter anahtarı yok")
    return await _chat_json(
        api_key,
        DISCUSS_SYSTEM,
        json.dumps({"script": script, "user_feedback": message}, ensure_ascii=False),
    )
