"""Kalıp / tekrar tespiti ve temizleme — iç denetim; kullanıcıya sızdırılmaz."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Yasak ifadeler — mock ve canlı çıktıda temizlenir
BANNED_PHRASES: list[str] = [
    r"\bdur\.?\b",
    r"bunu yanlış yapıyorsun",
    r"fikir var,? ritim yok",
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
    r"tam tersini yapıyor",
    r"kimse söylemiyor ama",
]

CLICHE_PATTERNS = BANNED_PHRASES


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

    for pat in BANNED_PHRASES:
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


def _strip_banned(text: str, *, topic: str, variant: int) -> str:
    """Yasak kalıbı topic'e dayalı özgün cümleyle değiştir."""
    if not text:
        return text
    out = text
    for pat in BANNED_PHRASES:
        if re.search(pat, out, re.I):
            out = re.sub(pat, "", out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip(" —.-")
    if not out or len(out) < 12:
        seed = topic[:40] or "konu"
        alts = [
            f"{seed} için izleyicinin merak ettiği detay burada.",
            f"{seed} — kısa formatta anlatılması gereken net bir açı.",
            f"Bugün {seed} üzerine somut bir örnek gösteriyorum.",
        ]
        out = alts[variant % len(alts)]
    return out


def sanitize_script(script: dict[str, Any], *, topic: str = "") -> dict[str, Any]:
    """Nihai senaryodan yasak kalıpları temizle (konsey sonrası zorunlu)."""
    out = dict(script)
    variant = topic_variant_index(topic or str(out.get("title") or ""), 9)
    if out.get("hook"):
        out["hook"] = _strip_banned(str(out["hook"]), topic=topic, variant=variant)
    if out.get("cta"):
        out["cta"] = _strip_banned(str(out["cta"]), topic=topic, variant=variant + 1)
    scenes = []
    for i, sc in enumerate(out.get("scenes") or []):
        row = dict(sc)
        row["narration"] = _strip_banned(
            str(row.get("narration") or ""),
            topic=topic,
            variant=variant + i,
        )
        scenes.append(row)
    out["scenes"] = scenes
    narrations = [str(s.get("narration") or "") for s in scenes]
    out["voiceover_full"] = " ".join(n for n in narrations if n)
    if scenes and out.get("hook"):
        out["hook"] = str(out["hook"])[:160]
    return out


def topic_variant_index(raw_input: str, modulo: int) -> int:
    h = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % max(modulo, 1)
