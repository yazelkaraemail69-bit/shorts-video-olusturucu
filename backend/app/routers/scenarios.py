from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_access import has_unlimited_credits
from app.database import get_db
from app.deps import get_current_user
from app.models import Scenario, User
from app.schemas import (
    DiscussionMessage,
    ScenarioDiscussRequest,
    ScenarioOut,
    ScenarioProfessionalizeRequest,
)
from app.services.credits import apply_credit_change
from app.services.director.ai1_scenario import run_scenario_agent
from app.services.director.critique import apply_critique_feedback, build_critique_report
from app.services.pricing import (
    copy_unlock_credit_cost,
    discuss_credit_cost,
    produce_credit_cost,
    scenario_credit_cost,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _parse_script(raw: str) -> dict:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {
            "title": "",
            "hook": "",
            "voiceover_full": raw,
            "music_mood": "",
            "cta": "",
            "scenes": [],
        }
    if data.get("_mock"):
        data = {**data, "mock": True}
        data.pop("_mock", None)
    return data


def _parse_discussion(raw: str | None) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _critique_to_message(critique: dict) -> str:
    strengths = critique.get("strengths") or []
    risks = critique.get("risks") or []
    suggestions = critique.get("suggestions") or []
    strength_lines = [f"• {x}" for x in strengths] or ["• —"]
    risk_lines = [f"• {x}" for x in risks] or ["• —"]
    suggestion_lines = [f"• {x}" for x in suggestions] or ["• —"]
    parts = [
        f"Eleştiri raporu — {critique.get('verdict') or 'inceleme'}",
        "",
        "Güçlü yanlar:",
        *strength_lines,
        "",
        "Riskler:",
        *risk_lines,
        "",
        "Öneriler:",
        *suggestion_lines,
        "",
        critique.get("how_to_reply")
        or "Ne değiştirmek istediğini yaz; ilgili kısmı güncelleyeyim.",
    ]
    return "\n".join(parts)


def _format_copy_text(script: dict, scenario: Scenario) -> str:
    lines = [
        f"# {script.get('title') or scenario.title or 'Senaryo'}",
        f"Dil: {scenario.language} | Süre: {scenario.duration_seconds}s | Üslup: {scenario.style}",
        "",
        f"HOOK: {script.get('hook') or ''}",
        "",
        "SESLENDİRME:",
        script.get("voiceover_full") or "",
        "",
        "SAHNELER:",
    ]
    for scene in script.get("scenes") or []:
        lines.append(
            f"- [{scene.get('timecode') or ''}] "
            f"Sahne {scene.get('index')} ({scene.get('role') or ''})"
        )
        lines.append(f"  Görsel: {scene.get('visual') or ''}")
        lines.append(f"  Anlatım: {scene.get('narration') or ''}")
        if scene.get("on_screen_text"):
            lines.append(f"  Ekran: {scene.get('on_screen_text')}")
    lines.extend(
        [
            "",
            f"Müzik: {script.get('music_mood') or ''}",
            f"CTA: {script.get('cta') or ''}",
        ]
    )
    if script.get("edit_notes"):
        lines.append(f"Kurgu notu: {script.get('edit_notes')}")
    return "\n".join(lines).strip() + "\n"


def _display_script(script: dict, unlocked: bool) -> dict:
    if unlocked:
        return script
    preview = dict(script)
    voice = str(preview.get("voiceover_full") or "")
    preview["voiceover_full"] = (voice[:120] + "…") if len(voice) > 120 else voice
    scenes = []
    for s in preview.get("scenes") or []:
        sc = dict(s)
        narr = str(sc.get("narration") or "")
        vis = str(sc.get("visual") or "")
        sc["narration"] = (narr[:80] + "…") if len(narr) > 80 else narr
        sc["visual"] = (vis[:80] + "…") if len(vis) > 80 else vis
        scenes.append(sc)
    preview["scenes"] = scenes
    return preview


def _to_out(row: Scenario, user: User | None = None) -> ScenarioOut:
    unlocked = bool(getattr(row, "copy_unlocked", False))
    if user is not None and has_unlimited_credits(user):
        unlocked = True

    full_script = _parse_script(row.professional_script)
    critique = build_critique_report(full_script, is_mock=bool(full_script.get("mock")))
    discussion_raw = _parse_discussion(getattr(row, "discussion_log", None))
    discussion = [
        DiscussionMessage(
            role=str(m.get("role") or "director"),
            content=str(m.get("content") or ""),
            summary=m.get("summary"),
            changed_fields=list(m.get("changed_fields") or []),
        )
        for m in discussion_raw
        if isinstance(m, dict)
    ]

    return ScenarioOut(
        id=row.id,
        language=row.language,
        title=row.title,
        duration_seconds=row.duration_seconds,
        style=row.style,
        audience=row.audience,
        raw_input=row.raw_input,
        professional_script=_display_script(full_script, unlocked),
        status=row.status,
        copy_unlocked=unlocked,
        copy_unlock_cost=copy_unlock_credit_cost(),
        produce_credit_cost=produce_credit_cost(row.duration_seconds),
        discuss_credit_cost=discuss_credit_cost(),
        critique=critique,
        discussion=discussion,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/professionalize", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def professionalize(
    payload: ScenarioProfessionalizeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    cost = scenario_credit_cost()
    apply_credit_change(
        db,
        user,
        -cost,
        "AI1 senaryo üretimi",
        reference_type="scenario",
        reference_id=None,
    )

    try:
        result = await run_scenario_agent(
            db,
            user,
            language=payload.language,
            title=payload.title,
            duration_seconds=payload.duration_seconds,
            style=payload.style,
            audience=payload.audience,
            raw_input=payload.raw_input.strip(),
        )
    except Exception as exc:  # noqa: BLE001
        apply_credit_change(
            db,
            user,
            cost,
            "Senaryo iadesi",
            reference_type="refund",
            reference_id=None,
            allow_negative=True,
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Senaryo hatası: {exc}",
        ) from exc

    script = result["script"]

    store = dict(script)
    is_mock = bool(store.pop("_mock", False))
    if is_mock:
        store["mock"] = True

    critique = build_critique_report(store, is_mock=is_mock)
    discussion = [
        {
            "role": "director",
            "content": _critique_to_message(critique),
            "summary": "İlk eleştiri raporu",
            "changed_fields": [],
            "at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    title = payload.title or store.get("title") or None
    row = Scenario(
        user_id=user.id,
        language=payload.language,
        title=title,
        duration_seconds=payload.duration_seconds,
        style=payload.style,
        audience=payload.audience,
        raw_input=payload.raw_input.strip(),
        professional_script=json.dumps(store, ensure_ascii=False),
        status="ready",
        copy_unlocked=has_unlimited_credits(user),
        discussion_log=json.dumps(discussion, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row, user)


@router.post("/{scenario_id}/discuss", response_model=ScenarioOut)
async def discuss_scenario(
    scenario_id: int,
    payload: ScenarioDiscussRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    row = db.get(Scenario, scenario_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Senaryo bulunamadı")

    cost = discuss_credit_cost()
    apply_credit_change(
        db,
        user,
        -cost,
        "Senaryo tartışma / revizyon",
        reference_type="scenario_discuss",
        reference_id=str(row.id),
    )

    before = _parse_script(row.professional_script)
    try:
        feedback = await apply_critique_feedback(
            db, user, script=before, instruction=payload.message.strip()
        )
    except Exception as exc:  # noqa: BLE001
        apply_credit_change(
            db,
            user,
            cost,
            "Tartışma iadesi",
            reference_type="refund",
            reference_id=str(row.id),
            allow_negative=True,
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tartışma hatası: {exc}",
        ) from exc

    after = feedback["script"]
    changed = feedback.get("changed_fields") or []
    summary = feedback.get("summary") or "Senaryo güncellendi."

    if after.get("title"):
        row.title = after["title"]
    row.professional_script = json.dumps(after, ensure_ascii=False)
    row.status = "discussed"
    row.updated_at = datetime.now(timezone.utc)

    discussion = _parse_discussion(row.discussion_log)
    now = datetime.now(timezone.utc).isoformat()
    discussion.append(
        {
            "role": "user",
            "content": payload.message.strip(),
            "summary": None,
            "changed_fields": [],
            "at": now,
        }
    )
    director_lines = [
        summary,
        "",
        f"Güncellenen alanlar: {', '.join(changed) if changed else 'genel dokunuş'}",
        "",
        "Başka neyi sıkılaştıralım? Hook, tempo, CTA veya belirli bir sahne söylemen yeterli.",
    ]
    discussion.append(
        {
            "role": "director",
            "content": "\n".join(director_lines),
            "summary": summary,
            "changed_fields": changed,
            "at": now,
        }
    )
    row.discussion_log = json.dumps(discussion, ensure_ascii=False)

    db.commit()
    db.refresh(row)
    return _to_out(row, user)


@router.post("/{scenario_id}/unlock-copy", response_model=ScenarioOut)
def unlock_copy(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    row = db.get(Scenario, scenario_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Senaryo bulunamadı")

    if row.copy_unlocked or has_unlimited_credits(user):
        row.copy_unlocked = True
        db.commit()
        db.refresh(row)
        return _to_out(row, user)

    apply_credit_change(
        db,
        user,
        -copy_unlock_credit_cost(),
        "Senaryo kopyalama kilidi",
        reference_type="scenario_copy_unlock",
        reference_id=str(row.id),
    )
    row.copy_unlocked = True
    db.commit()
    db.refresh(row)
    return _to_out(row, user)


@router.get("/{scenario_id}/copy-text")
def get_copy_text(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Scenario, scenario_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Senaryo bulunamadı")
    if not row.copy_unlocked and not has_unlimited_credits(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Kopyalamak için önce kilidi açın",
        )
    script = _parse_script(row.professional_script)
    return {"text": _format_copy_text(script, row), "scenario_id": row.id}


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScenarioOut]:
    rows = db.scalars(
        select(Scenario)
        .where(Scenario.user_id == user.id)
        .order_by(Scenario.created_at.desc())
        .limit(50)
    ).all()
    return [_to_out(r, user) for r in rows]


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioOut:
    row = db.get(Scenario, scenario_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Senaryo bulunamadı")
    return _to_out(row, user)
