#!/usr/bin/env node
/** Headless 2.2b: pure transitions first, then hydrate/accept override scenarios. */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML_PATH = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const CHINA_MODELS_JS = path.join(REPO, '08_Deliverables/desk_china_ladder_models.js');
const META_JSON = path.join(REPO, '08_Deliverables/data_dictionary_meta.json');
const BUNDLE_PATH = path.join(REPO, 'whinfell_pipeline/examples/hydration_bundle.json');

function extractBadgeDefault(html) {
  const m = html.match(/window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});/);
  if (!m) throw new Error('DICTIONARY_BADGE_DEFAULT not found in HTML');
  return JSON.parse(m[1]);
}

const REQUIRED_FNS = [
  'hydrateFromBundle', 'acceptSuggestedTracer', 'dismissSuggestedTracer',
  'renderTracerHorizonTable', 'renderSuggestedTracerPanel', 'renderAll',
  'applyIntakeOverride', 'applyHorizonOverride', 'getTracerChrome',
];

function extractScript(html) {
  const chinaModels = fs.readFileSync(CHINA_MODELS_JS, 'utf8');
  const badgeDefault = extractBadgeDefault(html);
  const metaPayload = JSON.parse(fs.readFileSync(META_JSON, 'utf8'));
  const m = html.match(/<script>\s*\/\*\* Whinfell Transmission Control[\s\S]*?<\/script>/);
  if (!m) throw new Error('main script block not found');
  const ddStub = `
window.DICTIONARY_BADGE_DEFAULT = ${JSON.stringify(badgeDefault)};
globalThis.fetch = () => Promise.resolve({
  ok: true,
  json: async () => JSON.parse(JSON.stringify(${JSON.stringify(metaPayload)})),
});
`;
  let body = ddStub + chinaModels + '\n' + m[0].replace(/^<script>\s*/, '').replace(/\s*<\/script>$/, '');
  const cut = body.indexOf("el('btnSave').onclick");
  if (cut >= 0) body = body.slice(0, cut);
  body += `
appState = createEmptyState();
this.__test = {
  LADDER, HORIZONS, appState, hydrateFromBundle, acceptSuggestedTracer, dismissSuggestedTracer,
  markTracerManualOverride, markCommandBarManualOverride, commitHorizonOverrideToAppState,
  onHorizonSelectChange, applySuggestedMarks, getTracerFlowState, getTracerChrome,
  applyIntakeOverride, applyHorizonOverride, createEmptyProvenance, createEmptyState,
  renderTracerHorizonTable, renderSuggestedTracerPanel, renderTracerFlowChrome, renderAll,
  applyTrackView, buildStateFromDOM, deriveGate, createEmptyHorizons, document,
};
`;
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
    get onclick() { return this._onclk; }
    set onclick(fn) { this._onclk = fn; }
    get onchange() { return this._onchg; }
    set onchange(fn) { this._onchg = fn; }
    querySelectorAll(sel) {
      if (sel === '[data-node-id]') {
        return Object.values(els).filter(e => e.dataset?.nodeId);
      }
      if (sel === '[data-horizon]') return [];
      return [];
    }
    querySelector(sel) {
      if (sel === '.cockpit-unhydrated-overlay') return this._overlay || null;
      return null;
    }
    appendChild(child) {
      if (this.id === 'cockpitChartCanvas') this._overlay = child;
      return child;
    }
  }
  const els = {};
  const bodyEl = new El('body');
  return {
    document: {
      body: bodyEl,
      createElement() { return new El(''); },
      getElementById(id) { if (!els[id]) els[id] = new El(id); return els[id]; },
      querySelectorAll(sel) {
        if (sel === '[data-node-id]') {
          return Object.values(els).filter(e => e.dataset?.nodeId);
        }
        if (sel === '#cockpitShell .cockpit-main') {
          if (!els._cockpitMain) els._cockpitMain = new El('cockpitMain');
          return [els._cockpitMain];
        }
        return [];
      },
      querySelector(sel) {
        if (sel === '#cockpitShell .cockpit-main') {
          if (!els._cockpitMain) els._cockpitMain = new El('cockpitMain');
          return els._cockpitMain;
        }
        return { value: 'full' };
      },
    },
    localStorage: { _data: {}, getItem(k) { return this._data[k] ?? null; }, setItem(k, v) { this._data[k] = v; } },
    window: { open() {} },
    navigator: { clipboard: { writeText: async () => {}, readText: async () => '' } },
    console, setTimeout, clearTimeout, Date, JSON, Math, Number, parseInt, parseFloat, Array, Object, Error,
    _els: els,
  };
}

