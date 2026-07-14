from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiKey, ApiProvider, User
from app.security import decrypt_api_key


def resolve_openrouter_key(db: Session, user: User) -> str | None:
    row = db.scalar(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == ApiProvider.openrouter,
        )
    )
    if row:
        return decrypt_api_key(row.key_encrypted)
    return get_settings().openrouter_api_key or None


def resolve_elevenlabs_key(db: Session, user: User) -> str | None:
    row = db.scalar(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.provider == ApiProvider.elevenlabs,
        )
    )
    if row:
        return decrypt_api_key(row.key_encrypted)
    return get_settings().elevenlabs_api_key or None


async def verify_openrouter(api_key: str | None) -> dict[str, Any]:
    """Her aşama öncesi OpenRouter bağlantı kontrolü."""
    settings = get_settings()
    if settings.mock_ai:
        return {"ok": True, "mode": "mock", "detail": "MOCK_AI=true — canlı API atlandı"}

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "OpenRouter API anahtarı yok. Ayarlardan kaydedin veya "
                ".env içine OPENROUTER_API_KEY ekleyin."
            ),
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenRouter rate limit — biraz bekleyip tekrar deneyin.",
        )
    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OpenRouter API anahtarı geçersiz.",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter doğrulama hatası ({resp.status_code}): {resp.text[:300]}",
        )

    return {"ok": True, "mode": "live", "detail": "OpenRouter bağlantısı doğrulandı"}
