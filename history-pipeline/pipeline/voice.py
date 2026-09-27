"""ElevenLabs narration, one audio file per scene."""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from .common import log, media_duration

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"


def narrate(cfg: dict, script: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    key = os.environ["ELEVENLABS_API_KEY"]
    scenes = script["scenes"]
    for i, scene in enumerate(scenes):
        path = out_dir / f"scene_{i:03d}.mp3"
        if not path.exists():
            body = {
                "text": scene["narration"],
                "model_id": cfg["elevenlabs_model"],
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15},
                # Continuity hints keep intonation natural across scene boundaries.
                "previous_text": scenes[i - 1]["narration"] if i else None,
                "next_text": scenes[i + 1]["narration"] if i + 1 < len(scenes) else None,
            }
            for attempt in range(5):
                r = requests.post(API.format(voice=cfg["elevenlabs_voice_id"]),
                                  params={"output_format": "mp3_44100_128"},
                                  headers={"xi-api-key": key, "Content-Type": "application/json"},
                                  json=body, timeout=180)
                if r.status_code == 200:
                    path.write_bytes(r.content)
                    break
                log(f"ElevenLabs error {r.status_code}: {r.text[:200]}")
                if r.status_code in (401, 402, 403):
                    raise RuntimeError("ElevenLabs rejected the request: check API key and credits")
                time.sleep(15 * (attempt + 1))
            else:
                raise RuntimeError("ElevenLabs failed repeatedly")
        scene["audio"] = str(path)
        # 0.45s breathing gap after each scene
        scene["duration"] = round(media_duration(path) + 0.45, 3)
    total = sum(s["duration"] for s in scenes)
    log(f"Narration: {total/60:.1f} minutes")
    script["narration_seconds"] = total