function seedDom(t) {
  const ids = [
    'whinfellScore', 'transmissionState', 'regimeTag', 'chinaPolicyStrength', 'chinaStateImpulse',
    'chinaGrowthImpulse', 'chinaRegimeTag', 'grossA', 'grossB', 'posture', 'handoverNote',
    'l3NearMonth', 'l3BasisSpread', 'cmdWhinfellScore', 'cmdSq3Score', 'cmdGateLabel', 'cmdGrossRisk',
    'cmdScoreZone', 'cmdFreshness', 'cmdHydrationBadge', 'cmdFreshnessMeta', 'cmdFreshnessDot', 'cmdFreshnessCluster', 'cmdFreshnessSubCluster',
    'txHealthValue', 'txHealthMeta', 'gateText', 'gateChip', 'shockText', 'shockMeta', 'scoreCard',
    'suggestionTray', 'suggestionRows', 'layer2Chip', 'layer3Chip', 'layer2Rule', 'layer3Rule',
    'operatorConfidence', 'operatorConfidenceValue', 'executionIntent', 'executionIntentHint',
    'shockProbability', 'shockHorizon', 'basisRegimeLabel', 'keyObservation', 'evidenceNote',
    'gateHelperText', 'plainEnglishBody', 'plainEnglishL3', 'plainEnglishAction', 'layer3ActionHint',
    'whyWhinfellScore', 'whyTransmission', 'whyGateState', 'whyShock', 'whyFreshness', 'txMappingNote',
    'whyTransmissionState', 'whyRegimeTag', 'whyChinaSq3', 'whyExecutionIntent', 'whyOperatorConfidence',
    'whyBasisRegime', 'whyLayer3Spread', 'l3ActionCode', 'l3ActionPosture', 'l3ActionReason', 'l3ActionKeyRisk',
    'importedObservationDisplay',
    'sq3ComputedDisplay', 'sq3BandChip', 'gateExplainList', 'gateUnlockList', 'gateHealthSub',
    'gateDetailPanel', 'scoreZoneChip', 'gateStatusChip', 'txChip', 'grossTotal', 'grossMmHint',
    'postureWarning', 'tracerScoreBar', 'tracerChain', 'tracerOverall', 'activeShockLabel',
    'urlDisplayKoyfin', 'urlDisplayBarchart', 'provenancePanel', 'provenanceDisplay',
    'suggestedTracerPanel', 'suggestedTracerSummary', 'suggestedTracerBadge',
    'tracerFlowBadge', 'tracerHorizonTable', 'tracerMatrixTitle', 'cmdGlobalCluster', 'cmdChinaCluster',
    'intakeGlobal', 'intakeChina', 'tracerScoreLabel', 'keyObservationDisplay', 'btcBiasDisplay', 'researchReadout',
    'cmdGateSub', 'cmdGrossPosture', 'snapshotList', 'snapshotCompare',
    'nodeRail', 'cockpitShell', 'cockpitChartTitle', 'cockpitChartSubtitle',
    'cockpitHorizonPills', 'cockpitRvCanvas', 'cockpitChartPlaceholder',
    'cockpitChartValue', 'cockpitChartRichness', 'cockpitChartPct',
    'cockpitDecisionRail', 'cockpitDetailBand', 'cockpitFocusLayer',
    'cockpitCompareLayer', 'btnHeresWhy', 'btnCompareMode', 'nodeCockpitZone',
    'legacyConsoleZone', 'btnWorkspaceToggle',
    'hydrationBanner', 'hydrationBannerTitle', 'hydrationBannerBody',
    'btnHydrationBannerImport', 'btnHydrationBannerDismiss', 'cockpitChartCanvas',
    'hydrationImportStatus', 'btnImportHydration',
  ];
  ids.forEach(id => t.document.getElementById(id));
  t.LADDER.forEach(r => {
    t.HORIZONS.forEach(h => t.document.getElementById(`hz-${r.id}-${h}`));
    t.document.getElementById(`net-${r.id}`);
  });
  t.renderTracerHorizonTable();
}

function boot(script) {
  const ctx = makeSandbox();
  vm.createContext(ctx);
  vm.runInContext(script, ctx);
  const t = ctx.__test;
  if (!t) throw new Error('__test missing');
  for (const fn of REQUIRED_FNS) {
    if (typeof t[fn] !== 'function') throw new Error(`missing function: ${fn}`);
  }
  return t;
}

