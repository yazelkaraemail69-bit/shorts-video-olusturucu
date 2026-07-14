"""Toplu üretim router — birden çok senaryodan video üretimi."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import SessionLocal
from app.deps import get_current_user
from app.models import Scenario, User, VideoJob
from app.services.director.pipeline import (
    enqueue_produce,
    execute_produce_job,
    produce_from_scenario,
)
from app.services.director.templates import apply_template, get_template, list_templates
from app.services.director.music_bed import get_available_moods
from app.services.director.sound_fx import list_sound_effects

router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchProduceRequest(BaseModel):
    scenario_ids: list[int] = Field(..., min_length=1, max_length=20)
    template_id: str | None = Field(None, description="Opsiyonel video şablonu")


class BatchProduceResponse(BaseModel):
    batch_id: str
    jobs: list[dict[str, Any]]
    total: int
    success: int
    failed: int


@router.post("/produce", response_model=BatchProduceResponse)
async def batch_produce(
    req: BatchProduceRequest,
    user: User = Depends(get_current_user),
):
    """Birden çok senaryoyu sırayla üret."""
    db = SessionLocal()
    try:
        jobs: list[dict[str, Any]] = []
        success = 0
        failed = 0

        for sid in req.scenario_ids:
            scenario = db.get(Scenario, sid)
            if not scenario or scenario.user_id != user.id:
                jobs.append({
                    "scenario_id": sid,
                    "status": "skipped",
                    "error": "Senaryo bulunamadı",
                })
                failed += 1
                continue

            # Şablon uygula (opsiyonel)
            if req.template_id:
                script = _parse_script(scenario.professional_script)
                if script:
                    script = apply_template(req.template_id, script)
                    scenario.professional_script = _serialize_script(script)
                    db.flush()

            try:
                job = enqueue_produce(db, user, scenario)
                jobs.append({
                    "scenario_id": sid,
                    "job_id": job.id,
                    "status": "pending",
                })
                success += 1
            except HTTPException as exc:
                jobs.append({
                    "scenario_id": sid,
                    "status": "failed",
                    "error": exc.detail,
                })
                failed += 1

        import uuid
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"

        # Arka planda sırayla işle
        asyncio.create_task(_process_batch_jobs(batch_id, [j["job_id"] for j in jobs if "job_id" in j]))

        return BatchProduceResponse(
            batch_id=batch_id,
            jobs=jobs,
            total=len(req.scenario_ids),
            success=success,
            failed=failed,
        )
    finally:
        db.close()


async def _process_batch_jobs(batch_id: str, job_ids: list[int]) -> None:
    """Batch job'ları sırayla işle."""
    for jid in job_ids:
        try:
            await execute_produce_job(jid)
            await asyncio.sleep(0.5)  # Rate limit koruması
        except Exception:
            pass


@router.get("/templates")
async def get_templates():
    """Kullanılabilir video şablonlarını listele."""
    return {"templates": list_templates()}


@router.get("/moods")
async def get_moods():
    """Kullanılabilir müzik ruh hallerini listele."""
    return {"moods": get_available_moods()}


@router.get("/sound-effects")
async def get_sound_effects():
    """Kullanılabilir ses efektlerini listele."""
    return {"effects": list_sound_effects()}


@router.post("/templates/{template_id}/preview")
async def preview_template(template_id: str, scenario_id: int, user: User = Depends(get_current_user)):
    """Şablonu bir senaryoya uygula ve önizle."""
    db = SessionLocal()
    try:
        scenario = db.get(Scenario, scenario_id)
        if not scenario or scenario.user_id != user.id:
            raise HTTPException(status_code=404, detail="Senaryo bulunamadı")

        template = get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Şablon bulunamadı")

        script = _parse_script(scenario.professional_script)
        if not script:
            raise HTTPException(status_code=400, detail="Önce AI1 senaryosunu üretin")

        applied = apply_template(template_id, script)
        return {
            "template": template,
            "preview": {
                "style": applied.get("style"),
                "music_mood": applied.get("music_mood"),
                "edit_notes": applied.get("edit_notes"),
                "scene_count": len(applied.get("scenes") or []),
                "cuts": list(set(s.get("cut", "") for s in (applied.get("scenes") or []) if s.get("cut"))),
            },
        }
    finally:
        db.close()


def _parse_script(raw: str) -> dict[str, Any] | None:
    import json
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None


def _serialize_script(script: dict[str, Any]) -> str:
    import json
    return json.dumps(script, ensure_ascii=False)