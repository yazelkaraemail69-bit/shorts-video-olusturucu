"""Tartışma / Eleştiri modülü — rapor + kısmi revizyon hedefleri."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.services.director.cliche_guard import detect_cliches
from app.services.director.integration import resolve_openrouter_key, verify_openrouter
from app.services.refine import refine_script


def _analyze_pace(scenes: list[dict[str, Any]], duration: float = 30.0) -> dict[str, Any]:
    """Sahne bazlı pace/ritim analizi."""
    if not scenes:
        return {"score": 0, "issues": ["Sahne yok"]}

    scores = []
    issues: list[str] = []
    prev_time = 0.0

    for i, s in enumerate(scenes):
        timecode = str(s.get("timecode") or "")
        m = re.search(r"(\d+(?:\.\d+)?)", timecode)
        current_time = float(m.group(1)) if m else prev_time + (duration / max(1, len(scenes)))
        scene_dur = current_time - prev_time

        if scene_dur < 1.5:
            issues.append(f"Sahne {s.get('index')}: çok kısa ({scene_dur:.1f}s), izleyici algılayamayabilir.")
            scores.append(3)
        elif scene_dur > 6:
            issues.append(f"Sahne {s.get('index')}: çok uzun ({scene_dur:.1f}s), Shorts temposu için ağır.")
            scores.append(4)
        else:
            scores.append(8 if 2 <= scene_dur <= 4 else 6)

        prev_time = current_time

    # voiceover_full uzunluğu kontrolü
    avg_score = sum(scores) / len(scores) if scores else 5

    if avg_score < 5:
        issues.append("Genel tempo zayıf: sahneler ya çok kısa ya çok uzun.")
    elif avg_score >= 7:
        issues.append("Tempo iyi: Shorts ritmine uygun.")

    return {"score": round(avg_score, 1), "issues": issues}


def _analyze_visual_richness(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Görsel tariflerin zenginliğini analiz et."""
    if not scenes:
        return {"score": 0, "issues": ["Sahne yok"]}

    scores = []
    issues: list[str] = []

    for s in scenes:
        visual = str(s.get("visual") or "")
        idx = s.get("index")

        # Kamera açısı var mı?
        has_camera = any(
            k in visual.lower()
            for k in ("close-up", "wide", "low-angle", "bird", "pov", "over-shoulder", "dutch", "aerial", "shot")
        )
        # Işık tonu var mı?
        has_lighting = any(
            k in visual.lower()
            for k in ("light", "shadow", "chiaroscuro", "backlit", "neon", "golden", "ambient", "diffuse")
        )
        # Kompozisyon var mı?
        has_composition = any(
            k in visual.lower()
            for k in ("rule of thirds", "leading", "frame", "depth", "symmetry", "asymmetry", "negative space")
        )
        # Renk bilgisi var mı?
        has_color = any(
            k in visual.lower()
            for k in ("color", "ton", "palette", "warm", "cold", "monochrome", "vibrant", "muted", "amber")
        )
        # Hareket / cut var mı?
        has_motion = any(
            k in visual.lower()
            for k in ("push", "track", "pan", "whip", "zoom", "handheld", "gimbal", "slow-mo", "ramp", "crane")
        )

        detail_count = sum([has_camera, has_lighting, has_composition, has_color, has_motion])
        score = detail_count * 2  # 0-10 arası

        if score <= 2:
            issues.append(f"Sahne {idx}: görsel tarif çok zayıf — kamera açısı, ışık, kompozisyon ekle.")
        elif score <= 4:
            issues.append(f"Sahne {idx}: görsel tarif yetersiz — en az 2-3 sinematik öğe ekle.")

        scores.append(min(10, score))

    avg = sum(scores) / len(scores) if scores else 0

    if avg >= 7:
        issues.append("Görsel tarifler zengin: sinematik detay seviyesi iyi.")
    elif avg >= 4:
        issues.append("Görsel tarifler orta: daha fazla kamera açısı ve ışık detayı eklenebilir.")
    else:
        issues.append("Görsel tarifler fakir: tüm sahneler için kamera+ışık+kompozisyon zorunlu.")

    return {"score": round(avg, 1), "issues": issues}


