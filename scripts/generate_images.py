#!/usr/bin/env python3
"""
Batch-generate scene images for the Zork graphic-text-adventure project.

Reads scene definitions + style bibles, assembles one prompt per (style, scene),
submits them as a SINGLE Gemini Batch job, persists the job id locally so polling
survives restarts, then dissects the results into per-style image folders.

Usage:
    python generate_images.py                 # ALL styles  (6 scenes x 4 styles = 24)
    python generate_images.py ink_engraving   # one style    (6 images)
    python generate_images.py --only west-of-house,behind-house --new --overwrite
                                              # regenerate just those scenes (all styles)
    python generate_images.py --new           # ignore any saved job, submit fresh
    python generate_images.py --poll-interval 30

Requires GEMINI_API_KEY in <repo>/.env (or the environment). Get one at
https://aistudio.google.com/apikey
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import yaml
from dotenv import load_dotenv
from PIL import Image
from google import genai

ROOT = Path(__file__).resolve().parent.parent
STYLES_FILE = ROOT / "styles.yaml"
JOBS_DIR = Path(__file__).resolve().parent / ".batch_jobs"
DEFAULT_SCENES = ROOT / "zork1" / "scenes" / "opening.yaml"

# Nano Banana: batch-eligible, ~$0.0195/image in batch. Alt: "gemini-3-pro-image-preview".
MODEL = "gemini-2.5-flash-image"
TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


def load_yaml(path: Path):
    with open(path) as f:
        return yaml.safe_load(f)


def build_prompt(world: str, style: dict, scene: dict, anchors: dict, global_negative: str = "") -> str:
    """world preamble + style prefix + scene content + anchor descriptions + negatives."""
    chunks = [world.strip(), style["prefix"].strip(), scene["scene_core"].strip()]
    descs = [
        anchors[a]["description"].strip()
        for a in (scene.get("anchors") or [])
        if a in anchors
    ]
    if descs:
        chunks.append("Consistent recurring elements: " + " ".join(descs))
    avoid = ", ".join(p for p in [style.get("negative", "").strip(), (global_negative or "").strip()] if p)
    if avoid:
        chunks.append("Avoid: " + avoid)
    # NOTE: aspect ratio is carried in the prompt (world preamble says "wide 16:9").
    # Nano Banana's aspect-ratio config key has varied across SDK versions, so we keep
    # the request config minimal/portable rather than risk an unknown parameter.
    return "\n\n".join(c for c in chunks if c)


def plan_requests(style_filter, styles, scenes, anchors, world, game, global_negative, only_slugs=None):
    """Build inline requests and a parallel metadata list (same order)."""
    if only_slugs:
        scenes = [s for s in scenes if s["slug"] in only_slugs]
    names = [style_filter] if style_filter else list(styles.keys())
    inline, meta = [], []
    for style_name in names:
        style = styles[style_name]
        for scene in scenes:
            prompt = build_prompt(world, style, scene, anchors, global_negative)
            inline.append(
                {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "config": {"response_modalities": ["TEXT", "IMAGE"]},
                }
            )
            meta.append(
                {
                    "style": style_name,
                    "slug": scene["slug"],
                    "scene_id": scene["id"],
                    "output": f"web/{game}/assets/images/{style_name}/{scene['slug']}.webp",
                }
            )
    return inline, meta


def state_path(run_id: str) -> Path:
    return JOBS_DIR / f"{run_id}.json"


def save_state(run_id: str, data: dict):
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    state_path(run_id).write_text(json.dumps(data, indent=2))


def load_state(run_id: str):
    p = state_path(run_id)
    return json.loads(p.read_text()) if p.exists() else None


def save_images(job, meta, overwrite=False):
    """Dissect inline batch results into target folders. Returns (saved, failed, skipped)."""
    saved = failed = skipped = 0
    dest = getattr(job, "dest", None)
    responses = list(getattr(dest, "inlined_responses", None) or [])
    if len(responses) != len(meta):
        print(f"  ! warning: {len(responses)} responses for {len(meta)} requests")
    for i, item in enumerate(responses):
        if i >= len(meta):
            break
        m = meta[i]
        out = ROOT / m["output"]
        if out.exists() and not overwrite:
            skipped += 1
            continue
        resp = getattr(item, "response", None)
        if resp is None or not getattr(resp, "candidates", None):
            failed += 1
            print(f"  ! {m['style']}/{m['slug']}: {getattr(item, 'error', 'no response')}")
            continue
        data = None
        for part in resp.candidates[0].content.parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and inline_data.data:
                data = inline_data.data
                break
        if not data:
            failed += 1
            print(f"  ! {m['style']}/{m['slug']}: no image in response")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(BytesIO(data))
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        img.save(out, "WEBP", quality=90, method=6)
        saved += 1
        print(f"  + {m['style']}/{m['slug']}  ->  {m['output']}")
    return saved, failed, skipped


def main():
    ap = argparse.ArgumentParser(description="Batch-generate Zork scene images via Gemini.")
    ap.add_argument("style", nargs="?", help="style key (e.g. ink_engraving). Omit for ALL styles.")
    ap.add_argument("--scenes", default=str(DEFAULT_SCENES), help="scenes YAML file")
    ap.add_argument("--only", help="comma-separated scene slugs to (re)generate, e.g. west-of-house,behind-house")
    ap.add_argument("--new", action="store_true", help="ignore any saved job and submit fresh")
    ap.add_argument("--overwrite", action="store_true", help="overwrite images that already exist")
    ap.add_argument("--poll-interval", type=int, default=60, help="seconds between status checks")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (see scripts/.env.example).")
    client = genai.Client(api_key=api_key)

    styles_doc = load_yaml(STYLES_FILE)
    world = styles_doc["world_preamble"]
    styles = styles_doc["styles"]
    global_negative = styles_doc.get("global_negative", "")
    scenes_doc = load_yaml(Path(args.scenes))
    scenes = scenes_doc["scenes"]
    game = scenes_doc.get("game", "zork1")
    anchors = (load_yaml(ROOT / game / "anchors.yaml") or {}).get("anchors", {})

    if args.style and args.style not in styles:
        sys.exit(f"Unknown style '{args.style}'. Choices: {', '.join(styles)}")
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    if only:
        unknown = only - {s["slug"] for s in scenes}
        if unknown:
            sys.exit(f"--only: unknown slug(s): {', '.join(sorted(unknown))}")

    run_id = f"{game}-{scenes_doc.get('slice', 'scenes')}-{args.style or 'all'}"
    if only:
        run_id += "-only-" + "_".join(sorted(only))
    inline, meta = plan_requests(args.style, styles, scenes, anchors, world, game, global_negative, only)

    state = None if args.new else load_state(run_id)

    if state and state.get("job_name") and not state.get("completed_at"):
        job_name = state["job_name"]
        meta = state["meta"]  # preserve original submission order
        print(f"Resuming saved job {job_name}  [{run_id}]")
    else:
        print(f"Submitting batch: {len(inline)} image request(s)  [{run_id}]  model={MODEL}")
        try:
            job = client.batches.create(
                model=MODEL,
                src=inline,
                config={"display_name": f"zork-{run_id}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"},
            )
        except Exception as e:  # noqa: BLE001 - surface API errors plainly
            sys.exit(f"Batch submission failed: {e}")
        job_name = job.name
        save_state(
            run_id,
            {
                "job_name": job_name,
                "model": MODEL,
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta": meta,
            },
        )
        print(f"Created {job_name}\nState saved to {state_path(run_id).relative_to(ROOT)} "
              f"(stop any time; re-run to resume polling).")

    start = time.time()
    while True:
        job = client.batches.get(name=job_name)
        st = job.state.name
        print(f"[{(time.time() - start) / 60:5.1f} min] {st}")
        if st in TERMINAL_STATES:
            break
        time.sleep(args.poll_interval)

    if job.state.name != "JOB_STATE_SUCCEEDED":
        sys.exit(
            f"Job ended in state {job.state.name}. Re-run to retry polling "
            f"(saved as {state_path(run_id).name}); use --new to resubmit."
        )

    print("Job succeeded - writing images...")
    saved, failed, skipped = save_images(job, meta, args.overwrite)
    print(f"\nDone: {saved} saved, {skipped} already existed, {failed} failed.")
    if skipped and not args.overwrite:
        print("(Pass --overwrite to replace existing images.)")
    if failed == 0:
        st_data = load_state(run_id) or {}
        st_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_state(run_id, st_data)
    else:
        print("Some requests failed. Use --new to resubmit a fresh job for this set.")


if __name__ == "__main__":
    main()
