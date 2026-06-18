#!/usr/bin/env python3
"""Build web/<game>/manifest.json from the scene + style + voice definitions.

Each room display-name (the key the runtime matches against the game buffer) maps
to its slug, narration text, region (music), and one image path per style. The
runtime composes narration audio paths as assets/audio/<voice-key>/<slug>.mp3.
Paths are relative to the game's web folder (web/<game>/).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STYLES_FILE = ROOT / "styles.yaml"
VOICES_FILE = ROOT / "voices.yaml"
DEFAULT_SCENES = ROOT / "zork1" / "scenes" / "zork1.yaml"
SECTIONS = ["above_ground", "underground", "peril", "wonder", "dread"]


def main():
    ap = argparse.ArgumentParser(description="Generate web/<game>/manifest.json from scene data.")
    ap.add_argument("--scenes", default=str(DEFAULT_SCENES), help="scenes YAML file")
    ap.add_argument("--default-style", default="ink_engraving")
    ap.add_argument("--out", help="output path (default web/<game>/manifest.json)")
    args = ap.parse_args()

    styles = list(yaml.safe_load(open(STYLES_FILE))["styles"].keys())
    voices_doc = yaml.safe_load(VOICES_FILE.read_text())
    voices = [{"key": v["key"], "label": v["label"]} for v in voices_doc["voices"]]
    default_voice = voices_doc.get("default", voices[0]["key"])

    doc = yaml.safe_load(open(args.scenes))
    game = doc.get("game", "zork1")
    default_region = doc.get("default_region", "above_ground")

    scenes = {}
    for s in doc["scenes"]:
        slug = s["slug"]
        scenes[s["id"]] = {
            "slug": slug,
            "room": s.get("room"),
            "region": s.get("region", default_region),
            "narration": " ".join((s.get("scene_description") or "").split()),
            "images": {st: f"assets/images/{st}/{slug}.webp" for st in styles},
        }

    music = {sec: [f"assets/music/{sec}-1.mp3", f"assets/music/{sec}-2.mp3"] for sec in SECTIONS}
    start_room = doc.get("start_room") or (doc["scenes"][0]["id"] if doc.get("scenes") else None)
    default_style = args.default_style if args.default_style in styles else styles[0]
    manifest = {
        "game": game,
        "styles": styles,
        "default_style": default_style,
        "voices": voices,
        "default_voice": default_voice,
        "audio_path": "assets/audio/{voice}/{slug}.mp3",
        "default_region": default_region,
        "start_room": start_room,
        "music": music,
        "scenes": scenes,
    }

    out = Path(args.out) if args.out else (ROOT / "web" / game / "manifest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out.relative_to(ROOT)}: {len(scenes)} scenes x {len(styles)} styles x {len(voices)} voices")


if __name__ == "__main__":
    main()
