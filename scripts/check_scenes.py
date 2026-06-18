#!/usr/bin/env python3
"""Consistency audit for a game's scene assets. Run after extract / generate /
bake, before shipping. Exits non-zero if anything looks off.

Checks:
  1. scene_description artifacts (dangling runtime-list stubs, empty/short,
     trailing colon) — the kind of thing the TTS then narrates as nonsense.
  2. scene image coverage: every style x slug present and not suspiciously tiny.
  3. narration coverage: every voice x slug present.

NOTE: this cannot tell whether an image is in the *right art style* (that needs a
human/visual spot-check) — it only catches missing/broken files and bad text.

    python scripts/check_scenes.py                          # zork1 (default)
    python scripts/check_scenes.py --scenes zork2/scenes/zork2.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def desc_problems(d: str) -> list[str]:
    d = (d or "").strip()
    p = []
    if not d:
        p.append("EMPTY")
        return p
    if len(d) < 40:
        p.append(f"short({len(d)})")
    if re.search(r"\byou can see\s*\.\s*$", d, re.I):
        p.append('dangling "you can see."')
    if d.endswith(":"):
        p.append("ends-with-colon (runtime list intro)")
    if re.search(r"\b(is|are|the|a|with|and|of)\s*\.\s*$", d):
        p.append("dangling stub (sentence cut off)")
    return p


def main():
    ap = argparse.ArgumentParser(description="Audit scene text + image/audio coverage.")
    ap.add_argument("--scenes", default=str(ROOT / "zork1" / "scenes" / "zork1.yaml"))
    ap.add_argument("--min-image-bytes", type=int, default=5000)
    args = ap.parse_args()

    doc = yaml.safe_load(open(args.scenes))
    game = doc.get("game", "zork1")
    scenes = doc["scenes"]
    styles = list(yaml.safe_load(open(ROOT / "styles.yaml"))["styles"].keys())
    voices = [v["key"] for v in yaml.safe_load(open(ROOT / "voices.yaml"))["voices"]]
    img = ROOT / "web" / game / "assets" / "images"
    aud = ROOT / "web" / game / "assets" / "audio"

    print(f"{game}: {len(scenes)} scenes | {len(styles)} styles | {len(voices)} voices")

    desc = [(s["slug"], p) for s in scenes if (p := desc_problems(s.get("scene_description")))]
    img_missing = [f"{st}/{s['slug']}" for st in styles for s in scenes
                   if not (img / st / f"{s['slug']}.webp").exists()]
    img_tiny = [f"{st}/{s['slug']}" for st in styles for s in scenes
                if (f := img / st / f"{s['slug']}.webp").exists() and f.stat().st_size < args.min_image_bytes]
    aud_missing = [f"{v}/{s['slug']}" for v in voices for s in scenes
                   if not (aud / v / f"{s['slug']}.mp3").exists()]

    def section(title, items, limit=20):
        print(f"\n{title}: {len(items)}")
        for i in items[:limit]:
            print("  -", i)
        if len(items) > limit:
            print(f"  ... +{len(items) - limit} more")

    print(f"\nDESCRIPTION ARTIFACTS: {len(desc)}")
    for slug, p in desc:
        print(f"  - {slug}: {', '.join(p)}")
    section(f"MISSING IMAGES (of {len(styles) * len(scenes)})", img_missing)
    section(f"TINY IMAGES <{args.min_image_bytes}b", img_tiny)
    section(f"MISSING AUDIO (of {len(voices) * len(scenes)})", aud_missing)

    bad = bool(desc or img_missing or img_tiny or aud_missing)
    print("\nRESULT:", "ISSUES FOUND — fix before shipping" if bad else "all consistent")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
