'use strict';

/* Scene controller. The game runs in a same-origin iframe (play.html / Parchment);
   we read the room from the buffer (a line matching a known scene key), then swap
   the scene image, region music, and narration.
   - Narration: pre-baked per-voice MP3s (assets/audio/<voice>/<slug>.mp3). Switching
     voice re-reads the current room. No browser token, fully static.
   - Music: per-region playlist of 2 tracks played successively, looping.
   - Theme: dark/light, applied to this page and synced into the iframe. */

const qs = (s) => document.querySelector(s);

const STATE = {
  manifest: null, style: null, voice: null, theme: 'dark',
  narrationOn: true, ttsVol: 1, started: false,
  visited: new Set(), current: null,
};

const Music = {
  el: null, section: null, list: [], idx: 0, on: true,
  init() {
    this.el = qs('#music');
    this.el.addEventListener('ended', () => this._advance());
  },
  setRegion(region) {
    if (!region || region === this.section) return;
    const list = (STATE.manifest.music || {})[region];
    if (!list || !list.length) return;
    this.section = region; this.list = list; this.idx = 0; this._load();
  },
  _load() { this.el.src = this.list[this.idx]; if (this.on && STATE.started) this.el.play().catch(() => {}); },
  _advance() { if (this.list.length) { this.idx = (this.idx + 1) % this.list.length; this._load(); } },
  kick() { if (this.on && this.list.length) this.el.play().catch(() => {}); },
  setOn(on) { this.on = on; if (!on) this.el.pause(); else if (this.list.length) this.el.play().catch(() => {}); },
  setVol(v) { this.el.volume = v; },
};

async function init() {
  try { STATE.manifest = await (await fetch('manifest.json?v=' + Date.now())).json(); }
  catch (e) { return showFatal('Could not load manifest.json (' + e + ')'); }

  const params = new URLSearchParams(location.search);
  STATE.style = params.get('style') || STATE.manifest.default_style || STATE.manifest.styles[0];
  STATE.theme = localStorage.getItem('zork-theme') || 'dark';
  applyTheme(STATE.theme);

  buildStyleSelect();
  buildVoiceSelect();
  buildThemeSelect();
  Music.init();
  wireAudioControls();
  wireStart();

  const source = new IframeRoomSource(qs('#game-frame'), Object.keys(STATE.manifest.scenes), STATE.manifest.start_room);
  source.onRoom(handleRoom);
  source.start();

  setupInterpreterNudge();
}

function handleRoom(name) {
  name = (name || '').trim();
  if (!name || name === STATE.current) return;
  STATE.current = name;
  qs('#scene-caption').textContent = name;

  const scene = STATE.manifest.scenes[name];
  swapImage(name, scene);
  Music.setRegion((scene && scene.region) || STATE.manifest.default_region);
  if (STATE.started) maybeNarrate(name, scene);
}

/* ---------- image ---------- */
function swapImage(name, scene) {
  const img = qs('#scene-img');
  const src = scene && scene.images && scene.images[STATE.style];
  if (!src) return showPlaceholder(name, 'no scene mapped');
  img.onerror = () => showPlaceholder(name, 'image pending');
  img.onload = () => { img.hidden = false; qs('#scene-placeholder').hidden = true; };
  img.src = src + '?s=' + encodeURIComponent(STATE.style);
}

function showPlaceholder(name, note) {
  qs('#scene-img').hidden = true;
  const ph = qs('#scene-placeholder');
  ph.hidden = false;
  ph.textContent = name + ' — ' + note;
}

/* ---------- narration (pre-baked, per voice) ---------- */
function audioSrc(slug) {
  const tpl = STATE.manifest.audio_path || 'assets/audio/{voice}/{slug}.mp3';
  return tpl.replace('{voice}', STATE.voice).replace('{slug}', slug);
}

function maybeNarrate(name, scene) {
  if (scene && !STATE.visited.has(name)) {
    STATE.visited.add(name);
    playNarration(scene);
  }
}

function playNarration(scene) {
  if (!STATE.narrationOn || !scene || !scene.slug) return;
  const a = qs('#narration');
  a.volume = STATE.ttsVol;
  a.src = audioSrc(scene.slug);
  a.play().catch(() => { /* file may not be baked yet, or autoplay gated; harmless */ });
}

function narrateCurrent() {
  if (STATE.current) playNarration(STATE.manifest.scenes[STATE.current]);
}

/* ---------- theme ---------- */
function applyTheme(t) {
  STATE.theme = t;
  document.documentElement.dataset.theme = t;
  localStorage.setItem('zork-theme', t);
  applyThemeToFrame();
}
function applyThemeToFrame() {
  try { qs('#game-frame').contentDocument.documentElement.dataset.theme = STATE.theme; } catch (e) {}
}

/* ---------- controls ---------- */
function buildStyleSelect() {
  const sel = qs('#style-select');
  STATE.manifest.styles.forEach((s) => {
    const o = document.createElement('option');
    o.value = s; o.textContent = s.replace(/_/g, ' ');
    if (s === STATE.style) o.selected = true;
    sel.appendChild(o);
  });
  sel.addEventListener('change', () => {
    STATE.style = sel.value;
    const u = new URL(location); u.searchParams.set('style', STATE.style); history.replaceState(null, '', u);
    if (STATE.current) swapImage(STATE.current, STATE.manifest.scenes[STATE.current]);
  });
}