def _analyze_cuts(scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Cut tiplerinin çeşitliliğini analiz et."""
    if not scenes:
        return {"score": 0, "issues": []}

    cuts = set()
    for s in scenes:
        cut = str(s.get("cut") or "").lower().strip()
        if cut:
            cuts.add(cut)

    issues: list[str] = []
    if len(cuts) <= 1:
        issues.append(f"Tek tip cut ({', '.join(cuts) if cuts else 'belirtilmemiş'}). Farklı cut tipleri dene.")
        score = 3
    elif len(cuts) <= 2:
        issues.append(f"Sadece {len(cuts)} farklı cut tipi var. Daha fazla çeşitlilik önerilir.")
        score = 5
    else:
        issues.append(f"{len(cuts)} farklı cut tipi — iyi çeşitlilik.")
        score = 8

    return {"score": score, "issues": issues, "cuts_used": list(cuts)}


def _analyze_hook_cta(script: dict[str, Any]) -> dict[str, Any]:
    """Hook ve CTA analizi."""
    issues: list[str] = []
    scores = []

    hook = str(script.get("hook") or "")
    cta = str(script.get("cta") or "")

    if len(hook) < 15:
        issues.append("Hook çok kısa — ilk 3 saniyede scroll'u durdurmak için daha güçlü bir açılış lazım.")
        scores.append(3)
    elif 15 <= len(hook) <= 80:
        issues.append("Hook uzunluğu ideal.")
        scores.append(8)
    else:
        issues.append("Hook çok uzun — 3 saniyede okunamaz.")
        scores.append(4)

    if not cta:
        issues.append("CTA eksik — kapanışta net bir eylem çağrısı olmalı.")
        scores.append(1)
    elif len(cta) < 10:
        issues.append("CTA kısa ve öz — iyi.")
        scores.append(8)
    elif len(cta) > 40:
        issues.append("CTA çok uzun — tek eylem, max 5-6 kelime.")
        scores.append(4)
    else:
        scores.append(7)

    avg_score = sum(scores) / len(scores) if scores else 5
    return {"score": round(avg_score, 1), "issues": issues}


def build_critique_report(script: dict[str, Any], *, is_mock: bool = False) -> dict[str, Any]:
    """Video sonrası otomatik eleştiri raporu (yönetmen notları)."""
    scenes = script.get("scenes") or []
    strengths: list[str] = []
    risks: list[str] = []
    suggestions: list[str] = []

    if script.get("hook"):
        strengths.append("Hook tanımlı — ilk 3 sn için net bir giriş var.")
    else:
        risks.append("Hook zayıf veya eksik.")

    if script.get("cta"):
        strengths.append(f"CTA mevcut: “{script.get('cta')}”.")
    else:
        risks.append("CTA yok — kapanış eylemi eklenmeli.")

    if len(scenes) < 4:
        risks.append("Sahne sayısı Shorts için az; ritim zayıf kalabilir.")
    elif len(scenes) > 7:
        risks.append("Sahne sayısı yüksek; tempo yavaşlayabilir.")
    else:
        strengths.append(f"{len(scenes)} sahne — Shorts ritmine uygun aralık.")

    narrations = [str(s.get("narration") or "") for s in scenes]
    if len(narrations) >= 2 and len(set(narrations)) < len(narrations):
        risks.append("Bazı sahnelerde anlatım tekrarı var.")
        suggestions.append("Tekrarlayan narration'ları farklı role göre yeniden yaz.")

    voiceover = str(script.get("voiceover_full") or "")
    if voiceover:
        # voiceover ile narration'ların uyumu
        combined_narrations = " ".join(narrations)
        if len(voiceover) > len(combined_narrations) * 1.3:
            suggestions.append("voiceover_full, narration'ların birleşiminden çok uzun. Kısalt.")
        elif len(voiceover) < len(combined_narrations) * 0.7:
            suggestions.append("voiceover_full, narration'ları tam kapsamıyor. Eksik parçalar olabilir.")

    clichés = detect_cliches(script)
    if clichés:
        risks.append("Metinde sık kullanılan kalıp ifadeler tespit edildi.")
        suggestions.append("Hook ve sahneleri daha özgün, konuşma diline yakın yeniden yaz.")

    for s in scenes:
        if not s.get("visual") or len(str(s.get("visual"))) < 20:
            risks.append(f"Sahne {s.get('index')}: görsel tarif zayıf.")
        if not s.get("image"):
            suggestions.append(f"Sahne {s.get('index')} için görsel yeniden üretilebilir.")

    # Gelişmiş analizler
    pace_analysis = _analyze_pace(scenes)
    visual_analysis = _analyze_visual_richness(scenes)
    cut_analysis = _analyze_cuts(scenes)
    hook_cta_analysis = _analyze_hook_cta(script)

    # Kalite skoru (0-10)
    quality_score = round(
        (
            pace_analysis["score"]
            + visual_analysis["score"]
            + cut_analysis["score"]
            + hook_cta_analysis["score"]
        )
        / 4,
        1,
    )

    # Riskleri ve önerileri analizlerden ekle
    for issue in pace_analysis["issues"]:
        if "iyi" in issue.lower():
            strengths.append(issue)
        else:
            risks.append(issue)

    for issue in visual_analysis["issues"]:
        if "zengin" in issue.lower():
            strengths.append(issue)
        else:
            risks.append(issue)

    for issue in cut_analysis["issues"]:
        if "iyi" in issue.lower():
            strengths.append(issue)
        else:
            suggestions.append(issue)

    for issue in hook_cta_analysis["issues"]:
        if "ideal" in issue.lower() or "iyi" in issue.lower():
            strengths.append(issue)
        else:
            risks.append(issue)

    if not suggestions:
        suggestions.extend(
            [
                "Tempo yavaşsa: 'sahne X daha hızlı' de — sadece o sahne kısalır.",
                "Görsel zayıfsa: 'sahne X daha çarpıcı görsel' de — AI2 yalnız o kareyi yeniler.",
                "CTA zayıfsa: yeni kapanış cümlesini yaz — kurgu yeniden birleşir.",
                "Cut çeşitliliği: 'sahne X'e smash cut ekle' dene.",
                "Renk paleti: 'sahne X daha sıcak tonlar' ile atmosfer değiştir.",
            ]
        )

    return {
        "title": "Eleştiri Raporu",
        "verdict": "revize_edilebilir" if risks else "yayına_yakın",
        "quality_score": quality_score,
        "breakdown": {
            "pace": pace_analysis,
            "visual_richness": visual_analysis,
            "cuts": cut_analysis,
            "hook_cta": hook_cta_analysis,
        },
        "strengths": strengths,
        "risks": risks,
        "suggestions": suggestions,
        "scene_count": len(scenes),
        "mock": is_mock,
        "how_to_reply": (
            "Örn: 'Sahne 2 çok yavaş', 'Hook daha çarpıcı olsun', "
            "'Sahne 3 görselini daha sinematik yap', 'Cut çeşitliliği ekle', "
            "'Sahne 4 için farklı kamera açısı dene'"
        ),
    }


def parse_feedback_targets(instruction: str, script: dict[str, Any]) -> dict[str, Any]:
    """Kullanıcı eleştirisinden hangi parçaların yenileneceğini çıkar."""
    lower = instruction.lower()
    scene_ids: list[int] = []
    for m in re.finditer(r"(?:sahne|scene)\s*#?\s*(\d+)", lower):
        scene_ids.append(int(m.group(1)))

    want_visuals = any(
        k in lower
        for k in ("görsel", "visual", "image", "çarpıcı", "sinematik", "kare", "shot", "kamera", "ışık", "renk")
    )
    want_script = any(
        k in lower
        for k in (
            "yavaş", "hızlı", "tempo", "hook", "cta", "metin", "anlat",
            "senaryo", "narration", "ses", "cut", "geçiş", "dil", "üslup",
        )
    )
    # Varsayılan: metin revizyonu
    if not want_visuals and not want_script:
        want_script = True

    if want_visuals and not scene_ids:
        # tüm sahneler yerine son/orta sahne varsayımı yerine hepsi değil — ilk problem sahnesi
        scenes = script.get("scenes") or []
        if scenes:
            scene_ids = [int(scenes[min(1, len(scenes) - 1)].get("index") or 1)]

    return {
        "regen_script": want_script,
        "regen_visuals": want_visuals,
        "scene_indices": scene_ids,
        "regen_audio": want_script or any(k in lower for k in ("ses", "voice", "anlat")),
    }


async def apply_critique_feedback(
    db: Session,
    user: User,
    *,
    script: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    settings = get_settings()
    api_key = resolve_openrouter_key(db, user)
    if not settings.mock_ai:
        await verify_openrouter(api_key)

    targets = parse_feedback_targets(instruction, script)
    result = await refine_script(db, user, script=script, instruction=instruction)
    return {
        "script": result["script"],
        "changed_fields": result.get("changed_fields") or [],
        "summary": result.get("summary") or "",
        "targets": targets,
    }