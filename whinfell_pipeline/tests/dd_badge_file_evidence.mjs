#!/usr/bin/env node
/**
 * Non-mocked badge evidence: reads data_dictionary_meta.json from disk via fetch shim
 * (same sibling-file path Transmission Control uses under file://).
 * DICTIONARY_BADGE_DEFAULT comes from sync-injected HTML block (from master_dictionary_info).
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML_PATH = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const META_JSON = path.join(REPO, '08_Deliverables/data_dictionary_meta.json');

function extractBadgeDefault(html) {
  const m = html.match(/<!-- DD_BADGE_SYNC_START -->[\s\S]*?window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});[\s\S]*?<!-- DD_BADGE_SYNC_END -->/);
  if (!m) throw new Error('DD_BADGE_SYNC block or DICTIONARY_BADGE_DEFAULT missing');
  return JSON.parse(m[1]);
}

function extractMainScript(html) {
  const m = html.match(/<script>\s*\/\*\* Whinfell Transmission Control[\s\S]*?<\/script>/);
  if (!m) throw new Error('main script block not found');
  let body = m[0].replace(/^<script>\s*/, '').replace(/\s*<\/script>$/, '');
  const cut = body.indexOf("el('btnSave').onclick");
  if (cut >= 0) body = body.slice(0, cut);
  return body;
}

function diskFetch(url) {
  const u = String(url);
  if (!u.includes('data_dictionary_meta.json')) {
    return Promise.reject(new Error(`unexpected fetch url: ${u}`));
  }
  const raw = fs.readFileSync(META_JSON, 'utf8');
  return Promise.resolve({
    ok: true,
    json: async () => JSON.parse(raw),
  });
}

function makeSandbox() {
  class El {
    constructor(id) {
      this.id = id;
      this.textContent = '';
      this.title = '';
      this.className = '';
      this.classList = {
        _s: new Set(),
        toggle(c, f) {
          if (f === true) this._s.add(c);
          else if (f === false) this._s.delete(c);
          else this._s.has(c) ? this._s.delete(c) : this._s.add(c);
        },
      };
    }
    addEventListener() {}
  }
  const els = { ddVersionBadge: new El('ddVersionBadge') };
  return {
    document: {
      getElementById(id) {
        if (!els[id]) els[id] = new El(id);
        return els[id];
      },
      querySelectorAll: () => [],
      querySelector: () => ({ value: 'full' }),
    },
    window: {},
    localStorage: { getItem: () => null, setItem: () => {} },
    console,
    setTimeout,
    clearTimeout,
    Date,
    JSON,
    Math,
    fetch: diskFetch,
  };
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const badgeDefault = extractBadgeDefault(html);
const metaOnDisk = JSON.parse(fs.readFileSync(META_JSON, 'utf8'));

const sandbox = makeSandbox();
sandbox.window.DICTIONARY_BADGE_DEFAULT = badgeDefault;
vm.createContext(sandbox);

const boot = `
window.DICTIONARY_BADGE_DEFAULT = ${JSON.stringify(badgeDefault)};
${extractMainScript(html)}
(async () => {
  renderDataDictionaryBadge(true);
  await new Promise(r => setTimeout(r, 30));
  const loadText = document.getElementById('ddVersionBadge').textContent;
  renderDataDictionaryBadge(true);
  await new Promise(r => setTimeout(r, 30));
  globalThis.__evidence = {
    loadText,
    refreshText: document.getElementById('ddVersionBadge').textContent,
    meta: ddMetaCache,
    validated: validateDataDictionaryMeta(ddMetaCache),
  };
})();
`;
vm.runInContext(boot, sandbox, { filename: 'dd-badge-file-evidence.mjs' });
await new Promise((r) => setTimeout(r, 120));
const out = { ...sandbox.__evidence, badgeDefault, metaOnDisk };
if (!out.loadText) throw new Error('__evidence missing — async badge render did not complete');

const lines = [
  '=== dd_badge_file_evidence (disk-backed, no in-memory meta mock) ===',
  `timestamp: ${new Date().toISOString()}`,
  `html_sync_block: DD_BADGE_SYNC_START present=${html.includes('DD_BADGE_SYNC_START')}`,
  `injected_default.version: ${out.badgeDefault.version}`,
  `injected_default.status: ${out.badgeDefault.status}`,
  `injected_default.source: ${out.badgeDefault.source}`,
  `meta_json.version: ${out.metaOnDisk.version}`,
  `meta_json.status: ${out.metaOnDisk.status}`,
  `meta_json.validated: ${out.metaOnDisk.validated}`,
  `yaml_chain: sync_dictionary_meta.py -> master_dictionary_info() -> badge_default_payload() + build_meta_payload()`,
  `fetch_mode: disk read ${META_JSON} (sibling file:// path)`,
  `validateDataDictionaryMeta: ${out.validated}`,
  `load_badge_text: ${out.loadText}`,
  `refresh_badge_text: ${out.refreshText}`,
];

for (const line of lines) console.log(line);

if (!out.validated) {
  console.error('FAIL validation');
  process.exit(1);
}
for (const t of [out.loadText, out.refreshText]) {
  if (!t.includes(`Master Data Dictionary v${out.badgeDefault.version}`)) {
    console.error('FAIL missing version in badge:', t);
    process.exit(1);
  }
  if (!t.includes(out.badgeDefault.status)) {
    console.error('FAIL missing status in badge:', t);
    process.exit(1);
  }
}
console.log('PASS dd_badge_file_evidence');
process.exit(0);