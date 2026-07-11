#!/usr/bin/env node
/** Verification plan step 3: load TC script in vm with window shim (not raw HTML). */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML_PATH = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const CHINA_MODELS_JS = path.join(REPO, '08_Deliverables/desk_china_ladder_models.js');
const META_JSON = path.join(REPO, '08_Deliverables/data_dictionary_meta.json');

function extractBadgeDefault(html) {
  const m = html.match(/window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});/);
  if (!m) throw new Error('DICTIONARY_BADGE_DEFAULT not found');
  return JSON.parse(m[1]);
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const chinaModels = fs.readFileSync(CHINA_MODELS_JS, 'utf8');
const badgeDefault = extractBadgeDefault(html);
const metaPayload = JSON.parse(fs.readFileSync(META_JSON, 'utf8'));
const block = html.match(/<script>\s*\/\*\* Whinfell Transmission Control[\s\S]*?<\/script>/);
if (!block) throw new Error('main script block not found');

const ddStub = `
window.DICTIONARY_BADGE_DEFAULT = ${JSON.stringify(badgeDefault)};
globalThis.fetch = () => Promise.resolve({ ok: true, json: async () => (${JSON.stringify(metaPayload)}) });
`;
let body = ddStub + chinaModels + '\n' + block[0].replace(/^<script>\s*/, '').replace(/\s*<\/script>$/, '');
const cut = body.indexOf("el('btnSave').onclick");
if (cut >= 0) body = body.slice(0, cut);

class CList {
  constructor() { this._set = new Set(); }
  add(...c) { c.forEach(x => this._set.add(x)); }
  remove(...c) { c.forEach(x => this._set.delete(x)); }
  toggle(c, force) {
    if (force === true) { this._set.add(c); return true; }
    if (force === false) { this._set.delete(c); return false; }
    if (this._set.has(c)) { this._set.delete(c); return false; }
    this._set.add(c); return true;
  }
  contains(c) { return this._set.has(c); }
}

class El {
  constructor(id) {
    this.id = id;
    this.classList = new CList();
    this.style = {};
    this.dataset = {};
    this.innerHTML = '';
    this.textContent = '';
    this.value = '';
    this.scrollTop = 0;
  }
  addEventListener() {}
  querySelectorAll() { return []; }
  querySelector() { return null; }
}

const els = {};
const ctx = {
  document: {
    getElementById(id) {
      if (!els[id]) els[id] = new El(id);
      return els[id];
    },
    querySelectorAll() { return []; },
    querySelector(sel) {
      if (sel === '#cockpitShell .cockpit-main') {
        if (!els._main) els._main = new El('cockpitMain');
        return els._main;
      }
      return null;
    },
    addEventListener() {},
  },
  localStorage: { getItem: () => null, setItem: () => {} },
  window: { open() {}, devicePixelRatio: 1 },
  navigator: { clipboard: { writeText: async () => {} } },
  console, setTimeout, clearTimeout, Date, JSON, Math, Number, parseInt, parseFloat, Array, Object, Error,
};

vm.createContext(ctx);
vm.runInContext(body, ctx);

const ladderLen = vm.runInContext('typeof LADDER !== "undefined" ? LADDER.length : 0', ctx);
const ok = typeof ctx.renderNodeCockpitShell === 'function'
  && typeof ctx.flipNode === 'function'
  && typeof ctx.setActiveNode === 'function'
  && typeof ctx.drawRvBasisChart === 'function'
  && ladderLen === 5;

console.log('loaded_ok', ok);
if (!ok) process.exit(1);