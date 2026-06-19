# Zork — graphic text adventure (web)

Modernized, web-playable ports of the classic Zork trilogy, enhanced with
AI-generated scene art and pre-rendered narration audio. Target: a fully static
site (GitHub Pages) — no backend, no API keys at runtime.

## Status

- **Live at [zork.coze.org](https://zork.coze.org):** **Zork I** and **Zork II** — both fully
  playable, illustrated (4 art styles), narrated (8 voices), and scored with regional music.
- **Planned:** Zork III.
- **Sources** (`sources/`, reference only): Zork I/II/III (MIT, 2025) + Colossal Cave (Unlicense).
- Per game: full-map scene/text extraction → Gemini batch art → pre-baked TTS narration →
  regional music → a static Parchment web shell with per-turn autosave / restart / death-reset.

## Layout

```
sources/                       cloned game sources (reference only)
styles.yaml                    4 art-style bibles + shared world preamble
zork1/
  anchors.yaml                 recurring entities for visual consistency
  scenes/opening.yaml          6 opening-slice scene cards
scripts/
  generate_images.py           Gemini batch image generator
  build_manifest.py            scenes -> web/manifest.json
  requirements.txt  .env.example
web/                           <-- the publishable static site
  index.html  styles.css  app.js
  manifest.json                room -> image (per style) + audio   (generated)
  stories/zork1.z3             compiled story file for the interpreter
  assets/zork1/images/<style>/<slug>.webp   generated art
  assets/zork1/audio/<slug>.<ext>           narration audio (your TTS server)
  vendor/parchment/            interpreter assets (added during wiring)
```

## Pipeline

1. **Scene cards** (`zork1/scenes/opening.yaml`): `id` = the room name shown in the
   Z-machine status line; `scene_description` = verbatim room text (for your TTS);
   `scene_core` = style-agnostic image content; `anchors` = recurring entities.
2. **Images:** `python scripts/generate_images.py [style]` assembles
   `world_preamble + style + scene_core + anchors + negatives`, submits a Gemini
   batch (`gemini-2.5-flash-image`), polls (resumable), and writes
   `web/assets/zork1/images/<style>/<slug>.webp`. Regenerate just-changed scenes
   with e.g. `--only west-of-house,behind-house --new --overwrite`.
3. **Narration:** `python scripts/build_audio.py` pre-bakes every scene in each
   curated voice (`voices.yaml`) via your TTS server (server-side; token in `.env`)
   to `web/<game>/assets/audio/<voice>/<slug>.mp3`. No token reaches the browser.
4. **Manifest:** `python scripts/build_manifest.py` regenerates `web/manifest.json`
   (includes the narration text the runtime sends to the TTS server).

## Run the site

```bash
python3 -m http.server -d web 8000      # serve web/ as the site root
```

Open `http://localhost:8000`. Until the interpreter is wired the page runs in
**preview mode** — room buttons let you jump between scenes to check art + audio.
Use the Style selector (or `?style=retro_pixel`) to compare looks.

## Runtime — how scene sync works

`zork1.z3` runs in a same-origin iframe (`play.html`) via Parchment (Bocfel/WASM).
`app.js` reads the current room by matching the game buffer against known scene
names → looks it up in `manifest.json` → swaps the scene image, region music, and
narration (first visit). Narration is pre-baked per voice (static MP3s under
`assets/audio/<voice>/`); the Voice picker switches voice and re-reads the room —
no browser token.

**Music:** each scene's `region` maps to a 2-track playlist in `manifest.json`
(`web/assets/zork1/music/<section>-{1,2}.mp3`); the two tracks play successively
and loop while you remain in that region. Music and narration each have an on/off
toggle and a volume slider. WAV masters are gitignored; web-optimized MP3s ship.

**Voices:** the 8 curated narration voices are defined in `voices.yaml`. Re-bake any
with `python scripts/build_audio.py --voice <key> --overwrite`.

### Wiring the interpreter (next step)

Add a Parchment web build under `web/vendor/parchment/`, render it into
`#gameport` / `#windowport` pointed at `stories/zork1.z3`, then set
`window.PARCHMENT_READY = true` in `index.html`. `app.js` switches from the
preview buttons to the live status-line reader automatically.

## Licensing

Zork I/II/III source © Infocom/Activision, MIT (2025) — keep the `LICENSE` files
in `sources/`. Colossal Cave is under the Unlicense. "Zork" is an Activision
trademark; this is an educational/fan project, not an official product.
