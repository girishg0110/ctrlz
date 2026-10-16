"""Generates the narration from video/script.md with ElevenLabs, one clip per scene.

Writes video/public/audio/scene-N.mp3 and video/src/narration.json (durations and
word timings), which the Remotion composition reads to place every scene.

Usage: uv run python video/tools/narrate.py [scene numbers to regenerate...]
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

VOICE_ID = "cjVigY5qzO86Huf0OWal"  # Eric
MODEL = os.environ.get("ELEVEN_MODEL", "eleven_multilingual_v2")
SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True, "speed": 1.0}
AUDIO = ROOT / "video" / "public" / "audio"
# Spoken spellings for names TTS gets wrong; captions keep the written form.
SAY = {"Ctrl+Z": "Control Z", "Arize": "Arise"}
OUT_JSON = ROOT / "video" / "src" / "narration.json"


def scenes() -> list[dict]:
    text = (ROOT / "video" / "script.md").read_text()
    out = []
    for m in re.finditer(r"^### (\d+)\. (.+?) \(.*?\)\n(.*?)(?=^### |\n---\n)", text, re.S | re.M):
        lines = [l[2:].strip() for l in m.group(3).splitlines() if l.startswith("> ")]
        out.append({"n": int(m.group(1)), "title": m.group(2), "text": " ".join(lines).strip()})
    return out


def words(alignment: dict) -> list[dict]:
    chars, starts, ends = alignment["characters"], alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    result, cur, t0 = [], "", None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                result.append({"w": cur, "s": round(t0, 3), "e": round(prev_e, 3)})
            cur, t0 = "", None
            continue
        if t0 is None:
            t0 = s
        cur += c
        prev_e = e
    if cur:
        result.append({"w": cur, "s": round(t0, 3), "e": round(prev_e, 3)})
    return result


def spoken(text: str) -> str:
    for k, v in SAY.items():
        text = text.replace(k, v)
    return text


def written(ws: list[dict]) -> list[dict]:
    """Map spoken spellings back so captions show 'Ctrl+Z', not 'Control Z'."""
    out, i = [], 0
    while i < len(ws):
        for k, v in SAY.items():
            parts = v.split()
            seg = [w["w"] for w in ws[i:i + len(parts)]]
            if len(seg) == len(parts) and [x.strip(".,:;!?") for x in seg] == parts:
                tail = seg[-1][len(parts[-1]):]
                out.append({"w": k + tail, "s": ws[i]["s"], "e": ws[i + len(parts) - 1]["e"]})
                i += len(parts)
                break
        else:
            out.append(ws[i])
            i += 1
    return out


def tts(text: str, prev: str, nxt: str) -> dict:
    text, prev, nxt = spoken(text), spoken(prev), spoken(nxt)
    body = json.dumps({
        "text": text, "model_id": MODEL, "voice_settings": SETTINGS,
        "previous_text": prev or None, "next_text": nxt or None,
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return round(float(out.stdout.strip()), 3)


def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    only = {int(a) for a in sys.argv[1:]}
    sc = scenes()
    existing = {s["n"]: s for s in json.loads(OUT_JSON.read_text())["scenes"]} if OUT_JSON.exists() else {}
    result = []
    for i, s in enumerate(sc):
        path = AUDIO / f"scene-{s['n']}.mp3"
        if only and s["n"] not in only and s["n"] in existing and existing[s["n"]]["text"] == s["text"]:
            result.append(existing[s["n"]])
            continue
        data = tts(s["text"], sc[i - 1]["text"] if i else "", sc[i + 1]["text"] if i + 1 < len(sc) else "")
        path.write_bytes(base64.b64decode(data["audio_base64"]))
        entry = {**s, "audio": f"audio/scene-{s['n']}.mp3", "duration": duration(path),
                 "words": written(words(data["alignment"]))}
        result.append(entry)
        print(f"scene {s['n']:2d}  {entry['duration']:5.2f}s  {s['text'][:70]}")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"voice": "Eric", "model": MODEL, "scenes": result}, indent=1))
    print(f"total speech {sum(s['duration'] for s in result):.1f}s")


if __name__ == "__main__":
    main()
