'use strict';

/* Scene controller. The game runs in a same-origin iframe (play.html / Parchment);
   we read the room name from the buffer (a line that exactly matches a known scene
   key), then swap the scene image, region music, and narration.
   - Narration: live TTS via POST /tts in the player-selected voice (static fallback).
   - Music: per-region playlist of 2 tracks played successively, looping. */

const qs = (s) => document.querySelector(s);
const CFG = window.ZORK_CONFIG || {};
const TTS_READY = !!(CFG.ttsBase && CFG.ttsToken);
const ttsUrl = (p) => CFG.ttsBase.replace(/\/$/, '') + p;

const STATE = {
  manifest: null, style: null, voice: null,
  narrationOn: true, ttsVol: 1, started: false,
  visited: new Set(), current: null, ttsCache: new Map(),
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
  try { STATE.manifest = await (await fetch('manifest.json')).json(); }
  catch (e) { return showFatal('Could not load manifest.json (' + e + ')'); }

  const params = new URLSearchParams(location.search);
  STATE.style = params.get('style') || STATE.manifest.default_style || STATE.manifest.styles[0];
  buildStyleSelect();
  Music.init();
  wireAudioControls();
  wireStart();
  await buildVoiceSelect();

  const source = new IframeRoomSource(qs('#game-frame'), Object.keys(STATE.manifest.scenes), STATE.manifest.start_room);
  source.onRoom(handleRoom);
  source.start();
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

function maybeNarrate(name, scene) {
  if (scene && STATE.narrationOn && !STATE.visited.has(name)) {
    STATE.visited.add(name);
    playNarration(scene);
  }
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

/* ---------- narration ---------- */
async function playNarration(scene) {
  if (!STATE.narrationOn || !scene) return;
  let url = null;
  try {
    if (TTS_READY && STATE.voice && scene.narration) url = await synth(scene.slug, scene.narration, STATE.voice);
  } catch (e) { console.warn('TTS synth failed, falling back to static audio:', e); }
  if (!url) url = scene.audio || null;
  if (!url) return;
  const a = qs('#narration');
  a.volume = STATE.ttsVol;
  a.src = url;
  a.play().catch(() => {});
}

async function synth(slug, text, voice) {
  const key = voice + '::' + slug;
  if (STATE.ttsCache.has(key)) return STATE.ttsCache.get(key);
  const res = await fetch(ttsUrl('/tts'), {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + CFG.ttsToken, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice }),
  });
  if (!res.ok) throw new Error('TTS HTTP ' + res.status);
  const url = URL.createObjectURL(await res.blob());
  STATE.ttsCache.set(key, url);
  return url;
}

/* ---------- voices ---------- */
async function buildVoiceSelect() {
  const control = qs('#voice-control');
  if (!TTS_READY) { control.hidden = true; return; }
  let voices;
  try {
    const res = await fetch(ttsUrl('/voices'), { headers: { 'Authorization': 'Bearer ' + CFG.ttsToken } });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    voices = await res.json();
  } catch (e) { console.warn('voices fetch failed:', e); control.hidden = true; return; }

  const en = voices.filter((v) => (v.Locale || '').toLowerCase().startsWith('en'))
    .sort((a, b) => (a.Locale + a.ShortName).localeCompare(b.Locale + b.ShortName));
  if (!en.length) { control.hidden = true; return; }

  const sel = qs('#voice-select');
  let lastLocale = null, group = null;
  en.forEach((v) => {
    if (v.Locale !== lastLocale) { group = document.createElement('optgroup'); group.label = v.Locale; sel.appendChild(group); lastLocale = v.Locale; }
    const o = document.createElement('option');
    o.value = v.ShortName;
    o.textContent = v.ShortName.replace(/^en-[A-Za-z]+-/, '').replace(/Neural$/, '');
    group.appendChild(o);
  });
  const saved = localStorage.getItem('zork-voice');
  STATE.voice = saved && en.some((v) => v.ShortName === saved) ? saved
    : (en.some((v) => v.ShortName === 'en-US-AriaNeural') ? 'en-US-AriaNeural' : en[0].ShortName);
  sel.value = STATE.voice;
  sel.addEventListener('change', () => { STATE.voice = sel.value; localStorage.setItem('zork-voice', STATE.voice); });
  control.hidden = false;
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

/* Start gate: one click in the parent document grants audio autoplay for the
   session, then music + narration flow even as the player types in the iframe. */
function wireStart() {
  const overlay = qs('#start-overlay');
  qs('#start-btn').addEventListener('click', () => {
    STATE.started = true;
    overlay.hidden = true;
    Music.kick();
    if (STATE.current) maybeNarrate(STATE.current, STATE.manifest.scenes[STATE.current]);
    try { qs('#game-frame').contentWindow.focus(); } catch (e) {}
  });
}

function showFatal(msg) { document.body.insertAdjacentHTML('afterbegin', '<div class="fatal">' + msg + '</div>'); }

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
