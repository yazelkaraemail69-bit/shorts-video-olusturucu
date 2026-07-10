from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import Scenario, User, VideoJob
from app.schemas import JobRevisionOut, ProduceRequest, RefineRequest, VideoJobOut
from app.services.director.pipeline import get_job_critique, produce_from_scenario, refine_job
from app.config import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_script(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _parse_fields(raw: str) -> list[str]:
    try:
        data = json.loads(raw) if raw else []
        if isinstance(data, dict):
            fields = data.get("fields") or []
            return fields if isinstance(fields, list) else [str(fields)]
        return data if isinstance(data, list) else [str(data)]
    except json.JSONDecodeError:
        return []


def _scene_images(job_id: int) -> list[dict]:
    root = Path(get_settings().media_dir) / "jobs" / str(job_id)
    manifest = root / "scenes_manifest.json"
    if manifest.exists():
        try:
            return json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    scenes_dir = root / "scenes"
    if not scenes_dir.exists():
        return []
    out = []
    for p in sorted(scenes_dir.glob("scene_*.jpg")):
        out.append({"index": int(p.stem.split("_")[1]), "url": f"/media/jobs/{job_id}/scenes/{p.name}"})
    return out


def _to_out(job: VideoJob, include_revisions: bool = True) -> VideoJobOut:
    revs: list[JobRevisionOut] = []
    if include_revisions and job.revisions:
        for r in sorted(job.revisions, key=lambda x: x.revision, reverse=True):
            revs.append(
                JobRevisionOut(
                    id=r.id,
                    revision=r.revision,
                    instruction=r.instruction,
                    changed_fields=_parse_fields(r.changed_fields),
                    created_at=r.created_at,
                )
            )
    return VideoJobOut(
        id=job.id,
        scenario_id=job.scenario_id,
        status=job.status,
        script_snapshot=_parse_script(job.script_snapshot),
        audio_url=job.audio_path,
        video_url=job.video_path,
        preview_url=job.preview_path,
        error_message=job.error_message,
        is_mock=job.is_mock,
        revision=job.revision,
        critique=get_job_critique(job),
        scene_images=_scene_images(job.id),
        created_at=job.created_at,
        updated_at=job.updated_at,
        revisions=revs,
    )


@router.post("/produce", response_model=VideoJobOut, status_code=status.HTTP_201_CREATED)
async def produce(
    payload: ProduceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobOut:
    scenario = db.get(Scenario, payload.scenario_id)
    if scenario is None or scenario.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Senaryo bulunamadı")
    job = await produce_from_scenario(db, user, scenario)
    job = db.scalar(
        select(VideoJob)
        .where(VideoJob.id == job.id)
        .options(selectinload(VideoJob.revisions))
    )
    assert job is not None
    return _to_out(job)


@router.post("/{job_id}/refine", response_model=VideoJobOut)
async def refine(
    job_id: int,
    payload: RefineRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobOut:
    job = db.scalar(
        select(VideoJob)
        .where(VideoJob.id == job_id)
        .options(selectinload(VideoJob.revisions))
    )
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İş bulunamadı")
    job = await refine_job(db, user, job, payload.instruction)
    job = db.scalar(
        select(VideoJob)
        .where(VideoJob.id == job.id)
        .options(selectinload(VideoJob.revisions))
    )
    assert job is not None
    return _to_out(job)


@router.get("/{job_id}", response_model=VideoJobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobOut:
    job = db.scalar(
        select(VideoJob)
        .where(VideoJob.id == job_id)
        .options(selectinload(VideoJob.revisions))
    )
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İş bulunamadı")
    return _to_out(job)


@router.get("", response_model=list[VideoJobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VideoJobOut]:
    rows = db.scalars(
        select(VideoJob)
        .where(VideoJob.user_id == user.id)
        .options(selectinload(VideoJob.revisions))
        .order_by(VideoJob.created_at.desc())
        .limit(30)
    ).all()
    return [_to_out(r) for r in rows]
