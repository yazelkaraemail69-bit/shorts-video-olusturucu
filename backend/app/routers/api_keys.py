from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import ApiKey, ApiProvider, User
from app.schemas import ApiKeyOut, ApiKeyUpsert, MessageOut
from app.security import api_key_hint, encrypt_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    return list(
        db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.provider)).all()
    )


@router.put("", response_model=ApiKeyOut)
def upsert_key(
    payload: ApiKeyUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKey:
    existing = db.scalar(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == payload.provider,
        )
    )
    encrypted = encrypt_api_key(payload.api_key.strip())
    hint = api_key_hint(payload.api_key.strip())

    if existing:
        existing.key_encrypted = encrypted
        existing.key_hint = hint
        db.commit()
        db.refresh(existing)
        return existing

    row = ApiKey(
        user_id=user.id,
        provider=payload.provider,
        key_encrypted=encrypted,
        key_hint=hint,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{provider}", response_model=MessageOut)
def delete_key(
    provider: ApiProvider,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    row = db.scalar(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.provider == provider)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anahtar bulunamadı")
    db.delete(row)
    db.commit()
    return MessageOut(detail=f"{provider.value} anahtarı silindi")
