#!/usr/bin/env python3
"""Pre-bake narration audio for each scene via the TTS server (POST /tts).

Run this server-side: the token stays in .env and never reaches the browser.
Output: web/<game>/assets/audio/<slug>.mp3 — the static files the runtime plays
on the public site (the live voice picker remains a local/dev feature).

    python scripts/build_audio.py                       # default voice
    python scripts/build_audio.py --voice en-GB-RyanNeural --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENES = ROOT / "zork1" / "scenes" / "zork1.yaml"


def main():
    ap = argparse.ArgumentParser(description="Pre-bake scene narration via the TTS server.")
    ap.add_argument("--scenes", default=str(DEFAULT_SCENES))
    ap.add_argument("--voice", default="en-US-AriaNeural")
    ap.add_argument("--base", default=os.environ.get("TTS_BASE", "https://tts.akaraduman.synology.me"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    token = os.environ.get("TTS_TOKEN")
    if not token:
        sys.exit("TTS_TOKEN not set in .env")

    doc = yaml.safe_load(open(args.scenes))
    game = doc.get("game", "zork1")
    outdir = ROOT / "web" / game / "assets" / "audio"
    outdir.mkdir(parents=True, exist_ok=True)

    saved = skipped = failed = 0
    for s in doc["scenes"]:
        slug = s["slug"]
        text = " ".join((s.get("scene_description") or "").split())
        out = outdir / f"{slug}.mp3"
        if out.exists() and not args.overwrite:
            skipped += 1
            print(f"  = {slug} (exists)")
            continue
        if not text:
            failed += 1
            print(f"  ! {slug}: no narration text")
            continue
        req = urllib.request.Request(
            args.base.rstrip("/") + "/tts",
            data=json.dumps({"text": text, "voice": args.voice}).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                audio = r.read()
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ! {slug}: {e}")
            continue
        out.write_bytes(audio)
        saved += 1
        print(f"  + {slug}.mp3 ({len(audio) // 1024} KB)")
        time.sleep(0.2)

    print(f"\nDone: {saved} saved, {skipped} skipped, {failed} failed -> {outdir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
