#!/usr/bin/env python3
"""Pre-bake narration audio for each scene in every curated voice (voices.yaml).

Run server-side: the token stays in .env, never in the browser. Output:
    web/<game>/assets/audio/<voice-key>/<slug>.mp3
so the public site narrates AND switches voices with zero token exposure.

    python scripts/build_audio.py                  # all voices x all scenes
    python scripts/build_audio.py --voice gb-ryan  # just one voice
    python scripts/build_audio.py --scenes zork1/scenes/opening.yaml --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import ssl
import urllib.request
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Verify TLS against certifi's CA bundle so this runs regardless of the local
# Python's certificate setup (a fresh macOS/venv Python often lacks one and
# fails with CERTIFICATE_VERIFY_FAILED against the public TTS host).
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    SSL_CONTEXT = ssl.create_default_context()

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENES = ROOT / "zork1" / "scenes" / "zork1.yaml"
VOICES_FILE = ROOT / "voices.yaml"


def main():
    ap = argparse.ArgumentParser(description="Pre-bake scene narration in the curated voices.")
    ap.add_argument("--scenes", default=str(DEFAULT_SCENES))
    ap.add_argument("--voice", help="only this voice key (default: every voice in voices.yaml)")
    ap.add_argument("--base", default=os.environ.get("TTS_BASE", "https://tts.akaraduman.synology.me"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--only", help="comma-separated slugs to (re)bake (default: all scenes)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    token = os.environ.get("TTS_TOKEN")
    if not token:
        sys.exit("TTS_TOKEN not set in .env")

    voices = yaml.safe_load(VOICES_FILE.read_text())["voices"]
    if args.voice:
        voices = [v for v in voices if v["key"] == args.voice]
        if not voices:
            sys.exit(f"unknown voice key: {args.voice}")

    doc = yaml.safe_load(open(args.scenes))
    game = doc.get("game", "zork1")
    only = {x.strip() for x in args.only.split(",")} if args.only else None
    scenes = [(s["slug"], " ".join((s.get("scene_description") or "").split()))
              for s in doc["scenes"] if not only or s["slug"] in only]

    saved = skipped = failed = 0
    for v in voices:
        outdir = ROOT / "web" / game / "assets" / "audio" / v["key"]
        outdir.mkdir(parents=True, exist_ok=True)
        for slug, text in scenes:
            out = outdir / f"{slug}.mp3"
            if out.exists() and not args.overwrite:
                skipped += 1
                continue
            if not text:
                failed += 1
                continue
            req = urllib.request.Request(
                args.base.rstrip("/") + "/tts",
                data=json.dumps({"text": text, "voice": v["short"]}).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as r:
                    audio = r.read()
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ! {v['key']}/{slug}: {e}")
                continue
            out.write_bytes(audio)
            saved += 1
            time.sleep(0.15)
        print(f"  {v['key']}: done ({v['short']})")
    print(f"\nDone: {saved} saved, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
