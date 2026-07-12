"""AI 1 — Senaryo Konseyi (AI-A + AI-B tartışma → AI-C denetim)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import User
from app.services.director.scenario_council import run_scenario_council


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
    knowledge_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await run_scenario_council(
        db,
        user,
        language=language,
        title=title,
        duration_seconds=duration_seconds,
        style=style,
        audience=audience,
        raw_input=raw_input,
        knowledge_brief=knowledge_brief,
    )
