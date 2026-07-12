"""Kalıp / tekrar tespiti — iç denetim; kullanıcıya sızdırılmaz."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Sık tekrarlanan zayıf kalıplar (TR + EN)
CLICHE_PATTERNS: list[str] = [
    r"\bdur\.?\b",
    r"asıl sorun",
    r"işte kanıt",
    r"kaydet.*dene",
    r"çoğu .* aynı hat",
    r"bu videoda",
    r"merak etme",
    r"stop scrolling",
    r"here'?s the (fix|shift|proof)",
    r"save this",
    r"try it on your next",
    r"her saniye iş yapsın",
    r"kırılma noktası",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def detect_cliches(script: dict[str, Any]) -> list[str]:
    """Bulunan kalıp uyarıları (iç kullanım)."""
    hits: list[str] = []
    blob_parts = [
        str(script.get("hook") or ""),
        str(script.get("voiceover_full") or ""),
        str(script.get("cta") or ""),
    ]
    for sc in script.get("scenes") or []:
        blob_parts.append(str(sc.get("narration") or ""))
    blob = _norm(" ".join(blob_parts))

    for pat in CLICHE_PATTERNS:
        if re.search(pat, blob, re.I):
            hits.append(pat)

    narrations = [_norm(str(s.get("narration") or "")) for s in script.get("scenes") or []]
    if len(narrations) >= 2:
        for i, a in enumerate(narrations):
            for b in narrations[i + 1 :]:
                if a and a == b:
                    hits.append("duplicate_narration")
                    break

    return hits


def topic_variant_index(raw_input: str, modulo: int) -> int:
    h = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % max(modulo, 1)


def rewrite_cliche_narration(text: str, *, language: str, variant: int) -> str:
    """Mock/iç düzeltme için alternatif cümle havuzu."""
    tr = not language.lower().startswith("en")
    if tr:
        alts = [
            text.replace("Dur.", "Bekle —").replace("dur.", "bekle —"),
            re.sub(r"Çoğu .* tekrar ediyor:", "Şunu fark ettim:", text, flags=re.I),
            re.sub(r"Asıl sorun", "Mesele şurada", text, flags=re.I),
            re.sub(r"Kaydet\.", "Not al.", text, flags=re.I),
        ]
    else:
        alts = [
            text.replace("Stop scrolling", "Hold up"),
            re.sub(r"Most .* waste time", "People miss this part", text, flags=re.I),
            re.sub(r"Save this", "Bookmark this", text, flags=re.I),
        ]
    pick = alts[variant % len(alts)]
    return pick if pick != text else text
