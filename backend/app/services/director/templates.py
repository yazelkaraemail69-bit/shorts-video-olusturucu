"""Video şablonları — hazır stil/ritim/efekt kombinasyonları."""

from __future__ import annotations

from typing import Any


VIDEO_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "hizli-egitim",
        "name": "📚 Hızlı Eğitim",
        "description": "Bilgi aktarımı için optimize edilmiş — hızlı kesmeler, net metin, sakin müzik",
        "style": "egitici",
        "duration": 30,
        "scene_count": 5,
        "music_mood": "calm",
        "cut_style": "hard-cut",
        "caption_style": "kinetic",
        "energy": "orta",
        "ideal_for": "Nasıl yapılır, ipuçları, püf noktaları",
    },
    {
        "id": "viral-meydan-okuma",
        "name": "🔥 Viral Meydan Okuma",
        "description": "Scroll'u durduran hook, hızlı tempo, yüksek enerji, punchy efektler",
        "style": "punchy",
        "duration": 20,
        "scene_count": 6,
        "music_mood": "energetic",
        "cut_style": "smash-cut,whip-pan,zoom-punch",
        "caption_style": "neon",
        "energy": "çok yüksek",
        "ideal_for": "Meydan okumalar, trendler, şov",
    },
    {
        "id": "sinematik-hikaye",
        "name": "🎬 Sinematik Hikaye",
        "description": "Yavaş tempo, crossfade geçişler, ambient müzik, duygusal anlatım",
        "style": "hikaye",
        "duration": 45,
        "scene_count": 5,
        "music_mood": "mysterious",
        "cut_style": "cross-dissolve,match-cut",
        "caption_style": "kinetic",
        "energy": "düşük-orta",
        "ideal_for": "Hikayeler, kişisel deneyimler, motivasyon",
    },
    {
        "id": "urun-tanitimi",
        "name": "📦 Ürün Tanıtımı",
        "description": "Ürün odaklı, clean görseller, net CTA, hızlı demo",
        "style": "minimal",
        "duration": 25,
        "scene_count": 4,
        "music_mood": "uplifting",
        "cut_style": "hard-cut,J-cut",
        "caption_style": "neon",
        "energy": "orta-yüksek",
        "ideal_for": "Ürün lansmanı, özellik tanıtımı, inceleme",
    },
    {
        "id": "mizah-sketch",
        "name": "😂 Mizah Sketch",
        "description": "Keskin espriler, hızlı geçişler, eğlenceli müzik, abartılı efektler",
        "style": "eglenceli",
        "duration": 20,
        "scene_count": 5,
        "music_mood": "fun",
        "cut_style": "smash-cut,whip-pan,zoom-punch",
        "caption_style": "neon",
        "energy": "yüksek",
        "ideal_for": "Skeçler, parodiler, komik anlar",
    },
    {
        "id": "bilim-teknik",
        "name": "🔬 Bilim & Teknoloji",
        "description": "Temiz görseller, cool renk paleti, bilimsel ton, hızlı bilgi akışı",
        "style": "teknoloji",
        "duration": 35,
        "scene_count": 6,
        "music_mood": "cinematic",
        "cut_style": "hard-cut,match-cut,J-cut",
        "caption_style": "kinetic",
        "energy": "orta",
        "ideal_for": "Bilim, teknoloji, keşifler, açıklamalar",
    },
    {
        "id": "dogal-vlog",
        "name": "🌿 Doğal Vlog",
        "description": "Sakin tempo, doğal ışık, samimi anlatım, organik geçişler",
        "style": "dogal",
        "duration": 40,
        "scene_count": 5,
        "music_mood": "calm",
        "cut_style": "cross-dissolve,J-cut",
        "caption_style": "kinetic",
        "energy": "düşük",
        "ideal_for": "Vlog, günlük rutin, seyahat",
    },
    {
        "id": "vintage-estetik",
        "name": "📽️ Vintage Estetik",
        "description": "Sıcak tonlar, film grain, retro his, yavaş romantik tempo",
        "style": "vintage",
        "duration": 30,
        "scene_count": 4,
        "music_mood": "mysterious",
        "cut_style": "cross-dissolve,match-cut",
        "caption_style": "neon",
        "energy": "düşük",
        "ideal_for": "Retro temalar, throwback, estetik içerik",
    },
    {
        "id": "hizli-shots",
        "name": "⚡ Hızlı Shot'lar",
        "description": "Süper hızlı kesmeler, 2-3 saniye sahneler, maksimum enerji",
        "style": "punchy",
        "duration": 15,
        "scene_count": 7,
        "music_mood": "punchy",
        "cut_style": "smash-cut,zoom-punch,whip-pan",
        "caption_style": "neon",
        "energy": "çok yüksek",
        "ideal_for": "Short highlight, özet, teaser",
    },
]


def get_template(template_id: str) -> dict[str, Any] | None:
    """ID'ye göre şablon döndür."""
    for t in VIDEO_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def apply_template(template_id: str, base_script: dict[str, Any]) -> dict[str, Any]:
    """Şablonu senaryoya uygula — stil, müzik, cut tiplerini ayarla."""
    template = get_template(template_id)
    if not template:
        return base_script

    script = dict(base_script)
    script["style"] = template["style"]
    script["music_mood"] = template["music_mood"]
    script["edit_notes"] = (
        f"Şablon: {template['name']}. "
        f"Cut: {template['cut_style']}. "
        f"Caption: {template['caption_style']}. "
        f"Enerji: {template['energy']}."
    )

    # Cut tiplerini sahnelere dağıt
    cut_styles = [c.strip() for c in template["cut_style"].split(",")]
    scenes = script.get("scenes") or []
    for i, scene in enumerate(scenes):
        scene["cut"] = cut_styles[i % len(cut_styles)]

    script["scenes"] = scenes
    return script


def list_templates() -> list[dict[str, Any]]:
    """Tüm şablonları listele."""
    return VIDEO_TEMPLATES