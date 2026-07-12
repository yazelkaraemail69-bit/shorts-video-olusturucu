"""Konsey pipeline mock test — iç süreç kullanıcıya sızdırılmaz."""

from __future__ import annotations

import asyncio
import json

from app.database import init_db
from app.services.director.cliche_guard import detect_cliches
from app.services.director.scenario_council import _mock_audit, _mock_challenge, _mock_council
from app.services.openrouter import _mock_script


def test_mock_council_reduces_cliches() -> None:
    init_db()
    raw = "kahve markası yaz kampanyası — serin içecek enerjisi"
    draft = _mock_script(
        language="tr",
        title="Test",
        duration_seconds=30,
        style="shorts-punchy",
        audience="genç yetişkinler",
        raw_input=raw,
    )
    before = detect_cliches(draft)
    revised = _mock_challenge(draft, language="tr", raw_input=raw)
    final = _mock_audit(revised, language="tr", style="shorts-punchy")
    after = detect_cliches(final)
    assert final.get("scenes"), "scenes missing"
    assert final.get("hook"), "hook missing"
    blob = (final.get("hook") or "") + " " + " ".join(
        str(s.get("narration") or "") for s in final.get("scenes") or []
    ).lower()
    for banned in ("yanlış yapıyorsun", "fikir var", "ritim yok", "dur."):
        assert banned not in blob, f"yasak kalıp: {banned}"
    print("cliches_before", len(before), "cliches_after", len(after))
    print("hook", final.get("hook"))


async def test_full_mock_council() -> None:
    init_db()
    script = await _mock_council(
        language="tr",
        title="Kahve",
        duration_seconds=30,
        style="enerjik",
        audience="25-35",
        raw_input="soğuk kahve yaz lansmanı",
    )
    assert script.get("scenes")
    assert not any(k.startswith("_") and k != "_mock" for k in script)
    # Simüle API yanıtı — iç konsey alanı yok
    public = {k: v for k, v in script.items() if not str(k).startswith("_")}
    dumped = json.dumps(public, ensure_ascii=False)
    assert "AI-A" not in dumped and "AI-B" not in dumped and "tartışma" not in dumped.lower()
    print("ok scenes", len(script["scenes"]), "verdict_fields", list(public.keys())[:6])


if __name__ == "__main__":
    test_mock_council_reduces_cliches()
    asyncio.run(test_full_mock_council())
    print("ALL OK")