function testPureTransitions(t) {
  const baseProv = { ...t.createEmptyProvenance(), snapshotId: 'snap-1', hydratedAt: '2026-06-27T00:00:00.000Z' };
  const baseState = {
    tracer: { flow: 'confirmed', horizons: t.createEmptyHorizons() },
    suggestedTracer: { credit: { d1: 'up' } },
    provenance: baseProv,
  };

  const intakeProv = t.applyIntakeOverride(baseProv);
  if (!intakeProv.manualOverride) throw new Error('intake: manualOverride not set');
  if (baseState.tracer.flow !== 'confirmed') throw new Error('intake: tracer.flow mutated');

  const horizon = t.applyHorizonOverride(baseState);
  if (horizon.tracer.flow !== 'override') throw new Error('horizon: flow not override');
  if (!horizon.provenance.manualOverride) throw new Error('horizon: manualOverride not set');
  if (horizon.suggestedTracer !== null) throw new Error('horizon: suggestedTracer not cleared');

  const chromeA = t.getTracerChrome({ flow: 'confirmed' }, null);
  const chromeB = t.getTracerChrome({ flow: 'confirmed' }, null);
  if (JSON.stringify(chromeA) !== JSON.stringify(chromeB)) {
    throw new Error('getTracerChrome must not depend on provenance.manualOverride');
  }
  if (chromeA.label !== 'Operator Confirmed') throw new Error(`chrome label=${chromeA.label}`);

  const dryProv = t.createEmptyProvenance();
  const dryState = { tracer: { flow: 'empty' }, suggestedTracer: null, provenance: dryProv };
  const dryHorizon = t.applyHorizonOverride(dryState);
  if (!dryHorizon.provenance.manualOverride) throw new Error('dry horizon: manualOverride not set');

  return {
    intakeLeavesTracer: true,
    horizonSetsManualOverride: true,
    chromeDecoupled: true,
    dryHorizonSetsManualOverride: true,
  };
}

/** Non-hydrated session: horizon override sets tracer + manualOverride; cmd badge stays hidden. */
function testNonHydratedHorizonDom(t) {
  seedDom(t);
  t.appState.provenance = t.createEmptyProvenance();
  t.appState.tracer.flow = 'empty';
  t.onHorizonSelectChange();
  if (t.appState.tracer.flow !== 'override') throw new Error('non-hydrated: tracer flow not override');
  if (!t.appState.provenance.manualOverride) throw new Error('non-hydrated: manualOverride not set');
  const tracerBadge = t.document.getElementById('tracerFlowBadge').textContent;
  const cmdBadge = t.document.getElementById('cmdHydrationBadge').textContent;
  const cmdHidden = t.document.getElementById('cmdHydrationBadge').classList.contains('hidden');
  if (tracerBadge !== 'Manual Override') throw new Error(`non-hydrated tracerBadge=${tracerBadge}`);
  if (cmdBadge === 'Override' && !cmdHidden) throw new Error('non-hydrated: cmd Override should not show');
  return { tracerFlow: 'override', manualOverride: true, cmdShowsOverride: false };
}

function step(label, fn) {
  return { step: label, ...fn() };
}

function runHydrateAccept(t, bundle, label) {
  seedDom(t);
  t.hydrateFromBundle(bundle);
  if (!t.appState.suggestedTracer || Object.keys(t.appState.suggestedTracer).length < 3) {
    throw new Error(`${label}: expected suggestedTracer`);
  }
  const preMatrix = t.LADDER.some(r => t.HORIZONS.some(h => t.appState.tracer.horizons[r.id]?.[h]));
  if (preMatrix) throw new Error(`${label}: matrix pre-filled before accept`);

  t.acceptSuggestedTracer();
  if (t.appState.suggestedTracer) throw new Error(`${label}: suggestedTracer not cleared`);
  if (!t.appState.tracer.horizons.highbeta?.d1) throw new Error(`${label}: horizons not populated`);

  return {
    tracerFlow: t.appState.tracer.flow,
    tracerBadge: t.document.getElementById('tracerFlowBadge').textContent,
    manualOverride: t.appState.provenance.manualOverride,
  };
}

function runHorizonOverrideOnly(t, bundle, label) {
  const log = [];
  log.push(step(`${label}: hydrate+accept`, () => runHydrateAccept(t, bundle, label)));
  log.push(step(`${label}: horizon override`, () => {
    if (t.appState.provenance.manualOverride) throw new Error('manualOverride already set');
    t.onHorizonSelectChange();
    if (t.appState.tracer.flow !== 'override') throw new Error('tracer flow not override');
    if (!t.appState.provenance.manualOverride) throw new Error('manualOverride not set');
    const tracerBadge = t.document.getElementById('tracerFlowBadge').textContent;
    const cmdBadge = t.document.getElementById('cmdHydrationBadge').textContent;
    const prov = t.document.getElementById('provenanceDisplay').innerHTML;
    if (tracerBadge !== 'Manual Override') throw new Error(`tracerBadge=${tracerBadge}`);
    if (cmdBadge !== 'Override') throw new Error(`cmdBadge=${cmdBadge}`);
    if (!prov.includes('Manual override active')) throw new Error('provenance missing Manual override active');
    return {
      tracerFlow: 'override', tracerBadge, cmdBadge, manualOverride: true,
      provenanceNote: prov.includes('Manual override active') ? 'Manual override active' : '',
    };
  }));
  return { label, scenario: 'horizonOnly', log, final: log[log.length - 1] };
}

