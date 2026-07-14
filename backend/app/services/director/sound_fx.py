"""Ses efektleri — geçiş/vurgu efektleri oluşturma ve karıştırma."""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def generate_whoosh(out_path: Path, duration: float = 0.3) -> Path:
    """Rüzgar sesi efekti — geçişler için."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i",
        f"aevalsrc=sin(16000*(1-exp(-t*10))*t):d={duration}:s=44100:c=1,"
        f"volume=0.4,"
        f"aflt=freq=500:width=2000",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def generate_impact(out_path: Path, duration: float = 0.15) -> Path:
    """Darbe efekti — vurgu anları için."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i",
        f"aevalsrc=sin(200*t)*(1-t/{duration}):d={duration}:s=44100:c=1,"
        f"volume=0.6,"
        f"aflt=freq=100:width=3000",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def generate_stinger(out_path: Path, duration: float = 0.5) -> Path:
    """Stinger efekti — bölüm sonu / CTA vurgusu."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i",
        f"aevalsrc=sin(400*(1-exp(-t*5))*t)+sin(800*(1-exp(-t*8))*t):"
        f"d={duration}:s=44100:c=1,"
        f"volume=0.5,"
        f"aflt=freq=200:width=5000",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def generate_swipe(out_path: Path, duration: float = 0.25) -> Path:
    """Kaydırma efekti — hızlı geçişler için."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i",
        f"aevalsrc=sin(3000*t)*sin(2*PI*{1/duration}*t):"
        f"d={duration}:s=44100:c=1,"
        f"volume=0.3",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def generate_glitch_effect(out_path: Path, duration: float = 0.2) -> Path:
    """Glitch efekti — dijital bozulma sesi."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i",
        f"anoisesrc=d={duration}:c=white:a=0.8,"
        f"lowpass=f=3000,highpass=f=500,"
        f"volume=0.35",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


SFX_GENERATORS = {
    "whoosh": generate_whoosh,
    "impact": generate_impact,
    "stinger": generate_stinger,
    "swipe": generate_swipe,
    "glitch": generate_glitch_effect,
}


def apply_sound_effect(
    audio_path: Path,
    effect_type: str,
    output_path: Path,
    insert_at: float = 0.0,
    effect_volume: float = 0.4,
) -> Path:
    """
    Ses dosyasına efekt ekle (belirtilen saniyede).
    
    Args:
        audio_path: Kaynak ses dosyası
        effect_type: Efekt türü (whoosh, impact, stinger, swipe, glitch)
        output_path: Çıktı dosyası
        insert_at: Efektin ekleneceği saniye
        effect_volume: Efekt ses seviyesi (0-1)
    
    Returns:
        Efekt eklenmiş ses dosyası yolu
    """
    import tempfile
    
    ffmpeg = _ffmpeg()
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Efekti üret
        generator = SFX_GENERATORS.get(effect_type)
        if not generator:
            raise ValueError(f"Bilinmeyen efekt: {effect_type}")

        effect_path = temp_dir / f"{effect_type}.wav"
        generator(effect_path)

        # Efekti ana sese belirtilen saniyede ekle
        cmd = [
            ffmpeg, "-y",
            "-i", str(audio_path),
            "-i", str(effect_path),
            "-filter_complex",
            f"[1:a]volume={effect_volume}[efx];"
            f"[0:a][efx]adelay={int(insert_at * 1000)}|{int(insert_at * 1000)}[efx_delayed];"
            f"[0:a][efx_delayed]amix=inputs=2:duration=first:dropout_transition=1",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path

    finally:
        # Temizlik
        for f in temp_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def apply_transition_sounds(
    audio_path: Path,
    output_path: Path,
    scene_times: list[float],
    effect_type: str = "whoosh",
) -> Path:
    """
    Tüm sahne geçişlerine ses efekti ekle.
    
    Args:
        audio_path: Kaynak ses dosyası
        output_path: Çıktı dosyası
        scene_times: Her sahnedeki geçiş zamanları (saniye)
        effect_type: Efekt türü
    
    Returns:
        Efektler eklenmiş ses dosyası
    """
    import tempfile

    ffmpeg = _ffmpeg()
    temp_dir = Path(tempfile.mkdtemp())

    try:
        current_input = audio_path
        for i, t in enumerate(scene_times):
            if t <= 0:
                continue

            temp_out = temp_dir / f"step_{i}.wav"
            current_input = apply_sound_effect(
                current_input, effect_type, temp_out,
                insert_at=t, effect_volume=0.25,
            )

        # Final çıktı
        if current_input != audio_path:
            import shutil
            shutil.copy2(str(current_input), str(output_path))
        else:
            import shutil
            shutil.copy2(str(audio_path), str(output_path))

        return output_path

    finally:
        for f in temp_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def list_sound_effects() -> list[dict]:
    """Kullanılabilir ses efektlerini döndür."""
    return [
        {"id": "whoosh", "name": "🌬️ Whoosh (Rüzgar)", "duration": 0.3, "usage": "Sahne geçişleri"},
        {"id": "impact", "name": "💥 Impact (Darbe)", "duration": 0.15, "usage": "Vurgu anları, hook"},
        {"id": "stinger", "name": "🔔 Stinger (Vurgu)", "duration": 0.5, "usage": "Bölüm sonu, CTA"},
        {"id": "swipe", "name": "👆 Swipe (Kaydırma)", "duration": 0.25, "usage": "Hızlı geçişler"},
        {"id": "glitch", "name": "📺 Glitch (Bozulma)", "duration": 0.2, "usage": "Dijital efekt, twist"},
    ]