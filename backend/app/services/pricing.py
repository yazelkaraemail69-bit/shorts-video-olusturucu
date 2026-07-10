"""Kredi fiyatlandırması — API COGS + SaaS marjına göre.

Kaynak birim maliyetler (yaklaşık, OpenRouter / ElevenLabs 2026):
  - Claude Sonnet 4: $3/M in + $15/M out → senaryo çağrısı ~$0.05
  - Flux.2 Pro: ilk MP $0.03 + sonraki $0.015 → 768×1344 (~1.03 MP) ≈ $0.045/görsel
  - ElevenLabs multilingual v2: $0.10 / 1K karakter → ~$0.0015/sn ses

1 kredi ≈ $0.01 perakende değer.
Hedef brüt marj ~65% (MARKUP ≈ 3.5×) platform anahtarı kullanıldığında.
BYOK olsa da orkestrasyon ücreti aynı kalır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.config import get_settings

# --- COGS (USD) ---
COGS_SCENARIO_USD = 0.05
COGS_IMAGE_USD = 0.045
COGS_TTS_PER_SEC_USD = 0.0015
COGS_DISCUSS_USD = 0.05
COGS_REFINE_BASE_USD = 0.10  # metin + ortalama 1–2 sahne yenileme varsayımı
COGS_COPY_UNLOCK_USD = 0.0

CREDIT_USD = 0.01
MARKUP = 3.5


def _round_credits(cogs_usd: float) -> int:
    raw = cogs_usd * MARKUP / CREDIT_USD
    return max(1, int(5 * round(raw / 5)))  # 5'in katına yuvarla


def scene_count_for_duration(duration_seconds: int) -> int:
    d = int(duration_seconds or 30)
    if d <= 15:
        return 4
    if d <= 30:
        return 5
    if d <= 45:
        return 6
    return 7


def produce_cogs_usd(duration_seconds: int) -> float:
    scenes = scene_count_for_duration(duration_seconds)
    d = max(5, int(duration_seconds or 30))
    return scenes * COGS_IMAGE_USD + d * COGS_TTS_PER_SEC_USD


def produce_credit_cost(duration_seconds: int) -> int:
    """Süreye göre üretim kredisi (görsel sayısı + TTS)."""
    settings = get_settings()
    computed = _round_credits(produce_cogs_usd(duration_seconds))
    ref_30 = _round_credits(produce_cogs_usd(30)) or 100
    configured_30 = settings.produce_credit_cost
    if configured_30 > 0 and ref_30 > 0:
        scaled = computed * (configured_30 / ref_30)
        return max(5, int(5 * round(scaled / 5)))
    return computed


def scenario_credit_cost() -> int:
    settings = get_settings()
    if settings.scenario_credit_cost > 0:
        return settings.scenario_credit_cost
    return _round_credits(COGS_SCENARIO_USD)


def discuss_credit_cost() -> int:
    settings = get_settings()
    if settings.discuss_credit_cost > 0:
        return settings.discuss_credit_cost
    return _round_credits(COGS_DISCUSS_USD)


def refine_credit_cost() -> int:
    settings = get_settings()
    if settings.refine_credit_cost > 0:
        return settings.refine_credit_cost
    return _round_credits(COGS_REFINE_BASE_USD)


def copy_unlock_credit_cost() -> int:
    settings = get_settings()
    if settings.copy_unlock_credit_cost > 0:
        return settings.copy_unlock_credit_cost
    return 5


@dataclass
class PricingTable:
    credit_usd: float
    markup: float
    scenario: int
    discuss: int
    refine: int
    copy_unlock: int
    produce_by_duration: dict[str, int]
    cogs_notes: dict[str, str]
    initial_credits: int
    full_30s_bundle: int


def build_pricing_table() -> PricingTable:
    settings = get_settings()
    produce_map = {
        str(d): produce_credit_cost(d) for d in (15, 20, 25, 30, 45, 60)
    }
    scenario = scenario_credit_cost()
    return PricingTable(
        credit_usd=CREDIT_USD,
        markup=MARKUP,
        scenario=scenario,
        discuss=discuss_credit_cost(),
        refine=refine_credit_cost(),
        copy_unlock=copy_unlock_credit_cost(),
        produce_by_duration=produce_map,
        cogs_notes={
            "scenario": f"Claude Sonnet 4 ≈ ${COGS_SCENARIO_USD:.2f}",
            "image": f"Flux.2 Pro 9:16 ≈ ${COGS_IMAGE_USD:.3f}/sahne",
            "tts": f"ElevenLabs ML v2 ≈ ${COGS_TTS_PER_SEC_USD:.4f}/sn",
            "produce_30s": (
                f"5 sahne + 30s ses ≈ ${produce_cogs_usd(30):.2f} COGS → "
                f"{produce_map['30']} kredi"
            ),
        },
        initial_credits=settings.initial_credits,
        full_30s_bundle=scenario + produce_map["30"],
    )


def pricing_dict() -> dict:
    return asdict(build_pricing_table())
