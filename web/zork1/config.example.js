// Copy this file to config.js (gitignored) and fill in your values.
// index.html loads config.js before app.js.
//
// WARNING: ttsToken is shipped to the browser. That's fine for local or private
// use, but on a PUBLIC deploy (e.g. GitHub Pages) anyone can read it from the
// page source. For a public site, proxy the TTS server (so the token stays
// server-side) or pre-bake the narration audio instead of calling /tts live.

window.ZORK_CONFIG = {
  ttsBase: "https://tts.akaraduman.synology.me",
  ttsToken: ""   // Bearer token for your TTS server
};
