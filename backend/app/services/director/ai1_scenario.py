"""AI 1 — Senaryo Uzmanı (OpenRouter / Claude)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import User
from app.services.director.integration import resolve_openrouter_key, verify_openrouter
from app.services.openrouter import professionalize_prompt


async def run_scenario_agent(
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
    api_key = resolve_openrouter_key(db, user)
    check = await verify_openrouter(api_key)
    script = await professionalize_prompt(
        db,
        user,
        language=language,
        title=title,
        duration_seconds=duration_seconds,
        style=style,
        audience=audience,
        raw_input=raw_input,
    )
    return {"script": script, "integration": check, "agent": "AI1_scenario"}
