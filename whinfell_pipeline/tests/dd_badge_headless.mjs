#!/usr/bin/env node
/** Headless: DICTIONARY_BADGE_DEFAULT (sync-injected) + fetch meta.json → badge text. */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML_PATH = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const META_JSON = path.join(REPO, '08_Deliverables/data_dictionary_meta.json');

function extractBadgeDefault(html) {
  const m = html.match(/window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});/);
  if (!m) throw new Error('DICTIONARY_BADGE_DEFAULT not found in HTML');
  return JSON.parse(m[1]);
}

function extractScript(html) {
  const m = html.match(/<script>\s*\/\*\* Whinfell Transmission Control[\s\S]*?<\/script>/);
  if (!m) throw new Error('main script block not found');
  let body = m[0].replace(/^<script>\s*/, '').replace(/\s*<\/script>$/, '');
  const cut = body.indexOf("el('btnSave').onclick");
  if (cut >= 0) body = body.slice(0, cut);
  const badgeDefault = extractBadgeDefault(html);
  const metaPayload = JSON.parse(fs.readFileSync(META_JSON, 'utf8'));
  body = `
window.DICTIONARY_BADGE_DEFAULT = ${JSON.stringify(badgeDefault)};
let __fetchCount = 0;
globalThis.fetch = () => {
  __fetchCount += 1;
  return Promise.resolve({ ok: true, json: async () => JSON.parse(JSON.stringify(${JSON.stringify(metaPayload)})) });
};
` + body + `
(async () => {
  renderDataDictionaryBadge(true);
  await new Promise(r => setTimeout(r, 25));
  const loadText = document.getElementById('ddVersionBadge').textContent;
  renderDataDictionaryBadge(true);
  await new Promise(r => setTimeout(r, 25));
  globalThis.__ddOut = {
    fetchCount: __fetchCount,
    loadText,
    refreshText: document.getElementById('ddVersionBadge').textContent,
    badgeDefault: window.DICTIONARY_BADGE_DEFAULT,
    meta: ddMetaCache,
    validated: validateDataDictionaryMeta(ddMetaCache),
  };
})();
`;
  return body;
}

function makeSandbox() {
  class El {
    constructor(id) {
      this.id = id; this.textContent = ''; this.title = ''; this.className = '';
      this.classList = { _s: new Set(), toggle(c, f) { if (f === true) this._s.add(c); else if (f === false) this._s.delete(c); else this._s.has(c) ? this._s.delete(c) : this._s.add(c); } };
      this.value = ''; this.innerHTML = ''; this.dataset = {}; this.style = {}; this.disabled = false;
    }
    addEventListener() {}
  }
  const els = { ddVersionBadge: new El('ddVersionBadge') };
  return {
    document: {
      getElementById(id) { if (!els[id]) els[id] = new El(id); return els[id]; },
      querySelectorAll: () => [],
      querySelector: () => ({ value: 'full' }),
    },
    window: {}, localStorage: { getItem: () => null, setItem: () => {} },
    console, setTimeout, clearTimeout, Date, JSON, Math, Number, parseInt, parseFloat, Array, Object, Error, Promise,
    navigator: { clipboard: { writeText: async () => {} } },
  };
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const sandbox = makeSandbox();
vm.createContext(sandbox);
vm.runInContext(extractScript(html), sandbox, { filename: 'tc-dd-badge.mjs' });

setTimeout(() => {
  const out = sandbox.__ddOut;
  if (!out) { console.error('FAIL no output'); process.exit(1); }
  if (out.fetchCount < 2) { console.error('FAIL fetchCount', out.fetchCount); process.exit(1); }
  if (!out.badgeDefault?.version) { console.error('FAIL no injected badge default'); process.exit(1); }
  if (!out.validated) { console.error('FAIL validation', out.meta, out.badgeDefault); process.exit(1); }
  for (const label of ['loadText', 'refreshText']) {
    const t = out[label] || '';
    if (!t.includes(`Master Data Dictionary v${out.badgeDefault.version}`)) {
      console.error(`FAIL ${label}:`, t); process.exit(1);
    }
    if (!t.includes(out.badgeDefault.status)) { console.error(`FAIL ${label} status:`, t); process.exit(1); }
  }
  console.log('PASS dd_badge_headless injected:', out.badgeDefault.version, out.badgeDefault.status);
  console.log('PASS dd_badge_headless refresh:', out.refreshText);
  process.exit(0);
}, 300);