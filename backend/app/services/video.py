from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_storyboard_video(
    *,
    job_dir: Path,
    script: dict[str, Any],
    audio_filename: str,
    duration_seconds: int,
) -> tuple[str, str]:
    """
    Shorts (9:16) önizleme: dikey player + kinetik caption + ses senkronu.
    Dönüş: (video_manifest_rel, preview_html_rel)
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes = script.get("scenes") or []
    manifest = {
        "title": script.get("title") or "Shorts",
        "format": script.get("format") or "shorts_9x16",
        "duration_seconds": duration_seconds,
        "audio": audio_filename,
        "music_mood": script.get("music_mood"),
        "cta": script.get("cta"),
        "hook": script.get("hook"),
        "edit_notes": script.get("edit_notes"),
        "scenes": scenes,
        "provider": "shorts-preview",
    }
    (job_dir / "video.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (job_dir / "preview.html").write_text(
        _preview_html(manifest, audio_filename),
        encoding="utf-8",
    )
    return "video.json", "preview.html"


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _preview_html(manifest: dict[str, Any], audio_filename: str) -> str:
    scenes_json = json.dumps(manifest.get("scenes") or [], ensure_ascii=False)
    title = _esc(manifest.get("title") or "Shorts")
    hook = _esc(manifest.get("hook") or "")
    cta = _esc(manifest.get("cta") or "")
    duration = int(manifest.get("duration_seconds") or 30)
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  :root {{
    --bg: #070908;
    --phone: #0c100e;
    --line: rgba(243,239,230,.14);
    --text: #f6f2e9;
    --muted: #9aa39a;
    --accent: #e2a84a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; font-family: "Segoe UI", system-ui, sans-serif;
    color: var(--text); background: radial-gradient(700px 420px at 50% 0%, rgba(61,155,122,.2), transparent 55%), var(--bg);
    display: grid; place-items: center; padding: 1rem;
  }}
  .wrap {{ display: flex; flex-direction: column; align-items: center; gap: .85rem; width: min(100%, 420px); }}
  .phone {{
    width: min(100%, 360px); aspect-ratio: 9/16; border-radius: 28px; overflow: hidden;
    border: 1px solid var(--line); position: relative; background: #101612;
    box-shadow: 0 30px 80px rgba(0,0,0,.45);
  }}
  .stage {{
    position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: flex-end;
    padding: 1.1rem 1rem 4.2rem; transition: background .35s ease;
    background: linear-gradient(180deg, #1b2a22 0%, #0e1411 55%, #0a0d0b 100%);
  }}
  .stage::before {{
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(180deg, transparent 40%, rgba(0,0,0,.55) 100%);
  }}
  .role {{
    position: absolute; top: 1rem; left: 1rem; z-index: 2;
    font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
    color: var(--accent); font-weight: 700; background: rgba(0,0,0,.35);
    padding: .25rem .5rem; border-radius: 999px; backdrop-filter: blur(6px);
  }}
  .cut-tag {{
    position: absolute; top: 1rem; right: 1rem; z-index: 2;
    font-size: .65rem; color: var(--muted); background: rgba(0,0,0,.3);
    padding: .25rem .45rem; border-radius: 8px;
  }}
  .caption {{
    position: relative; z-index: 2; text-align: center;
    font-size: clamp(1.35rem, 4.5vw, 1.85rem); font-weight: 800; line-height: 1.15;
    letter-spacing: -.02em; text-wrap: balance;
    text-shadow: 0 2px 18px rgba(0,0,0,.55);
    animation: pop .28s ease;
  }}
  .visual-line {{
    position: relative; z-index: 2; margin-top: .55rem; text-align: center;
    font-size: .82rem; color: rgba(246,242,233,.78); line-height: 1.35;
  }}
  .progress {{
    position: absolute; left: .7rem; right: .7rem; top: .45rem; height: 3px;
    background: rgba(255,255,255,.15); border-radius: 99px; overflow: hidden; z-index: 3;
  }}
  .progress > i {{
    display: block; height: 100%; width: 0%; background: var(--accent);
    border-radius: inherit;
  }}
  .play-hit {{
    position: absolute; inset: 0; z-index: 4; display: grid; place-items: center;
    background: rgba(0,0,0,.25); cursor: pointer; border: 0; color: var(--text);
  }}
  .play-hit[hidden] {{ display: none; }}
  .play-hit span {{
    width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center;
    background: rgba(226,168,74,.92); color: #111; font-size: 1.4rem; font-weight: 800;
  }}
  audio {{ width: min(100%, 360px); }}
  .meta {{ width: min(100%, 360px); color: var(--muted); font-size: .8rem; text-align: center; line-height: 1.4; }}
  .meta strong {{ color: var(--text); }}
  @keyframes pop {{
    from {{ transform: scale(.92); opacity: .4; }}
    to {{ transform: scale(1); opacity: 1; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="phone" id="phone">
    <div class="progress"><i id="bar"></i></div>
    <div class="stage" id="stage">
      <div class="role" id="role">SHORTS</div>
      <div class="cut-tag" id="cut">—</div>
      <div class="caption" id="caption">{hook or title}</div>
      <div class="visual-line" id="visual">Oynat — dikey Shorts önizleme</div>
    </div>
    <button type="button" class="play-hit" id="playHit" aria-label="Oynat"><span>▶</span></button>
  </div>
  <audio id="audio" controls src="{audio_filename}"></audio>
  <p class="meta"><strong>{title}</strong><br/>9:16 Shorts · {duration}s · CTA: {cta}</p>
</div>
<script>
const scenes = {scenes_json};
const audio = document.getElementById('audio');
const stage = document.getElementById('stage');
const caption = document.getElementById('caption');
const visual = document.getElementById('visual');
const role = document.getElementById('role');
const cut = document.getElementById('cut');
const bar = document.getElementById('bar');
const playHit = document.getElementById('playHit');
const durationHint = {duration};

const palettes = [
  ['#1b2a22', '#0e1411'],
  ['#2a1f14', '#120e0a'],
  ['#14222a', '#0a1014'],
  ['#241828', '#100c12'],
  ['#1a2418', '#0c100c'],
  ['#222018', '#10100c'],
];

function parseStart(timecode) {{
  if (!timecode) return 0;
  const m = String(timecode).match(/(\\d+(?:\\.\\d+)?)/);
  return m ? Number(m[1]) : 0;
}}

function currentScene(t) {{
  if (!scenes.length) return null;
  let chosen = scenes[0];
  for (const s of scenes) {{
    if (t >= parseStart(s.timecode)) chosen = s;
  }}
  return chosen;
}}

let lastIndex = -1;
function paint(s) {{
  if (!s) return;
  const idx = Number(s.index || 1);
  if (idx !== lastIndex) {{
    lastIndex = idx;
    caption.style.animation = 'none';
    caption.offsetHeight;
    caption.style.animation = '';
  }}
  caption.textContent = s.on_screen_text || s.narration || '';
  visual.textContent = s.visual || '';
  role.textContent = (s.role || 'scene').toUpperCase();
  cut.textContent = s.cut || 'cut';
  const p = palettes[(idx - 1) % palettes.length];
  stage.style.background = `linear-gradient(180deg, ${{p[0]}} 0%, ${{p[1]}} 60%, #070908 100%)`;
}}

audio.addEventListener('timeupdate', () => {{
  const dur = audio.duration && isFinite(audio.duration) ? audio.duration : durationHint;
  bar.style.width = Math.min(100, (audio.currentTime / dur) * 100) + '%';
  paint(currentScene(audio.currentTime));
}});

audio.addEventListener('play', () => {{ playHit.hidden = true; }});
audio.addEventListener('pause', () => {{ if (audio.currentTime < 0.15) playHit.hidden = false; }});
audio.addEventListener('ended', () => {{ playHit.hidden = false; bar.style.width = '100%'; }});

playHit.addEventListener('click', async () => {{
  try {{ await audio.play(); }} catch (e) {{}}
}});

if (scenes[0]) paint(scenes[0]);
</script>
</body>
</html>
"""
