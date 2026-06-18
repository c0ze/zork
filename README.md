# Zork — graphic text adventure (web)

Modernized, web-playable ports of the classic Zork trilogy, enhanced with
AI-generated scene art and pre-rendered narration audio. Target: a fully static
site (GitHub Pages) — no backend, no API keys at runtime.

## Status

- **Sources** (`sources/`, reference only): Zork I/II/III (MIT, 2025) + Colossal Cave (Unlicense).
- **First target:** Zork I "opening" vertical slice — 6 scenes, 4 candidate art styles.
- **Done:** scene/text extraction, style bibles, Gemini batch image generator, static web shell.
- **Next:** choose the art style, wire the Parchment interpreter, extend to the full map.

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
3. **Narration:** the runtime synthesizes each scene's text live via your TTS
   server (`POST /tts {text, voice}`) in the voice the player selects (dropdown
   from `/voices`, English only). Optional pre-baked fallbacks can live at
   `web/assets/zork1/audio/<slug>.<ext>`.
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

`zork1.z3` → Parchment (Bocfel/WASM) renders into `#gameport`/`#windowport` →
`app.js` reads the current room from GlkOte's `.GridWindow` status line → looks it
up in `manifest.json` → swaps the scene image and narrates it (first visit only).
Narration is synthesized live from your TTS server in the player-selected voice
(`/voices`, English only), with pre-baked files as fallback. No browser speech
synthesis.

**Music:** each scene's `region` maps to a 2-track playlist in `manifest.json`
(`web/assets/zork1/music/<section>-{1,2}.mp3`); the two tracks play successively
and loop while you remain in that region. Music and narration each have an on/off
toggle and a volume slider. WAV masters are gitignored; web-optimized MP3s ship.

**TTS config:** copy `web/config.example.js` to `web/config.js` (gitignored) and
set `ttsBase` + `ttsToken`. ⚠️ The token ships to the browser — fine for local or
private use, but for a PUBLIC deploy proxy the TTS server or pre-bake the audio so
the token stays secret.

### Wiring the interpreter (next step)

Add a Parchment web build under `web/vendor/parchment/`, render it into
`#gameport` / `#windowport` pointed at `stories/zork1.z3`, then set
`window.PARCHMENT_READY = true` in `index.html`. `app.js` switches from the
preview buttons to the live status-line reader automatically.

## Licensing

Zork I/II/III source © Infocom/Activision, MIT (2025) — keep the `LICENSE` files
in `sources/`. Colossal Cave is under the Unlicense. "Zork" is an Activision
trademark; this is an educational/fan project, not an official product.
