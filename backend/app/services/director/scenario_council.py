"""3'lü iç konsey: AI-A taslak → AI-B tartışarak iyileştir → AI-C denetle.

ÖNEMLİ: Tartışma/düşünme süreci kullanıcıya ve API'ye ASLA döndürülmez.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.cliche_guard import detect_cliches, rewrite_cliche_narration, topic_variant_index
from app.services.director.constitution import (
    AUDITOR_SYSTEM,
    CHALLENGER_SYSTEM,
    PROPOSER_SYSTEM,
)
from app.services.director.integration import resolve_openrouter_key, verify_openrouter
from app.services.openrouter import _extract_json, _mock_script, _topic_seed, chat_completion_json
from app.services.shorts_prompt import SHORTS_SCHEMA_HINT, SHORTS_USER_PREFIX

logger = logging.getLogger(__name__)


def _payload(
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
) -> dict[str, Any]:
    return {
        "language": language,
        "title": title,
        "duration_seconds": duration_seconds,
        "style": style,
        "audience": audience,
        "format": "youtube_shorts_9x16",
        "user_brief": raw_input,
    }


def _validate_script(script: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(script, dict) or "scenes" not in script:
        raise ValueError("Senaryo şeması geçersiz")
    script.setdefault("format", "shorts_9x16")
    return script


def _mock_challenge(script: dict[str, Any], *, language: str, raw_input: str) -> dict[str, Any]:
    """AI-B mock: kalıpları tespit et, alternatif cümlelerle tazele."""
    out = json.loads(json.dumps(script, ensure_ascii=False))
    variant = topic_variant_index(raw_input, 6)
    clichés = detect_cliches(out)
    if not clichés:
        return out

    for sc in out.get("scenes") or []:
        sc["narration"] = rewrite_cliche_narration(
            str(sc.get("narration") or ""),
            language=language,
            variant=variant + int(sc.get("index") or 0),
        )

    narrations = [str(s.get("narration") or "") for s in out.get("scenes") or []]
    out["voiceover_full"] = " ".join(n for n in narrations if n)
    if out.get("scenes"):
        out["hook"] = narrations[0][:120] if narrations else out.get("hook")

    topic = _topic_seed(raw_input)
    tr = not language.lower().startswith("en")
    hooks = (
        [
            f"{topic[:40]} — çoğu kişi tam tersini yapıyor.",
            f"3 saniyede anlayacaksın: {topic[:35]}",
            f"Kimse söylemiyor ama {topic[:30]} böyle çalışır.",
        ]
        if tr
        else [
            f"{topic[:40]} — most people get this backwards.",
            f"In 3 seconds you'll see why {topic[:30]} matters.",
            f"Nobody talks about this part of {topic[:25]}.",
        ]
    )
    out["hook"] = hooks[variant % len(hooks)]
    return out


def _mock_audit(script: dict[str, Any], *, language: str, style: str) -> dict[str, Any]:
    """AI-C mock: küçük üslup cilası."""
    out = json.loads(json.dumps(script, ensure_ascii=False))
    tr = not language.lower().startswith("en")

    for sc in out.get("scenes") or []:
        txt = str(sc.get("on_screen_text") or "")
        words = txt.split()
        if len(words) > 6:
            sc["on_screen_text"] = " ".join(words[:6])

    cta = str(out.get("cta") or "")
    if tr and "kaydet" in cta.lower() and style in ("minimal", "eğitici"):
        out["cta"] = "Denemek için kaydet — bir sonraki Short'ta uygula."
    elif not tr and "save" in cta.lower() and style in ("minimal",):
        out["cta"] = "Save for your next Short — try the first step today."

    narrations = [str(s.get("narration") or "") for s in out.get("scenes") or []]
    out["voiceover_full"] = " ".join(n for n in narrations if n)
    return out


async def _mock_council(
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
) -> dict[str, Any]:
    draft = _mock_script(
        language=language,
        title=title,
        duration_seconds=duration_seconds,
        style=style,
        audience=audience,
        raw_input=raw_input,
    )
    revised = _mock_challenge(draft, language=language, raw_input=raw_input)
    final = _mock_audit(revised, language=language, style=style)
    final["_mock"] = True
    return _validate_script(final)


async def _propose(
    api_key: str,
    model: str,
    base_payload: dict[str, Any],
) -> dict[str, Any]:
    user = (
        SHORTS_USER_PREFIX
        + "\n\n"
        + SHORTS_SCHEMA_HINT
        + "\n\n"
        + json.dumps(base_payload, ensure_ascii=False, indent=2)
    )
    raw = await chat_completion_json(
        api_key=api_key,
        model=model,
        system=PROPOSER_SYSTEM,
        user=user,
        temperature=0.82,
    )
    return _validate_script(raw)


async def _challenge(
    api_key: str,
    model: str,
    base_payload: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    user = (
        "Aşağıdaki brief ve AI-A taslağını incele. Kalıpları kır, insani tonda yeniden yaz.\n"
        "Tartışma metni yazma — yalnızca iyileştirilmiş JSON.\n\n"
        f"BRIEF:\n{json.dumps(base_payload, ensure_ascii=False, indent=2)}\n\n"
        f"AI-A TASLAK (gizli — kullanıcı görmez):\n"
        f"{json.dumps(draft, ensure_ascii=False, indent=2)}\n\n"
        f"{SHORTS_SCHEMA_HINT}"
    )
    raw = await chat_completion_json(
        api_key=api_key,
        model=model,
        system=CHALLENGER_SYSTEM,
        user=user,
        temperature=0.65,
    )
    return _validate_script(raw)


async def _audit(
    api_key: str,
    model: str,
    base_payload: dict[str, Any],
    script: dict[str, Any],
) -> dict[str, Any]:
    user = (
        "Son denetim: üslup uyumu, insan sesi, tekrar/kalıp kontrolü.\n"
        "Gerekirse küçük düzeltmeler yap. Rapor yazma — yalnızca nihai JSON.\n\n"
        f"BRIEF:\n{json.dumps(base_payload, ensure_ascii=False, indent=2)}\n\n"
        f"SENARYO:\n{json.dumps(script, ensure_ascii=False, indent=2)}\n\n"
        f"{SHORTS_SCHEMA_HINT}"
    )
    raw = await chat_completion_json(
        api_key=api_key,
        model=model,
        system=AUDITOR_SYSTEM,
        user=user,
        temperature=0.35,
    )
    return _validate_script(raw)


async def run_scenario_council(
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
    """
    Dışarıya yalnızca: {"script": ..., "integration": ..., "agent": "AI1_council"}
    İç konsey adımları loglanmaz / API'ye eklenmez.
    """
    settings = get_settings()
    api_key = resolve_openrouter_key(db, user)
    check = await verify_openrouter(api_key)

    if settings.mock_ai:
        script = await _mock_council(
            language=language,
            title=title,
            duration_seconds=duration_seconds,
            style=style,
            audience=audience,
            raw_input=raw_input,
        )
        return {"script": script, "integration": check, "agent": "AI1_council"}

    if not api_key:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API anahtarı bulunamadı.",
        )

    model = settings.openrouter_model
    base = _payload(
        language=language,
        title=title,
        duration_seconds=duration_seconds,
        style=style,
        audience=audience,
        raw_input=raw_input,
    )

    draft = await _propose(api_key, model, base)
    revised = await _challenge(api_key, model, base, draft)
    final = await _audit(api_key, model, base, revised)

    # İç kalite kontrolü — hâlâ kalıp varsa bir kez daha challenge (gizli)
    if detect_cliches(final):
        logger.debug("Council: cliché detected post-audit, running silent re-challenge")
        final = await _challenge(api_key, model, base, final)

    return {"script": final, "integration": check, "agent": "AI1_council"}
