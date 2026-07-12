"""Kaynak paketi — video link, görsel, PDF yükleme ve Anthropic tarama."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import SourceItem, SourcePack, User
from app.schemas import SourceItemOut, SourcePackOut
from app.services.director.knowledge_scanner import analyze_source_pack, extract_text_from_file

router = APIRouter(prefix="/sources", tags=["sources"])

ALLOWED_EXT = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".pdf",
    ".txt",
    ".md",
}


def _pack_dir(user_id: int, pack_id: int) -> Path:
    root = Path(get_settings().media_dir) / "sources" / str(user_id) / str(pack_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_out(pack: SourcePack) -> SourcePackOut:
    try:
        kb = json.loads(pack.knowledge_brief or "{}")
    except json.JSONDecodeError:
        kb = {}
    return SourcePackOut(
        id=pack.id,
        name=pack.name,
        status=pack.status,
        item_count=len(pack.items),
        knowledge_ready=pack.status == "ready",
        has_brief=bool(kb.get("brief_for_council")),
        error_message=pack.error_message,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
    )


@router.get("/packs", response_model=list[SourcePackOut])
def list_packs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SourcePackOut]:
    rows = db.scalars(
        select(SourcePack)
        .where(SourcePack.user_id == user.id)
        .options(selectinload(SourcePack.items))
        .order_by(SourcePack.id.desc())
    ).all()
    return [_to_out(r) for r in rows]


@router.post("/packs", response_model=SourcePackOut, status_code=status.HTTP_201_CREATED)
def create_pack(
    name: str = Form(default="Kaynak paketi"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourcePackOut:
    pack = SourcePack(user_id=user.id, name=name.strip()[:200] or "Kaynak paketi")
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return _to_out(pack)


@router.post("/packs/{pack_id}/items/url", response_model=SourceItemOut)
def add_video_url(
    pack_id: int,
    url: str = Form(...),
    label: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceItemOut:
    pack = db.scalar(
        select(SourcePack)
        .where(SourcePack.id == pack_id, SourcePack.user_id == user.id)
        .options(selectinload(SourcePack.items))
    )
    if not pack:
        raise HTTPException(status_code=404, detail="Kaynak paketi bulunamadı")
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Geçerli bir video/link URL'si girin")
    item = SourceItem(
        pack_id=pack.id,
        kind="video_url",
        label=label or u[:120],
        external_url=u,
        extracted_text=f"Video/link referansı: {u}",
    )
    db.add(item)
    pack.status = "pending"
    db.commit()
    db.refresh(item)
    return SourceItemOut(
        id=item.id,
        kind=item.kind,
        label=item.label,
        external_url=item.external_url,
    )


@router.post("/packs/{pack_id}/items/upload", response_model=SourceItemOut)
async def upload_file(
    pack_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceItemOut:
    pack = db.scalar(
        select(SourcePack)
        .where(SourcePack.id == pack_id, SourcePack.user_id == user.id)
        .options(selectinload(SourcePack.items))
    )
    if not pack:
        raise HTTPException(status_code=404, detail="Kaynak paketi bulunamadı")

    suffix = Path(file.filename or "file").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenen türler: {', '.join(sorted(ALLOWED_EXT))}",
        )

    kind = "pdf" if suffix == ".pdf" else ("image" if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else "file")
    dest_dir = _pack_dir(user.id, pack.id)
    safe_name = f"{kind}_{len(pack.items) + 1:02d}{suffix}"
    dest = dest_dir / safe_name

    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    extracted = extract_text_from_file(dest, kind)
    item = SourceItem(
        pack_id=pack.id,
        kind=kind,
        label=file.filename,
        storage_path=str(dest.relative_to(Path(get_settings().media_dir))),
        extracted_text=extracted or None,
    )
    db.add(item)
    pack.status = "pending"
    db.commit()
    db.refresh(item)
    return SourceItemOut(
        id=item.id,
        kind=item.kind,
        label=item.label,
        external_url=item.external_url,
    )


@router.post("/packs/{pack_id}/analyze", response_model=SourcePackOut)
async def analyze_pack(
    pack_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourcePackOut:
    pack = db.scalar(
        select(SourcePack)
        .where(SourcePack.id == pack_id, SourcePack.user_id == user.id)
        .options(selectinload(SourcePack.items))
    )
    if not pack:
        raise HTTPException(status_code=404, detail="Kaynak paketi bulunamadı")
    if not pack.items:
        raise HTTPException(status_code=400, detail="Önce en az bir kaynak ekleyin")

    pack.status = "analyzing"
    pack.error_message = None
    db.commit()

    try:
        brief = await analyze_source_pack(pack, list(pack.items))
        pack.knowledge_brief = json.dumps(brief, ensure_ascii=False)
        pack.status = "ready"
    except HTTPException as exc:
        pack.status = "failed"
        pack.error_message = str(exc.detail)
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        pack.status = "failed"
        pack.error_message = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=500, detail=f"Kaynak tarama hatası: {exc}") from exc

    db.commit()
    db.refresh(pack)
    return _to_out(pack)


def load_knowledge_brief(db: Session, user_id: int, pack_id: int | None) -> dict | None:
    if not pack_id:
        return None
    pack = db.scalar(
        select(SourcePack).where(SourcePack.id == pack_id, SourcePack.user_id == user_id)
    )
    if not pack or pack.status != "ready":
        return None
    try:
        return json.loads(pack.knowledge_brief or "{}")
    except json.JSONDecodeError:
        return None