function buildVoiceSelect() {
  const control = qs('#voice-control');
  const sel = qs('#voice-select');
  const voices = STATE.manifest.voices || [];
  if (!voices.length) { control.hidden = true; return; }
  const saved = localStorage.getItem('zork-voice');
  STATE.voice = (saved && voices.some((v) => v.key === saved)) ? saved
    : (STATE.manifest.default_voice || voices[0].key);
  voices.forEach((v) => {
    const o = document.createElement('option');
    o.value = v.key; o.textContent = v.label;
    if (v.key === STATE.voice) o.selected = true;
    sel.appendChild(o);
  });
  sel.addEventListener('change', () => {
    STATE.voice = sel.value;
    localStorage.setItem('zork-voice', STATE.voice);
    if (STATE.started) narrateCurrent();
  });
  control.hidden = false;
}

function buildThemeSelect() {
  const sel = qs('#theme-select');
  if (!sel) return;
  sel.value = STATE.theme;
  sel.addEventListener('change', () => applyTheme(sel.value));
}

function wireAudioControls() {
  const nBtn = qs('#narration-toggle'), nVol = qs('#tts-vol');
  STATE.ttsVol = parseFloat(nVol.value); qs('#narration').volume = STATE.ttsVol;
  nBtn.addEventListener('click', () => {
    STATE.narrationOn = !STATE.narrationOn;
    nBtn.setAttribute('aria-pressed', String(STATE.narrationOn));
    if (!STATE.narrationOn) qs('#narration').pause();
  });
  nVol.addEventListener('input', () => { STATE.ttsVol = parseFloat(nVol.value); qs('#narration').volume = STATE.ttsVol; });

  const mBtn = qs('#music-toggle'), mVol = qs('#music-vol');
  Music.setVol(parseFloat(mVol.value));
  mBtn.addEventListener('click', () => {
    const on = mBtn.getAttribute('aria-pressed') !== 'true';
    mBtn.setAttribute('aria-pressed', String(on));
    Music.setOn(on);
  });
  mVol.addEventListener('input', () => Music.setVol(parseFloat(mVol.value)));
}

/* One click in the parent grants audio autoplay for the session. */
function wireStart() {
  const overlay = qs('#start-overlay');
  qs('#start-btn').addEventListener('click', () => {
    STATE.started = true;
    overlay.hidden = true;
    Music.kick();
    if (STATE.current) maybeNarrate(STATE.current, STATE.manifest.scenes[STATE.current]);
    try { qs('#game-frame').contentWindow.focus(); } catch (e) {}
    nudgeFrame();
  });
}

function showFatal(msg) { document.body.insertAdjacentHTML('afterbegin', '<div class="fatal">' + msg + '</div>'); }

/* GlkOte inside the iframe can lay out with a stale/zero size until a resize
   fires (the "only renders after opening dev tools" bug). Nudge it after load,
   on the Start click, and on window resize; also sync the theme once it loads. */
function nudgeFrame() {
  try { qs('#game-frame').contentWindow.dispatchEvent(new Event('resize')); } catch (e) {}
}
function setupInterpreterNudge() {
  const f = qs('#game-frame');
  [200, 700, 1500, 2500].forEach((t) => setTimeout(nudgeFrame, t));
  f.addEventListener('load', () => {
    applyThemeToFrame();
    [150, 600].forEach((t) => setTimeout(nudgeFrame, t));
  });
  window.addEventListener('resize', nudgeFrame);
}

/* ---------- room source: read the room name from the iframe's game buffer ---------- */
class IframeRoomSource {
  constructor(iframe, roomNames, startRoom) {
    this.iframe = iframe; this.rooms = new Set(roomNames); this.startRoom = startRoom;
    this._cb = null; this._obs = null; this._last = null;
  }
  onRoom(cb) { this._cb = cb; }
  start() {
    const attach = () => {
      let doc = null;
      try { doc = this.iframe.contentDocument; } catch (e) { doc = null; }
      const buf = doc && doc.querySelector('.BufferWindow');
      if (!buf) return void setTimeout(attach, 400);
      applyThemeToFrame();
      if (this.startRoom && this._cb) { this._last = this.startRoom; this._cb(this.startRoom); }
      const scan = () => {
        const lines = doc.querySelectorAll('.BufferWindow .BufferLine');
        for (let i = lines.length - 1; i >= 0 && i > lines.length - 10; i--) {
          const t = lines[i].textContent.replace(/\s+/g, ' ').trim();
          if (this.rooms.has(t)) { if (t !== this._last) { this._last = t; this._cb(t); } return; }
        }
      };
      this._obs = new MutationObserver(scan);
      this._obs.observe(buf, { childList: true, subtree: true });
      scan();
    };
    attach();
  }
}

document.addEventListener('DOMContentLoaded', init);
