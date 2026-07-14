"""Background müzik oluşturucu — FFmpeg ile ambient müzik üretimi / karıştırma."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _generate_silent_audio(out_path: Path, duration: float, sample_rate: int = 44100) -> None:
    """Sessiz referans audio oluştur (arkaplan müzik yoksa)."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _generate_tone(out_path: Path, duration: float, freq: int = 220) -> None:
    """Basit sinüs tonu — ambient drone efekti."""
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
        "-af",
        "volume=0.08,"
        "aeval=val(0)|val(0):channel_layout=stereo",
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _generate_ambient(out_path: Path, duration: float, mood: str = "cinematic") -> None:
    """
    Mood'a göre ambient ses oluştur.
    Mood seçenekleri: cinematic, punchy, calm, energetic, mysterious, uplifting, dark
    """
    ffmpeg = _ffmpeg()

    # Mood → ses parametre eşlemesi
    mood_params = {
        "cinematic": {
            "freq": 110,
            "noise": "pink",
            "volume": 0.06,
            "mod_freq": 0.1,
            "reverb": 0.3,
        },
        "punchy": {
            "freq": 55,
            "noise": "brown",
            "volume": 0.10,
            "mod_freq": 2.0,
            "reverb": 0.1,
        },
        "calm": {
            "freq": 220,
            "noise": "pink",
            "volume": 0.04,
            "mod_freq": 0.05,
            "reverb": 0.4,
        },
        "energetic": {
            "freq": 80,
            "noise": "white",
            "volume": 0.09,
            "mod_freq": 3.0,
            "reverb": 0.15,
        },
        "mysterious": {
            "freq": 65,
            "noise": "brown",
            "volume": 0.07,
            "mod_freq": 0.08,
            "reverb": 0.5,
        },
        "uplifting": {
            "freq": 175,
            "noise": "pink",
            "volume": 0.07,
            "mod_freq": 0.3,
            "reverb": 0.25,
        },
        "dark": {
            "freq": 45,
            "noise": "brown",
            "volume": 0.09,
            "mod_freq": 0.04,
            "reverb": 0.6,
        },
        "fun": {
            "freq": 260,
            "noise": "white",
            "volume": 0.08,
            "mod_freq": 4.0,
            "reverb": 0.1,
        },
    }

    p = mood_params.get(mood.lower(), mood_params["cinematic"])

    # Çok katmanlı ambient: sinüs ton + noise + tremolo + reverb
    filter_chain = (
        f"aevalsrc=sin({p['freq']}*2*PI*t):d={duration}:s=44100:c=2"
        f" [tone];"
        f"anoisesrc=d={duration}:c=pink:a=0.02 [noise];"
        f"[tone][noise]amix=inputs=2:duration=first"
        f",volume={p['volume']}"
        f",tremolo=f={p['mod_freq']}:d=0.6"
        f",aecho=0.8:0.7:{p['reverb']}:0.5"
        f",lowpass=f=400"
    )

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", filter_chain,
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def mix_background_music(
    voiceover_path: Path,
    output_path: Path,
    duration: float,
    mood: str = "cinematic",
    music_volume: float = 0.15,
    voice_volume: float = 1.0,
) -> Path:
    """
    Voiceover + background müzik karıştır.
    
    Args:
        voiceover_path: Ana ses dosyası
        output_path: Çıktı dosyası
        duration: Video süresi (saniye)
        mood: Müzik ruh hali
        music_volume: Müzik ses seviyesi (0-1)
        voice_volume: Voiceover ses seviyesi (0-1)
    
    Returns:
        Karışık ses dosyasının yolu
    """
    ffmpeg = _ffmpeg()
    temp_dir = Path(tempfile.mkdtemp())
    music_path = temp_dir / "ambient.wav"

    try:
        _generate_ambient(music_path, duration, mood)

        # Eğer voiceover yoksa sadece müzik döndür
        if not voiceover_path.exists() or voiceover_path.stat().st_size < 1000:
            music_path.replace(output_path)
            return output_path

        cmd = [
            ffmpeg, "-y",
            "-i", str(voiceover_path),
            "-i", str(music_path),
            "-filter_complex",
            f"[0:a]volume={voice_volume}[v];"
            f"[1:a]volume={music_volume}[m];"
            f"[v][m]amix=inputs=2:duration=first:dropout_transition=2",
            "-c:a", "pcm_s16le",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path

    finally:
        # Temizlik
        if music_path.exists():
            music_path.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def get_available_moods() -> list[dict[str, Any]]:
    """Kullanılabilir müzik ruh hallerini döndür."""
    return [
        {"id": "cinematic", "name": "🎬 Sinematik", "bpm": "60-80", "energy": "orta"},
        {"id": "punchy", "name": "⚡ Enerjik Punchy", "bpm": "100-120", "energy": "yüksek"},
        {"id": "calm", "name": "🧘 Sakin", "bpm": "40-60", "energy": "düşük"},
        {"id": "energetic", "name": "🔥 Yüksek Enerji", "bpm": "120-140", "energy": "çok yüksek"},
        {"id": "mysterious", "name": "🔮 Gizemli", "bpm": "50-70", "energy": "düşük-orta"},
        {"id": "uplifting", "name": "✨ İlham Verici", "bpm": "80-100", "energy": "orta-yüksek"},
        {"id": "dark", "name": "🌑 Karanlık", "bpm": "40-60", "energy": "düşük"},
        {"id": "fun", "name": "🎉 Eğlenceli", "bpm": "110-130", "energy": "yüksek"},
    ]