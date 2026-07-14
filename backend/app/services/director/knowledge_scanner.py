"""Anthropic Sonnet — kaynak tarama ve konsey eğitim özeti (AI-4).

İç süreç: kullanıcıya ham tarama / tartışma logu döndürülmez.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.models import SourceItem, SourcePack
from app.services.director.constitution import DIRECTOR_CONSTITUTION

logger = logging.getLogger(__name__)

KNOWLEDGE_SYSTEM = f"""
Sen AI-4: Shorts kaynak analistisin. Kullanıcının yüklediği dosya, görsel, PDF ve video linklerini tararsın.

{DIRECTOR_CONSTITUTION}

Görev:
- Marka/ürün/fikir hakkında somut bilgi çıkar.
- Diğer 3 yapay zekâya verilecek "eğitim özeti" üret (tartışma metni YAZMA).
- Yasak kalıp listesi oluştur (tekrar edilmemesi gereken ifadeler).
- Video linkleri için: URL + kullanıcı notunu referans olarak kaydet (içerik uydurma).

Yanıt SADECE JSON:
{{
  "brand_voice": "ton ve üslup",
  "key_facts": ["somut bilgi"],
  "visual_cues": ["görsel ipuçları"],
  "script_angles": ["Shorts açıları"],
  "do_not_say": ["yasak kalıp ifadeler"],
  "reference_urls": ["video/link"],
  "brief_for_council": "3 AI'ya verilecek kısa özet (max 800 karakter)"
}}
""".strip()


def _resolve_anthropic_key() -> str:
    key = get_settings().anthropic_api_key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anthropic API anahtarı gerekli (kaynak tarama için ANTHROPIC_API_KEY).",
        )
    return key


def _mock_knowledge_brief(pack: SourcePack, items: list[SourceItem]) -> dict[str, Any]:
    facts: list[str] = []
    urls: list[str] = []
    for it in items:
        if it.external_url:
            urls.append(it.external_url)
            facts.append(f"Video/link referansı: {it.external_url}")
        if it.extracted_text:
            facts.append(it.extracted_text[:240])
    brief = pack.name or "Kaynak paketi"
    return {
        "brand_voice": "Doğal, konuşma diline yakın, özgün",
        "key_facts": facts[:8] or [brief],
        "visual_cues": ["Brief'teki görselleri referans al", "9:16 dikey kadraj"],
        "script_angles": [f"{brief} için somut Shorts açısı"],
        "do_not_say": [
            "Dur.",
            "bunu yanlış yapıyorsun",
            "fikir var ritim yok",
            "Kaydet ve dene",
        ],
        "reference_urls": urls,
        "brief_for_council": (
            f"Kaynak özeti: {brief}. "
            + " ".join(facts[:3])[:600]
        ),
        "mock": True,
    }


async def anthropic_completion_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.7,
) -> dict[str, Any]:
    settings = get_settings()
    api_key = _resolve_anthropic_key()
    body = {
        "model": settings.anthropic_model,
        "max_tokens": 4096,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.anthropic_base_url}/messages",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anthropic bağlantı hatası: {exc}",
        ) from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anthropic hata ({resp.status_code}): {resp.text[:400]}",
        )

    data = resp.json()
    try:
        blocks = data["content"]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except (KeyError, json.JSONDecodeError, IndexError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Anthropic yanıtı parse edilemedi",
        ) from exc


def extract_text_from_file(path: Path, kind: str) -> str:
    """Basit metin çıkarımı (pdf/image stub)."""
    if kind == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            parts = [p.extract_text() or "" for p in reader.pages[:12]]
            return "\n".join(parts).strip()[:8000]
        except Exception:
            return ""
    if kind == "image":
        return f"[Görsel dosya: {path.name}]"
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:8000]
    except Exception:
        return ""


async def analyze_source_pack(pack: SourcePack, items: list[SourceItem]) -> dict[str, Any]:
    """Kaynakları tarayıp knowledge_brief üretir — iç kullanım."""
    settings = get_settings()
    if settings.mock_ai and not settings.anthropic_api_key:
        return _mock_knowledge_brief(pack, items)

    payload_items: list[dict[str, Any]] = []
    for it in items:
        entry: dict[str, Any] = {"kind": it.kind, "label": it.label}
        if it.external_url:
            entry["url"] = it.external_url
        if it.extracted_text:
            entry["text"] = it.extracted_text[:4000]
        payload_items.append(entry)

    user = (
        f"Paket adı: {pack.name}\n\n"
        f"Kaynaklar:\n{json.dumps(payload_items, ensure_ascii=False, indent=2)}"
    )
    return await anthropic_completion_json(KNOWLEDGE_SYSTEM, user)


def knowledge_for_council(knowledge_brief: dict[str, Any] | None) -> str:
    """Konsey prompt'una eklenecek güvenli özet — tartışma yok."""
    if not knowledge_brief:
        return ""
    brief = str(knowledge_brief.get("brief_for_council") or "").strip()
    facts = knowledge_brief.get("key_facts") or []
    banned = knowledge_brief.get("do_not_say") or []
    parts = []
    if brief:
        parts.append(f"KAYNAK ÖZETİ: {brief}")
    if facts:
        parts.append("SOMUT BİLGİLER: " + "; ".join(str(f) for f in facts[:6]))
    if banned:
        parts.append("ASLA KULLANMA: " + ", ".join(str(b) for b in banned[:12]))
    return "\n".join(parts)
