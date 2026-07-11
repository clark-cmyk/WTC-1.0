#!/usr/bin/env node
/** Headless parity: Python fixture horizons → TC cluster, Grok, WTM export, Deep Dive summary. */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const TC_HTML = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const LADDER_JS = path.join(REPO, '08_Deliverables/desk_china_ladder_models.js');
const BUNDLE_PATH = path.join(REPO, 'whinfell_pipeline/examples/hydration_bundle.json');

const FIXTURE = {
  liquidity: { d1: 'flat', d5: 'flat', d20: 'down', d60: 'flat' },
  credit: { d1: 'flat', d5: 'flat', d20: 'flat', d60: 'down' },
  breadth: { d1: 'up', d5: 'flat', d20: 'flat', d60: 'flat' },
  highbeta: { d1: 'flat', d5: 'down', d20: 'flat', d60: 'flat' },
  basis: { d1: 'flat', d5: 'flat', d20: 'down', d60: 'flat' },
};
const SQ3 = 54;

function extractTcScript(html) {
  const m = html.match(/<script>\s*\/\*\* Whinfell Transmission Control[\s\S]*?<\/script>/);
  if (!m) throw new Error('TC main script not found');
  let body = m[0].replace(/^<script>\s*/, '').replace(/\s*<\/script>$/, '');
  const cut = body.indexOf("el('btnSave').onclick");
  if (cut >= 0) body = body.slice(0, cut);
  return body;
}

function makeSandbox() {
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
      this.id = id; this.value = ''; this.textContent = ''; this.className = '';
      this.innerHTML = ''; this.disabled = false; this.dataset = {}; this.style = {};
      this.classList = new CList(); this._listeners = {};
    }
    addEventListener() {}
  }
  const els = {};
  return {
    document: {
      getElementById(id) { if (!els[id]) els[id] = new El(id); return els[id]; },
      querySelectorAll() { return []; },
      querySelector() { return { value: 'full' }; },
    },
    localStorage: { _data: {}, getItem() { return null; }, setItem() {} },
    window: { open() {} },
    navigator: { clipboard: { writeText: async () => {} } },
    console, setTimeout, clearTimeout, Date, JSON, Math, Number, parseInt, parseFloat,
    Array, Object, Error, RegExp,
    _els: els,
  };
}

function seedTcDom(sb) {
  const ids = [
    'whinfellScore', 'transmissionState', 'regimeTag', 'chinaPolicyStrength', 'chinaStateImpulse',
    'chinaGrowthImpulse', 'chinaRegimeTag', 'grossA', 'grossB', 'posture', 'handoverNote',
    'cmdGlobalCluster', 'cmdChinaCluster', 'sq3ComputedDisplay', 'sq3BandChip',
    'operatorConfidence', 'executionIntent', 'basisRegimeLabel', 'keyObservation', 'evidenceNote',
    'shockProbability', 'shockHorizon', 'provenanceDisplay', 'tracerHorizonBody',
    'chinaTracerHorizonBody', 'chinaLadderBadge', 'chinaLadderSummary',
  ];
  ids.forEach(id => sb.document.getElementById(id));
  sb.document.getElementById('whinfellScore').value = '58';
  sb.document.getElementById('transmissionState').value = 'stressed';
  sb.document.getElementById('regimeTag').value = 'Fragile Risk-On';
  sb.document.getElementById('chinaPolicyStrength').value = '68';
  sb.document.getElementById('chinaStateImpulse').value = '22';
  sb.document.getElementById('chinaGrowthImpulse').value = '55';
}

function runTc() {
  const ladderJs = fs.readFileSync(LADDER_JS, 'utf8');
  const tcBody = extractTcScript(fs.readFileSync(TC_HTML, 'utf8'));
  const sb = makeSandbox();
  seedTcDom(sb);
  const ctx = vm.createContext(sb);
  vm.runInContext(`${ladderJs}\n${tcBody}\nappState = createEmptyState();`, ctx);
  vm.runInContext(`
    appState.chinaLadder = { horizons: ${JSON.stringify(FIXTURE)} };
    appState.china = { policyStrength: '68', stateImpulse: '22', growthImpulse: '55', regimeTag: '' };
    appState.intake = { whinfellScore: '58', transmissionState: 'stressed', regimeTag: 'Fragile Risk-On' };
    appState.provenance = createEmptyProvenance();
    const state = buildStateFromDOM();
    const read = computeChinaLadderRead(state);
    renderLadderCommandClusters(state);
    const grok = buildGrokPayload(state);
    const wtm = buildWtmExportV21();
    __out = {
      read,
      clusterHtml: document.getElementById('cmdChinaCluster').innerHTML,
      grokChina: grok.master_state.china_ladder,
      wtm,
    };
  `, ctx);
  return sb.__out;
}

function runDeepDiveParity() {
  const ladderJs = fs.readFileSync(LADDER_JS, 'utf8');
  const sb = makeSandbox();
  const ctx = vm.createContext(sb);
  vm.runInContext(ladderJs, ctx);
  vm.runInContext(`
    const hz = ${JSON.stringify(FIXTURE)};
    const sq3 = ${SQ3};
    const stages = CHINA_LADDER_STAGES.map(function (d) {
      return {
        id: d.id,
        name: d.name,
        score: compositeChinaStageScore(d.id, hz),
        net: chinaHorizonNet(hz[d.id] || {}),
      };
    });
    const weakest = weakestStage(stages, 'composite');
    const avg = Math.round(stages.reduce(function (a, s) { return a + s.score; }, 0) / stages.length);
    const mult = chinaSq3Multiplier(sq3);
    const finalScore = Math.max(0, Math.min(100, Math.round(avg * mult)));
    const bandInfo = chinaLadderFinalBand(finalScore);
    __out = {
      raw: avg,
      final: finalScore,
      band: bandInfo.band,
      weakest_stage: weakest.name,
      sq3: sq3,
    };
  `, ctx);
  return sb.__out;
}

function parseCluster(html, read) {
  return {
    raw: read.raw,
    final: read.finalScore,
    band: read.band,
    weakest_stage: read.weakestStage,
    has_cluster: html.includes('China final (adj.)'),
  };
}

function main() {
  const tc = runTc();
  const dd = runDeepDiveParity();
  const cluster = parseCluster(tc.clusterHtml, tc.read);
  const payload = {
    kernel: {
      raw: tc.read.raw,
      final: tc.read.finalScore,
      band: tc.read.band,
      weakest_stage: tc.read.weakestStage,
      sq3: tc.read.sq3,
    },
    tc_cluster: cluster,
    deep_dive: dd,
    grok: { china_ladder: tc.grokChina },
    wtm_export: tc.wtm,
  };
  console.log('china_handoff_headless_ok');
  console.log(JSON.stringify(payload));
}

main();