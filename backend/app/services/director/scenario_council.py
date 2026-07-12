"""3'lü iç konsey: AI-A taslak → AI-B tartışarak iyileştir → AI-C denetle.

ÖNEMLİ: Tartışma/düşünme süreci kullanıcıya ve API'ye ASLA döndürülmez.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.cliche_guard import detect_cliches, sanitize_script
from app.services.director.constitution import (
    AUDITOR_SYSTEM,
    CHALLENGER_SYSTEM,
    PROPOSER_SYSTEM,
)
from app.services.director.integration import resolve_openrouter_key, verify_openrouter
from app.services.director.knowledge_scanner import anthropic_completion_json, knowledge_for_council
from app.services.openrouter import _mock_script, _topic_seed, chat_completion_json
from app.services.shorts_prompt import SHORTS_SCHEMA_HINT, SHORTS_USER_PREFIX

logger = logging.getLogger(__name__)

Provider = Literal["anthropic", "openrouter"]


def _payload(
    *,
    language: str,
    title: str | None,
    duration_seconds: int,
    style: str,
    audience: str | None,
    raw_input: str,
    knowledge_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = {
        "language": language,
        "title": title,
        "duration_seconds": duration_seconds,
        "style": style,
        "audience": audience,
        "format": "youtube_shorts_9x16",
        "user_brief": raw_input,
    }
    ctx = knowledge_for_council(knowledge_brief)
    if ctx:
        base["source_knowledge"] = ctx
    return base


def _validate_script(script: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(script, dict) or "scenes" not in script:
        raise ValueError("Senaryo şeması geçersiz")
    script.setdefault("format", "shorts_9x16")
    return script


async def _llm_json(
    *,
    provider: Provider,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
) -> dict[str, Any]:
    if provider == "anthropic":
        return await anthropic_completion_json(system, user, temperature=temperature)
    return await chat_completion_json(
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        temperature=temperature,
    )


def _mock_challenge(script: dict[str, Any], *, raw_input: str) -> dict[str, Any]:
    return sanitize_script(script, topic=_topic_seed(raw_input))


def _mock_audit(script: dict[str, Any], *, language: str, style: str) -> dict[str, Any]:
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
    revised = _mock_challenge(draft, raw_input=raw_input)
    final = _mock_audit(revised, language=language, style=style)
    final["_mock"] = True
    return _validate_script(sanitize_script(final, topic=raw_input))


async def _propose(
    provider: Provider,
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
    raw = await _llm_json(
        provider=provider,
        api_key=api_key,
        model=model,
        system=PROPOSER_SYSTEM,
        user=user,
        temperature=0.82,
    )
    return _validate_script(raw)


async def _challenge(
    provider: Provider,
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
    raw = await _llm_json(
        provider=provider,
        api_key=api_key,
        model=model,
        system=CHALLENGER_SYSTEM,
        user=user,
        temperature=0.65,
    )
    return _validate_script(raw)


async def _audit(
    provider: Provider,
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
    raw = await _llm_json(
        provider=provider,
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
    knowledge_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    openrouter_key = resolve_openrouter_key(db, user)
    anthropic_key = settings.anthropic_api_key.strip()

    if openrouter_key:
        check = await verify_openrouter(openrouter_key)
        provider: Provider = "openrouter"
        api_key = openrouter_key
        model = settings.openrouter_model
        model_challenge = settings.openrouter_model_challenger or model
        model_audit = settings.openrouter_model_auditor or model
    elif anthropic_key:
        check = {"ok": True, "mode": "anthropic", "model": settings.anthropic_model}
        provider = "anthropic"
        api_key = anthropic_key
        model = settings.anthropic_model
        model_challenge = model
        model_audit = model
    else:
        check = await verify_openrouter(None)
        provider = "openrouter"
        api_key = ""
        model = ""

    use_mock = settings.mock_ai and not anthropic_key and not openrouter_key

    if use_mock:
        script = await _mock_council(
            language=language,
            title=title,
            duration_seconds=duration_seconds,
            style=style,
            audience=audience,
            raw_input=raw_input,
        )
        if knowledge_brief and script.get("scenes"):
            script["edit_notes"] = (
                str(script.get("edit_notes") or "") + " | Kaynak rehberli"
            ).strip(" |")
        script = sanitize_script(script, topic=raw_input)
        return {"script": script, "integration": check, "agent": "AI1_council"}

    if not api_key:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anthropic veya OpenRouter API anahtarı gerekli.",
        )

    base = _payload(
        language=language,
        title=title,
        duration_seconds=duration_seconds,
        style=style,
        audience=audience,
        raw_input=raw_input,
        knowledge_brief=knowledge_brief,
    )

    draft = await _propose(provider, api_key, model, base)
    revised = await _challenge(provider, api_key, model_challenge, base, draft)
    final = await _audit(provider, api_key, model_audit, base, revised)

    if detect_cliches(final):
        logger.debug("Council: cliché detected post-audit, running silent re-challenge")
        final = await _challenge(provider, api_key, model_challenge, base, final)

    final = sanitize_script(final, topic=raw_input)
    return {"script": final, "integration": check, "agent": "AI1_council"}
