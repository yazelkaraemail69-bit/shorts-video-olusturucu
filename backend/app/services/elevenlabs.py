from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.integration import resolve_elevenlabs_key


def _write_mock_wav(path: Path, text: str, duration_hint: float = 3.0) -> None:
    """Basit bip tonu — gerçek TTS yokken önizleme için."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050
    duration = max(2.0, min(12.0, duration_hint + len(text) * 0.02))
    frequency = 440.0
    n_samples = int(sample_rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            # Yumuşak envelope + hafif frekans kayması
            t = i / sample_rate
            env = min(1.0, t * 4) * min(1.0, (duration - t) * 4)
            freq = frequency + 40 * math.sin(t * 1.5)
            sample = int(12000 * env * math.sin(2 * math.pi * freq * t))
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)


async def synthesize_voiceover(
    db: Session,
    user: User,
    *,
    text: str,
    out_path: Path,
    language: str = "tr",
) -> bool:
    """
    ElevenLabs TTS. Dönüş: is_mock.
    MOCK_AI=true ise her zaman mock WAV üretir.
    """
    settings = get_settings()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.mock_ai:
        _write_mock_wav(out_path.with_suffix(".wav"), text)
        return True

    api_key = resolve_elevenlabs_key(db, user)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ElevenLabs API anahtarı yok. Ayarlardan ekleyin, .env'e ELEVENLABS_API_KEY koyun veya MOCK_AI=true kullanın.",
        )

    url = (
        f"{settings.elevenlabs_base_url}/text-to-speech/"
        f"{settings.elevenlabs_voice_id}"
    )
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ElevenLabs bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ElevenLabs hata ({resp.status_code}): {resp.text[:400]}",
        )

    mp3_path = out_path.with_suffix(".mp3")
    mp3_path.write_bytes(resp.content)
    return False
