"""Master AI Yönetmen — AI1 → AI2 → ses → AI3 + eleştiri."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import JobRevision, Scenario, User, VideoJob
from app.services.credits import apply_credit_change
from app.services.director.ai2_visuals import run_visual_agent
from app.services.director.ai3_editor import run_editor_agent
from app.services.director.critique import apply_critique_feedback, build_critique_report
from app.services.elevenlabs import synthesize_voiceover
from app.services.video import render_storyboard_video


def _media_root() -> Path:
    root = Path(get_settings().media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _parse_script(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _public(job_id: int, filename: str) -> str:
    return f"/media/jobs/{job_id}/{filename}"


def _save_critique(job_dir: Path, report: dict[str, Any]) -> None:
    (job_dir / "critique.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_critique(job_dir: Path) -> dict[str, Any] | None:
    p = job_dir / "critique.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


async def produce_from_scenario(
    db: Session,
    user: User,
    scenario: Scenario,
) -> VideoJob:
    settings = get_settings()
    if scenario.user_id != user.id:
        raise HTTPException(status_code=404, detail="Senaryo bulunamadı")

    script = _parse_script(scenario.professional_script)
    if not script:
        raise HTTPException(status_code=400, detail="Önce AI1 senaryosunu üretin")

    apply_credit_change(
        db, user, -settings.produce_credit_cost, "Master pipeline üretimi",
        reference_type="video_job",
    )

    job = VideoJob(
        user_id=user.id,
        scenario_id=scenario.id,
        status="producing",
        script_snapshot=json.dumps(script, ensure_ascii=False),
        revision=1,
    )
    db.add(job)
    db.flush()
    job_dir = _media_root() / "jobs" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # AI2 — görseller
        visual = await run_visual_agent(
            db, user,
            script=script,
            job_dir=job_dir,
            style=scenario.style,
            language=scenario.language,
        )
        script = visual["script"]

        # Ses (ElevenLabs / mock)
        voice_text = script.get("voiceover_full") or scenario.raw_input
        is_mock_audio = await synthesize_voiceover(
            db, user, text=voice_text, out_path=job_dir / "voice", language=scenario.language
        )
        audio_file = "voice.wav" if (job_dir / "voice.wav").exists() else "voice.mp3"

        # AI3 — kurgu
        edited = run_editor_agent(
            job_dir=job_dir,
            script=script,
            audio_path=job_dir / audio_file,
            duration_seconds=scenario.duration_seconds,
        )

        _, preview_rel = render_storyboard_video(
            job_dir=job_dir,
            script=script,
            audio_filename=audio_file,
            duration_seconds=scenario.duration_seconds,
        )

        is_mock = bool(visual.get("mock")) or is_mock_audio
        critique = build_critique_report(script, is_mock=is_mock)
        _save_critique(job_dir, critique)

        # scene image public urls
        scene_manifest = []
        for img in visual.get("images") or []:
            idx = img.get("index")
            scene_manifest.append(
                {
                    "index": idx,
                    "url": _public(job.id, f"scenes/scene_{int(idx):02d}.jpg"),
                }
            )
        (job_dir / "scenes_manifest.json").write_text(
            json.dumps(scene_manifest, ensure_ascii=False), encoding="utf-8"
        )

        job.script_snapshot = json.dumps(script, ensure_ascii=False)
        job.audio_path = _public(job.id, audio_file)
        job.video_path = _public(job.id, edited["video_file"])
        job.preview_path = _public(job.id, preview_rel)
        job.is_mock = is_mock
        job.status = "completed"
        job.error_message = None
        job.updated_at = datetime.now(timezone.utc)
        if hasattr(job, "critique_report"):
            job.critique_report = json.dumps(critique, ensure_ascii=False)

        scenario.status = "produced"
        scenario.professional_script = json.dumps(script, ensure_ascii=False)
        db.commit()
        db.refresh(job)
        return job
    except HTTPException:
        job.status = "failed"
        job.error_message = "Pipeline başarısız"
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline hatası: {exc}") from exc


async def refine_job(
    db: Session,
    user: User,
    job: VideoJob,
    instruction: str,
) -> VideoJob:
    settings = get_settings()
    if job.user_id != user.id:
        raise HTTPException(status_code=404, detail="İş bulunamadı")
    if not job.script_snapshot:
        raise HTTPException(status_code=400, detail="İş düzenlenemez")
    if job.status in ("producing", "refining", "pending"):
        raise HTTPException(status_code=409, detail="İş hâlâ işleniyor")

    apply_credit_change(
        db, user, -settings.refine_credit_cost, "Eleştiri ile revizyon",
        reference_type="video_job_refine", reference_id=str(job.id),
    )

    before = _parse_script(job.script_snapshot)
    job.status = "refining"
    db.flush()
    job_dir = _media_root() / "jobs" / str(job.id)

    try:
        feedback = await apply_critique_feedback(
            db, user, script=before, instruction=instruction.strip()
        )
        after = feedback["script"]
        targets = feedback["targets"]
        changed = feedback.get("changed_fields") or []

        rev_no = job.revision + 1
        db.add(
            JobRevision(
                job_id=job.id,
                revision=rev_no,
                instruction=instruction.strip(),
                changed_fields=json.dumps(
                    {"fields": changed, "targets": targets}, ensure_ascii=False
                ),
                script_before=json.dumps(before, ensure_ascii=False),
                script_after=json.dumps(after, ensure_ascii=False),
            )
        )
        job.script_snapshot = json.dumps(after, ensure_ascii=False)
        job.revision = rev_no

        scenario = db.get(Scenario, job.scenario_id)
        if scenario and scenario.user_id == user.id:
            scenario.professional_script = json.dumps(after, ensure_ascii=False)
            if after.get("title"):
                scenario.title = after["title"]
            scenario.status = "refined"

        only = targets.get("scene_indices") or None
        if targets.get("regen_visuals") or targets.get("regen_script"):
            visual = await run_visual_agent(
                db, user,
                script=after,
                job_dir=job_dir,
                style=scenario.style if scenario else "cinematic",
                language=scenario.language if scenario else "tr",
                only_indices=only if targets.get("regen_visuals") and only else None,
            )
            after = visual["script"]
            job.script_snapshot = json.dumps(after, ensure_ascii=False)

        audio_file = Path(job.audio_path or "voice.wav").name
        if targets.get("regen_audio"):
            voice_text = after.get("voiceover_full") or instruction
            is_mock = await synthesize_voiceover(
                db, user,
                text=voice_text,
                out_path=job_dir / "voice",
                language=scenario.language if scenario else "tr",
            )
            audio_file = "voice.wav" if (job_dir / "voice.wav").exists() else "voice.mp3"
            job.audio_path = _public(job.id, audio_file)
            job.is_mock = is_mock or job.is_mock

        edited = run_editor_agent(
            job_dir=job_dir,
            script=after,
            audio_path=job_dir / audio_file,
            duration_seconds=scenario.duration_seconds if scenario else 30,
        )
        _, preview_rel = render_storyboard_video(
            job_dir=job_dir,
            script=after,
            audio_filename=audio_file,
            duration_seconds=scenario.duration_seconds if scenario else 30,
        )

        critique = build_critique_report(after, is_mock=job.is_mock)
        critique["last_feedback"] = instruction.strip()
        critique["summary"] = feedback.get("summary")
        _save_critique(job_dir, critique)
        if hasattr(job, "critique_report"):
            job.critique_report = json.dumps(critique, ensure_ascii=False)

        job.video_path = _public(job.id, edited["video_file"])
        job.preview_path = _public(job.id, preview_rel)
        job.status = "completed"
        job.error_message = None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
    except HTTPException:
        job.status = "failed"
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=500, detail=f"Revizyon hatası: {exc}") from exc


def get_job_critique(job: VideoJob) -> dict[str, Any] | None:
    if getattr(job, "critique_report", None):
        try:
            return json.loads(job.critique_report)
        except (TypeError, json.JSONDecodeError):
            pass
    job_dir = _media_root() / "jobs" / str(job.id)
    return _load_critique(job_dir)
