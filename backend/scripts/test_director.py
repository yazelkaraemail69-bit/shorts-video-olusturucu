from pathlib import Path

from app.config import get_settings
from app.database import init_db
from app.services.director.ai2_visuals import _mock_scene_image
from app.services.director.ai3_editor import run_editor_agent
from app.services.director.critique import build_critique_report
from app.services.elevenlabs import _write_mock_wav
from app.services.openrouter import _mock_script

init_db()
d = Path("data/media/jobs/_director_test")
d.mkdir(parents=True, exist_ok=True)
script = _mock_script(
    language="tr",
    title="Director",
    duration_seconds=10,
    style="shorts-punchy",
    audience="gencler",
    raw_input="kahve shorts",
)
settings = get_settings()
for sc in script["scenes"]:
    idx = int(sc["index"])
    p = d / "scenes" / f"scene_{idx:02d}.jpg"
    _mock_scene_image(sc, p, settings.image_width, settings.image_height)
    sc["image"] = f"scenes/scene_{idx:02d}.jpg"

_write_mock_wav(d / "voice.wav", "test", 10)
edited = run_editor_agent(
    job_dir=d,
    script=script,
    audio_path=d / "voice.wav",
    duration_seconds=10,
)
rep = build_critique_report(script, is_mock=True)
size = (d / edited["video_file"]).stat().st_size
print("video", edited["video_file"], size)
print("critique", rep["verdict"], "scenes", rep["scene_count"])