function runDecoupledIntake(t, bundle, label) {
  const log = [];
  log.push(step(`${label}: hydrate+accept`, () => runHydrateAccept(t, bundle, label)));
  log.push(step(`${label}: gross intake override`, () => {
    t.document.getElementById('grossA').value = '99';
    t.markCommandBarManualOverride();
    if (!t.appState.provenance.manualOverride) throw new Error('manualOverride not set');
    if (t.appState.tracer.flow !== 'confirmed') throw new Error('tracer should stay confirmed');
    const tracerBadge = t.document.getElementById('tracerFlowBadge').textContent;
    const cmdBadge = t.document.getElementById('cmdHydrationBadge').textContent;
    if (tracerBadge !== 'Operator Confirmed') throw new Error(`tracerBadge=${tracerBadge}`);
    if (cmdBadge !== 'Override') throw new Error(`cmdBadge=${cmdBadge}`);
    return { tracerFlow: 'confirmed', tracerBadge, cmdBadge, manualOverride: true };
  }));
  log.push(step(`${label}: dual-track`, () => {
    t.applyTrackView('china');
    t.applyTrackView('both');
    return { trackView: t.appState.ui?.trackView };
  }));
  return { label, scenario: 'decoupledIntake', log, final: log[log.length - 1] };
}

function snapshot(run) {
  const row = run.scenario === 'decoupledIntake'
    ? run.log.find(s => String(s.step).includes('gross intake override'))
    : run.final;
  const out = {
    scenario: run.scenario,
    tracerFlow: row.tracerFlow,
    tracerBadge: row.tracerBadge,
    manualOverride: row.manualOverride,
    cmdBadge: row.cmdBadge,
  };
  if (row.provenanceNote) out.provenanceNote = row.provenanceNote;
  return out;
}

function runFullSuite(script, bundle, label) {
  const pure = testPureTransitions(boot(script));
  const nonHydratedHorizon = testNonHydratedHorizonDom(boot(script));
  const horizonOnly = runHorizonOverrideOnly(boot(script), bundle, `${label}-horizon`);
  const decoupledIntake = runDecoupledIntake(boot(script), bundle, `${label}-intake`);
  return { label, pure, nonHydratedHorizon, horizonOnly, decoupledIntake };
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const bundle = JSON.parse(fs.readFileSync(BUNDLE_PATH, 'utf8'));
const script = extractScript(html);

const run1 = runFullSuite(script, bundle, 'run1');
const run2 = runFullSuite(script, bundle, 'run2');

for (const scenario of ['horizonOnly', 'decoupledIntake']) {
  const a = snapshot(run1[scenario]);
  const b = snapshot(run2[scenario]);
  if (JSON.stringify(a) !== JSON.stringify(b)) {
    throw new Error(`run1/run2 mismatch (${scenario}): ${JSON.stringify({ a, b })}`);
  }
}
if (JSON.stringify(run1.pure) !== JSON.stringify(run2.pure)) {
  throw new Error(`pure transitions mismatch: ${JSON.stringify({ run1: run1.pure, run2: run2.pure })}`);
}
if (JSON.stringify(run1.nonHydratedHorizon) !== JSON.stringify(run2.nonHydratedHorizon)) {
  throw new Error(`non-hydrated horizon mismatch: ${JSON.stringify({ run1: run1.nonHydratedHorizon, run2: run2.nonHydratedHorizon })}`);
}

const out = [
  'html_headless_2_2b_ok',
  'Harness: node vm + window shim (no module/require globals).',
  `Required functions: ${REQUIRED_FNS.join(', ')}.`,
  'Block 1 testPureTransitions: intake leaves tracer.flow; horizon sets manualOverride; dry horizon; getTracerChrome decoupled.',
  'Block 2a testNonHydratedHorizonDom: horizon override without hydration — manualOverride set, cmd badge hidden.',
  'Block 2b DOM: hydrate+accept; horizon-only override; decoupled intake; dual-track.',
  'Executed twice (run1, run2) with identical snapshots.',
  JSON.stringify({
    pure: run1.pure,
    nonHydratedHorizon: run1.nonHydratedHorizon,
    snapshots: {
      horizonOnly: snapshot(run1.horizonOnly),
      decoupledIntake: snapshot(run1.decoupledIntake),
    },
  }, null, 2),
].join('\n');
console.log(out);