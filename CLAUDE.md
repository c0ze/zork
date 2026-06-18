# Zork — graphic text adventure (agent guide)

Web-playable Zork ports (zork1 is live; zork2/zork3 planned). The Z-machine story
runs in-browser via **Parchment**, dressed with AI scene art (4 styles), pre-baked
**TTS narration** (8 voices), and regional music. Fully static; deployed to GitHub
Pages (**zork.coze.org**) on every push to `main`. Project backstory: `README.md`.

## Layout
- `styles.yaml` — the 4 art-style "bibles" (shared across games) + world preamble + global negative.
- `voices.yaml` — the 8 baked narration voices (`key`, `short`, `label`).
- `zork<N>/scenes/<game>.yaml` — extracted scenes. Per scene: `slug`, `region`,
  `scene_description` (**TTS source**), `scene_core` (**image-prompt source**), `anchors`.
- `zork<N>/anchors.yaml` — recurring character/object/location descriptions injected into prompts.
- `scripts/` — `extract_scenes.py`, `generate_images.py`, `build_audio.py`, `build_manifest.py`, `check_scenes.py`.
- `web/<game>/` — the deployed site: `index.html` (shell + controls), `app.js` (scene
  controller), `play.html` (Parchment iframe), `manifest.json`, `assets/{images/<style>,audio/<voice>}/<slug>.{webp,mp3}`.

## Running the scripts
Use the venv at `~/.venvs/zork` (`~/.venvs/zork/bin/pip install -r scripts/requirements.txt`).
Secrets live in `.env` (gitignored, **never commit**): `GEMINI_API_KEY`, `TTS_TOKEN`.

Pipeline per game: `extract_scenes.py` (parse ZIL in `sources/<game>/`) → `generate_images.py`
→ `build_audio.py` → `build_manifest.py` → **`check_scenes.py`** → commit + tag + push.

## Handling image / voice inconsistencies — READ THIS

Two failure classes have bitten this project. Handle them deliberately.

### 1. Image mis-mapping (the "scramble")
**Symptom:** a room shows the wrong scene and/or wrong art style (e.g. the "ink engraving"
option renders pixel art; "Studio" shows a treasure vault).
**Cause:** the Gemini **Batch API returns `inlined_responses` out of order and drops
image-less entries.** Mapping results to requests by list position (`responses[i] → meta[i]`)
silently mis-files every image after the first gap.
**Fix (already in `generate_images.py` — do not regress):** each request carries
`{style, slug}` **metadata**; `save_images` routes every result by that metadata, never by
position, and reports image-less requests as `missing`. **Never go back to index-based mapping.**
**After any (re)generation:**
- Confirm the run reports `0 failed / 0 missing`; retry stragglers with `--only <slugs> --overwrite`.
- **Eyeball a few `.webp` per style folder** — `ink_engraving/` must be ink line-art,
  `retro_pixel/` chunky pixels, etc. (the mapping is proven, but verify visually, especially
  any room a user flags). Style correctness can't be auto-checked.
- Run `check_scenes.py` (missing/tiny files).
- **Cache-bust:** bump `IMG_VER` in `app.js` *and* `app.js?v=` in `index.html`, or re-rendered
  images are served stale at the same path.

### 2. TTS / narration inconsistencies
**Symptom:** narration reads differently from the room text (e.g. a trailing "…you can see."
stub), or a voice is silent.
**Mapping is safe here** — `build_audio.py` is a per-`(voice, slug)` loop writing straight to
`<voice>/<slug>.mp3` from that scene's `scene_description`; it can't scramble like the image batch.
So inconsistencies are in the **source text**, not the mapping:
- `scene_description` is extracted from ZIL room text. A dynamic object-list
  ("…you can see: <runtime list>") can leave a **dangling stub** once the list is stripped.
  `extract_scenes.py`'s `clean()` removes these; after extraction run `check_scenes.py` to confirm none remain.
- Narration is the **static** room text by design — it won't include dynamic objects
  (the jewelled egg in Up a Tree, etc.). That's expected, not a bug.
- The hand-authored opening rooms have `scene_description` ≠ `scene_core` on purpose
  (polished narration vs image prompt) — not an issue.
- **TLS:** `build_audio.py` verifies against `certifi`; a fresh macOS/venv Python otherwise
  fails `CERTIFICATE_VERIFY_FAILED` against the TTS host.
- Re-bake targeted scenes with `build_audio.py --only <slugs> --overwrite`.
- **Cache-bust:** bump `AUDIO_VER` in `app.js` (and `app.js?v=`) after re-baking.

## Verify-before-ship checklist
1. `~/.venvs/zork/bin/python scripts/check_scenes.py --scenes zork<N>/scenes/<game>.yaml` is clean.
2. Spot-check a few images per style by eye (style ≠ scramble), incl. any user-flagged room.
3. Bump `IMG_VER` / `AUDIO_VER` and `app.js?v=` / `play.html?v=` whenever assets or front-end change.
4. Commit → `git tag vX.Y.Z` → push `main` (→ Pages). Cut the release with `gh release create`.

## Conventions
- End commit messages with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Never commit `.env`, `sources/`, or a venv. `scripts/.batch_jobs/` is gitignored.
- Continuity (zork1): Parchment `do_vm_autosave: true` resumes per-turn; `visited` is persisted
  (`zork-visited`); Restart wipes `dialog_*` + progress and reloads; death is detected from the
  buffer banner and resets `visited` so the start scene re-renders/re-narrates.
- Releases: v1.0 launch · v1.0.1 interpreter/theme · v1.0.2 image-scramble fix ·
  v1.1.0 autosave/restart/death-reset · v1.1.1 narration fix.
