#!/usr/bin/env node
/** Headless Phase 2 cockpit: RV chart, focus, compare, rail navigation. */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML_PATH = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const CHINA_MODELS_JS = path.join(REPO, '08_Deliverables/desk_china_ladder_models.js');
const META_JSON = path.join(REPO, '08_Deliverables/data_dictionary_meta.json');
const COCKPIT_BUNDLE = path.join(REPO, 'whinfell_pipeline/examples/cockpit_hydration_snippet.json');
const LATEST_BUNDLE = path.join(REPO, 'data/hydration/latest.json');

const REQUIRED_FNS = [
  'drawRvBasisChart', 'toggleFocusMode', 'toggleCompareMode', 'setActiveNode',
  'renderNodeCockpitShell', 'flipNode', 'hydrateFromBundle', 'mergeNodeCockpit',
  'renderFundsFlowSponsorshipCard',
];

function extractBadgeDefault(html) {
  const m = html.match(/window\.DICTIONARY_BADGE_DEFAULT\s*=\s*(\{[\s\S]*?\});/);
  if (!m) throw new Error('DICTIONARY_BADGE_DEFAULT not found in HTML');
  return JSON.parse(m[1]);
}

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
  const probeMatch = html.match(/function runMissionSurfaceProbe[\s\S]*?window\.__rvHorizonEvidenceProbe[\s\S]*?\n\};\n/);
  if (!probeMatch) throw new Error('mission surface probes not found in HTML');
  body += '\n' + probeMatch[0];
  body += `
appState = createEmptyState();
this.__test = {
  LADDER, RV_HORIZONS, appState, hydrateFromBundle, mergeNodeCockpit,
  drawRvBasisChart, toggleFocusMode, toggleCompareMode, setActiveNode,
  renderNodeCockpitShell, flipNode, jumpToNode, activeNodeId, applyWorkspaceView,
  applyCompareSelection, buildStateFromDOM, createEmptyState, createEmptyNavigation,
  renderFundsFlowSponsorshipCard, assessHydrationImportGuard, scoreHydrationBundleQuality,
  assessHydrationSession, renderHydrationBanner, setSharedHorizon, document,
  assessCockpitHydrationMode, buildNodeGateDecisionSentence, renderNodeCoverageBanner,
  assessPostImportWorkflow, deriveGate, isMissionSurfaceNode, buildMissionImplicationChips,
  renderIngestProvenanceAudit, renderHydrationFieldLog, renderDataDictionaryAudit, buildUiAuditPayload,
  renderFlipchartState, openDictionaryAudit, buildDataDictionaryAuditRows,
  __creditMissionProbe: window.__creditMissionProbe,
  __uiAuditProbe: window.__uiAuditProbe,
  __liquidityMissionProbe: window.__liquidityMissionProbe,
  __breadthMissionProbe: window.__breadthMissionProbe,
  __highbetaMissionProbe: window.__highbetaMissionProbe,
  __rvHorizonEvidenceProbe: window.__rvHorizonEvidenceProbe,
  applyConsoleTheme, initConsoleTheme,
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
      this.id = id;
      this.value = '';
      this.textContent = '';
      this.className = '';
      this.innerHTML = '';
      this.disabled = false;
      this.dataset = {};
      this.style = {};
      this.classList = new CList();
      this.scrollTop = 0;
      this._listeners = {};
      if (id === 'cockpitRvCanvas') {
        this.parentElement = {
          getBoundingClientRect: () => ({ width: 400, height: 240 }),
        };
      }
    }
    addEventListener() {}
    setAttribute(name, value) { this[name] = value; }
    getAttribute(name) { return this[name] ?? null; }
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
    get style() { return this._style || (this._style = {}); }
    set style(v) { this._style = v; }
  }

  const els = {};
  const ctx2d = {
    setTransform() {},
    clearRect() {},
    beginPath() {},
    moveTo() {},
    lineTo() {},
    stroke() {},
    strokeRect() {},
    fillRect() {},
    fillText() {},
    measureText(text) { return { width: String(text || '').length * 5 }; },
    arc() {},
    fill() {},
    setLineDash() {},
    lineWidth: 1,
  };

  const documentElement = {
    _attrs: { 'data-theme': 'dark' },
    getAttribute(name) { return this._attrs[name] ?? null; },
    setAttribute(name, value) { this._attrs[name] = value; },
  };

  return {
    document: {
      documentElement,
      createElement() {
        return new El('');
      },
      getElementById(id) {
        if (!els[id]) els[id] = new El(id);
        const el = els[id];
        if (id === 'cockpitRvCanvas') {
          el.getContext = (type) => (type === '2d' ? ctx2d : null);
        }
        return el;
      },
      querySelectorAll(sel) {
        if (sel === '[data-node-id]') {
          return Object.values(els).filter(e => e.dataset?.nodeId);
        }
        return [];
      },
      querySelector(sel) {
        if (sel === '#cockpitShell .cockpit-main') {
          if (!els._cockpitMain) els._cockpitMain = new El('cockpitMain');
          return els._cockpitMain;
        }
        return null;
      },
    },
    localStorage: { _data: {}, getItem(k) { return this._data[k] ?? null; }, setItem(k, v) { this._data[k] = v; } },
    window: { open() {}, devicePixelRatio: 1 },
    navigator: { clipboard: { writeText: async () => {}, readText: async () => '' } },
    console, setTimeout, clearTimeout, Date, JSON, Math, Number, parseInt, parseFloat, Array, Object, Error,
    _els: els,
  };
}

function seedCockpitDom(t) {
  const ids = [
    'nodeRail', 'cockpitShell', 'cockpitChartTitle', 'cockpitChartSubtitle',
    'cockpitHorizonRow', 'cockpitHorizonPills', 'cockpitRvCanvas', 'cockpitChartPlaceholder',
    'basisTacticalBanner', 'basisTacticalSentence', 'basisTacticalSuffix', 'basisSummaryStrip',
    'basisReadingValue', 'basisReadingLabel', 'basisStanceRow', 'basisTradeRow',
    'cockpitChartValue', 'cockpitChartRichness', 'cockpitChartPct',
    'cockpitDecisionRail', 'cockpitDetailBand', 'cockpitFocusLayer',
    'cockpitCompareLayer', 'btnHeresWhy', 'btnCompareMode', 'nodeCockpitZone',
    'legacyConsoleZone', 'btnWorkspaceToggle',
    'hydrationBanner', 'hydrationBannerTitle', 'hydrationBannerBody',
    'btnHydrationBannerImport', 'btnHydrationBannerDismiss', 'cockpitChartCanvas',
    'whinfellScore', 'transmissionState', 'regimeTag', 'grossA', 'grossB',
    'cmdFreshnessSubCluster', 'cmdFreshnessMeta', 'cmdFreshnessDot', 'cmdFreshnessCluster', 'cmdFreshness',
    'nodeCoverageBanner', 'postImportWorkflow', 'postImportSteps', 'sessionReadyChip', 'commandBar',
    'cmdWhinfellScore', 'cmdScoreZone', 'txHealthValue', 'txHealthMeta', 'cmdTxState', 'cmdRegime',
    'cmdSq3Score', 'cmdSq3Band', 'cmdGrossRisk', 'cmdGrossPosture', 'cmdHydrationBadge', 'gateText',
    'chinaPolicyStrength', 'chinaStateImpulse', 'chinaGrowthImpulse', 'chinaRegimeTag',
    'gateChip', 'gateHelperText', 'shockText', 'shockMeta', 'scoreCard', 'cmdGlobalCluster', 'cmdChinaCluster',
    'btnTheme',
    'gateExplainList', 'gateUnlockList', 'gateHealthSub', 'gateDetailPanel', 'sq3ComputedDisplay', 'sq3BandChip',
    'scoreZoneChip', 'gateStatusChip', 'txChip', 'grossTotal', 'grossMmHint', 'postureWarning',
  ];
  ids.forEach(id => t.document.getElementById(id));
  const banner = t.document.getElementById('basisTacticalBanner');
  banner._eyebrowEl = { textContent: '', className: 'basis-tactical-eyebrow' };
  banner.querySelector = (sel) => (sel === '.basis-tactical-eyebrow' ? banner._eyebrowEl : null);
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

function hydrateCockpit(t, bundle) {
  seedCockpitDom(t);
  t.appState.ui = t.appState.ui || {};
  t.appState.ui.workspaceView = 'cockpit';
  t.hydrateFromBundle(bundle);
}

function testDrawRvBasisChart(t, bundle) {
  hydrateCockpit(t, bundle);
  const cockpit = t.mergeNodeCockpit('basis', t.buildStateFromDOM());
  const canvas = t.document.getElementById('cockpitRvCanvas');
  const result = t.drawRvBasisChart(cockpit, canvas);
  if (!result.drew) throw new Error('drawRvBasisChart did not draw');
  if (result.pointCount !== 5) throw new Error(`expected 5 horizon points, got ${result.pointCount}`);
  t.renderNodeCockpitShell(t.buildStateFromDOM());
  const title = t.document.getElementById('cockpitChartTitle').textContent;
  if (!title || title === '—') throw new Error(`chart title not set: ${title}`);
  return { drew: true, pointCount: result.pointCount, title };
}

function testFocusMode(t, bundle) {
  hydrateCockpit(t, bundle);
  t.toggleFocusMode(true);
  if (!t.appState.navigation.focus_mode) throw new Error('focus_mode not set');
  const layer = t.document.getElementById('cockpitFocusLayer');
  if (layer.classList.contains('zone-hidden')) throw new Error('focus layer hidden when active');
  if (!layer.innerHTML.includes('Thesis')) throw new Error('focus layer missing thesis block');
  t.toggleFocusMode(false);
  if (t.appState.navigation.focus_mode) throw new Error('focus_mode not cleared');
  return { focusToggle: true, thesisRendered: true };
}

function testCompareMode(t, bundle) {
  hydrateCockpit(t, bundle);
  t.setActiveNode('credit');
  t.toggleCompareMode(true);
  if (t.appState.navigation.view_mode !== 'compare') throw new Error('view_mode not compare');
  t.applyCompareSelection('liquidity');
  const ids = t.appState.navigation.compare_node_ids || [];
  if (!ids.includes('credit') || !ids.includes('liquidity')) {
    throw new Error(`compare ids unexpected: ${JSON.stringify(ids)}`);
  }
  const layer = t.document.getElementById('cockpitCompareLayer');
  if (layer.classList.contains('zone-hidden')) throw new Error('compare layer hidden when active');
  if (!layer.innerHTML.includes('compare-card')) throw new Error('compare cards not rendered');
  t.toggleCompareMode(false);
  if (t.appState.navigation.view_mode !== 'flip') throw new Error('view_mode not restored to flip');
  return { compareToggle: true, cardCount: (layer.innerHTML.match(/compare-card/g) || []).length };
}

function testRailNavigation(t, bundle) {
  hydrateCockpit(t, bundle);
  t.setActiveNode('highbeta');
  if (t.activeNodeId() !== 'highbeta') throw new Error(`setActiveNode failed: ${t.activeNodeId()}`);
  t.flipNode(1);
  if (t.activeNodeId() !== 'basis') throw new Error(`flipNode forward failed: ${t.activeNodeId()}`);
  t.jumpToNode('liquidity');
  if (t.activeNodeId() !== 'liquidity') throw new Error(`jumpToNode failed: ${t.activeNodeId()}`);
  t.renderNodeCockpitShell(t.buildStateFromDOM());
  const rail = t.document.getElementById('nodeRail');
  if (!rail.innerHTML.includes('node-rail-tab')) throw new Error('node rail not rendered');
  return { activeNode: t.activeNodeId(), railRendered: true };
}

function testFundsFlowCard(t, bundle) {
  hydrateCockpit(t, bundle);
  t.setActiveNode('credit');
  t.renderNodeCockpitShell(t.buildStateFromDOM());
  const decisionRail = t.document.getElementById('cockpitDecisionRail');
  if (!decisionRail.innerHTML.includes('funds-flow-card')) {
    throw new Error('funds-flow-card not rendered in decision rail when hydrated');
  }
  if (!decisionRail.innerHTML.includes('funds-flow-verdict-supportive')) {
    throw new Error('funds-flow verdict badge missing for credit supportive payload');
  }
  if (!decisionRail.innerHTML.includes('funds-flow-etf-row')) {
    throw new Error('funds-flow ETF rows missing in decision rail');
  }

  const cockpit = t.mergeNodeCockpit('credit', t.buildStateFromDOM());
  const compareHtml = t.renderFundsFlowSponsorshipCard(cockpit, { variant: 'compare' });
  if (!compareHtml.includes('funds-flow-card--compare')) {
    throw new Error('compare variant class missing from funds flow card');
  }

  t.toggleFocusMode(true);
  const focus = t.document.getElementById('cockpitFocusLayer');
  if (!focus.innerHTML.includes('funds-flow-card--expanded')) {
    throw new Error('expanded funds-flow card missing in focus layer');
  }
  t.toggleFocusMode(false);

  t.toggleCompareMode(true);
  const compareLayer = t.document.getElementById('cockpitCompareLayer');
  if (!compareLayer.innerHTML.includes('funds-flow-card--compare')) {
    throw new Error('compare funds-flow card missing in compare layer');
  }
  t.toggleCompareMode(false);

  return { fundsFlowCardRendered: true, verdict: 'supportive', variants: ['rail', 'compare', 'expanded'] };
}

function testStatePreservation(t, bundle) {
  hydrateCockpit(t, bundle);
  t.setActiveNode('breadth');
  t.setSharedHorizon('6m');
  const nodeBefore = t.activeNodeId();
  const hzBefore = t.appState.chart?.shared_horizon;
  t.toggleFocusMode(true);
  t.toggleFocusMode(false);
  if (t.activeNodeId() !== nodeBefore) throw new Error('active node lost after focus exit');
  if (t.appState.chart?.shared_horizon !== hzBefore) throw new Error('shared horizon lost after focus exit');
  t.toggleCompareMode(true);
  t.toggleCompareMode(false);
  if (t.activeNodeId() !== nodeBefore) throw new Error('active node lost after compare exit');
  return { nodePreserved: nodeBefore, horizonPreserved: hzBefore };
}

function testNodeCoverageBanner(t, bundle) {
  seedCockpitDom(t);
  t.appState.ui = t.appState.ui || {};
  t.appState.ui.workspaceView = 'cockpit';
  const degraded = t.assessCockpitHydrationMode(t.buildStateFromDOM());
  if (degraded.mode !== 'degraded') throw new Error('expected degraded mode on fresh session');
  t.hydrateFromBundle(bundle);
  const partialOrComplete = t.assessCockpitHydrationMode(t.buildStateFromDOM());
  if (!['partial', 'complete'].includes(partialOrComplete.mode)) {
    throw new Error(`expected partial/complete after hydrate, got ${partialOrComplete.mode}`);
  }
  const cockpit = t.mergeNodeCockpit('basis', t.buildStateFromDOM());
  t.renderNodeCoverageBanner(cockpit, t.buildStateFromDOM());
  const banner = t.document.getElementById('nodeCoverageBanner');
  if (banner.classList.contains('zone-hidden')) throw new Error('coverage banner should be visible');
  const gateLine = t.buildNodeGateDecisionSentence(cockpit, t.buildStateFromDOM(), t.deriveGate(t.buildStateFromDOM()));
  if (!gateLine.includes('Tight Risk') && !gateLine.includes('Blocked') && !gateLine.includes('eligible')) {
    throw new Error(`unexpected gate sentence: ${gateLine}`);
  }
  return { degraded: degraded.mode, hydrated: partialOrComplete.mode, gateLine };
}

function testHydrationBanner(t, bundle) {
  seedCockpitDom(t);
  t.appState.ui = t.appState.ui || {};
  t.appState.ui.workspaceView = 'cockpit';
  const missing = t.assessHydrationSession(t.buildStateFromDOM());
  if (missing.level !== 'missing' || !missing.showBanner) {
    throw new Error('expected missing hydration assessment on fresh session');
  }
  t.renderHydrationBanner(t.buildStateFromDOM());
  const banner = t.document.getElementById('hydrationBanner');
  if (banner.classList.contains('zone-hidden')) throw new Error('hydration banner should be visible when missing');
  t.hydrateFromBundle(bundle);
  const ok = t.assessHydrationSession(t.buildStateFromDOM());
  if (ok.level !== 'ok') throw new Error(`expected ok after hydrate, got ${ok.level}`);
  return { missingLevel: missing.level, okAfterHydrate: true };
}

function testBreadthMissionSurface(t, bundle) {
  seedCockpitDom(t);
  if (typeof t.__breadthMissionProbe !== 'function') {
    throw new Error('__breadthMissionProbe missing from headless harness');
  }
  const result = t.__breadthMissionProbe(bundle);
  if (result.error) throw new Error(result.error);

  if (!result.missionVisible) throw new Error('breadth mission banner hidden');
  if (!result.tacticalLead || result.tacticalLead === '—') {
    throw new Error(`breadth tactical lead empty: ${result.tacticalLead}`);
  }
  if (!/fair|rich|cheap/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing RV richness: ${result.tacticalLead}`);
  }
  if (!/0\.5×|eligible|blocked|neutral/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing expression/gate read: ${result.tacticalLead}`);
  }
  if (result.tacticalLead.includes('SQ3') || result.tacticalLead.includes('constraint')) {
    throw new Error(`SQ3 must not appear in lead sentence: ${result.tacticalLead}`);
  }
  if (!result.tacticalSuffix || !result.tacticalSuffix.includes('SQ3')) {
    throw new Error(`material SQ3 suffix missing: ${result.tacticalSuffix}`);
  }
  if (!result.compositeFallback) {
    throw new Error(`breadth composite fallback chip missing: ${result.chips.join(', ')}`);
  }
  if (result.gateChip !== 'Tight + China Caution') {
    throw new Error(`expected Tight + China Caution gate chip, got ${result.gateChip}`);
  }

  return {
    breadthMissionSurface: true,
    tacticalLead: result.tacticalLead,
    compositeFallbackVisible: result.compositeFallback,
    gateChipLabel: result.gateChip,
  };
}

function testHighbetaMissionSurface(t, bundle) {
  seedCockpitDom(t);
  if (typeof t.__highbetaMissionProbe !== 'function') {
    throw new Error('__highbetaMissionProbe missing from headless harness');
  }
  const result = t.__highbetaMissionProbe(bundle);
  if (result.error) throw new Error(result.error);

  if (!result.missionVisible) throw new Error('highbeta mission banner hidden');
  if (!result.tacticalLead || result.tacticalLead === '—') {
    throw new Error(`highbeta tactical lead empty: ${result.tacticalLead}`);
  }
  if (!/fair|rich|cheap/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing RV richness: ${result.tacticalLead}`);
  }
  if (!/0\.5×|eligible|blocked|neutral/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing expression/gate read: ${result.tacticalLead}`);
  }
  if (result.tacticalLead.includes('SQ3') || result.tacticalLead.includes('constraint')) {
    throw new Error(`SQ3 must not appear in lead sentence: ${result.tacticalLead}`);
  }
  if (!result.tacticalSuffix || !result.tacticalSuffix.includes('SQ3')) {
    throw new Error(`material SQ3 suffix missing: ${result.tacticalSuffix}`);
  }
  if (!result.compositeFallback) {
    throw new Error(`highbeta composite fallback chip missing: ${result.chips.join(', ')}`);
  }
  if (result.gateChip !== 'Tight + China Caution') {
    throw new Error(`expected Tight + China Caution gate chip, got ${result.gateChip}`);
  }

  return {
    highbetaMissionSurface: true,
    tacticalLead: result.tacticalLead,
    compositeFallbackVisible: result.compositeFallback,
    gateChipLabel: result.gateChip,
  };
}

function testLiquidityMissionSurface(t, bundle) {
  seedCockpitDom(t);
  if (typeof t.__liquidityMissionProbe !== 'function') {
    throw new Error('__liquidityMissionProbe missing from headless harness');
  }
  const result = t.__liquidityMissionProbe(bundle);
  if (result.error) throw new Error(result.error);

  if (!result.missionVisible) throw new Error('liquidity mission banner hidden');
  if (!result.tacticalLead || result.tacticalLead === '—') {
    throw new Error(`liquidity tactical lead empty: ${result.tacticalLead}`);
  }
  if (!/fair|rich|cheap/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing RV richness: ${result.tacticalLead}`);
  }
  if (!/0\.5×|eligible|blocked/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing gate read: ${result.tacticalLead}`);
  }
  if (result.tacticalLead.includes('SQ3') || result.tacticalLead.includes('constraint')) {
    throw new Error(`SQ3 must not appear in lead sentence: ${result.tacticalLead}`);
  }
  if (!result.tacticalSuffix || !result.tacticalSuffix.includes('SQ3')) {
    throw new Error(`material SQ3 suffix missing: ${result.tacticalSuffix}`);
  }
  if (result.compositeFallback) {
    throw new Error(`liquidity should show band chip, not composite fallback: ${result.chips.join(', ')}`);
  }
  if (result.bandChip !== 'Supportive') {
    throw new Error(`expected Supportive band chip, got ${result.bandChip}`);
  }
  if (!result.readingValue.includes('%')) {
    throw new Error(`expected pct reading, got ${result.readingValue}`);
  }
  if (result.gateChip !== 'Tight + China Caution') {
    throw new Error(`expected Tight + China Caution gate chip, got ${result.gateChip}`);
  }

  return {
    liquidityMissionSurface: true,
    tacticalLead: result.tacticalLead,
    tacticalSuffix: result.tacticalSuffix,
    readingValue: result.readingValue,
    bandChip: result.bandChip,
    gateChipLabel: result.gateChip,
    chips: result.chips,
  };
}

function testThemeToggle(t) {
  seedCockpitDom(t);
  if (typeof t.applyConsoleTheme !== 'function') {
    throw new Error('applyConsoleTheme missing from headless harness');
  }
  t.applyConsoleTheme('light');
  if (t.document.documentElement.getAttribute('data-theme') !== 'light') {
    throw new Error('light theme not applied');
  }
  if (t.document.getElementById('btnTheme').textContent !== 'Dark mode') {
    throw new Error('theme button label not updated for light mode');
  }
  t.applyConsoleTheme('dark');
  if (t.document.documentElement.getAttribute('data-theme') !== 'dark') {
    throw new Error('dark theme not applied');
  }
  return { themeToggle: true };
}

function testCreditRvHorizonFallback(t, bundle) {
  hydrateCockpit(t, bundle);
  t.setActiveNode('credit');
  if (typeof t.__rvHorizonEvidenceProbe !== 'function') {
    throw new Error('__rvHorizonEvidenceProbe missing from headless harness');
  }
  const result = t.__rvHorizonEvidenceProbe(bundle, 'credit');
  if (result.error) throw new Error(result.error);
  if (result.fallbackMode !== 'spot') {
    throw new Error(`expected spot fallback mode for credit HY OAS, got ${result.fallbackMode}`);
  }
  if (!result.spotFallbackTable) {
    throw new Error('focus horizon table missing spot-fallback class');
  }
  if (result.spotValueRepeatCount !== 1) {
    throw new Error(`spot value should appear once in table, got ${result.spotValueRepeatCount}`);
  }
  if (!result.hasSpotNote) {
    throw new Error('spot fallback explanatory note missing from focus layer');
  }
  if (result.primaryHorizon !== '3m') {
    throw new Error(`expected active 3m horizon to carry spot value, got ${result.primaryHorizon}`);
  }
  return {
    creditRvHorizonFallback: true,
    spotValueRepeatCount: result.spotValueRepeatCount,
    primaryHorizon: result.primaryHorizon,
  };
}

function testCreditMissionSurface(t, bundle) {
  seedCockpitDom(t);
  if (typeof t.__creditMissionProbe !== 'function') {
    throw new Error('__creditMissionProbe missing from headless harness');
  }
  const result = t.__creditMissionProbe(bundle);
  if (result.error) throw new Error(result.error);

  if (!result.tacticalLead || result.tacticalLead === '—') {
    throw new Error(`credit tactical lead empty: ${result.tacticalLead}`);
  }
  if (!/cheap|rich|fair/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing RV richness: ${result.tacticalLead}`);
  }
  if (!/long spread|0\.5×/i.test(result.tacticalLead)) {
    throw new Error(`tactical lead missing expression/gate cap: ${result.tacticalLead}`);
  }
  if (result.tacticalLead.includes('SQ3') || result.tacticalLead.includes('constraint')) {
    throw new Error(`SQ3 must not appear in lead sentence: ${result.tacticalLead}`);
  }
  if (!result.tacticalSuffix || !result.tacticalSuffix.includes('SQ3')) {
    throw new Error(`material SQ3 suffix missing: ${result.tacticalSuffix}`);
  }
  if (!result.compositeFallback) {
    throw new Error(`Composite fallback chip missing: ${result.chips.join(', ')}`);
  }
  if (!result.railHasHorizonNet) {
    throw new Error('horizon-net fallback missing from rail diagnostics HTML');
  }
  if (result.gateChip !== 'Tight + China Caution') {
    throw new Error(`expected Tight + China Caution gate chip, got ${result.gateChip}`);
  }

  return {
    creditMissionSurface: true,
    tacticalLead: result.tacticalLead,
    tacticalSuffix: result.tacticalSuffix,
    compositeFallbackVisible: result.compositeFallback,
    railHasHorizonNet: result.railHasHorizonNet,
    horizonNetFallbackDiagnostics: result.railHasHorizonNet ? 'horizon-net fallback' : '',
    gateChipLabel: result.gateChip,
    chips: result.chips,
  };
}

function testUiAuditProbe(t, bundle) {
  hydrateCockpit(t, bundle);
  if (typeof t.__uiAuditProbe !== 'function') {
    throw new Error('__uiAuditProbe missing from headless harness');
  }
  const result = t.__uiAuditProbe(bundle);
  if (result.error) throw new Error(result.error);
  if (result.consoleBuild !== '2.2-UX-TIPS-2026-06-30') {
    throw new Error(`unexpected console build: ${result.consoleBuild}`);
  }
  if (!result.hasFlipchartState) {
    throw new Error(`flipchart state not visible: ${result.flipPosition}`);
  }
  if (!['complete', 'partial', 'degraded'].includes(result.coverageMode)) {
    throw new Error(`invalid coverage mode: ${result.coverageMode}`);
  }
  t.renderDataDictionaryAudit(t.buildStateFromDOM());
  if (!t.document.getElementById('dataDictionaryAudit')?.innerHTML) {
    throw new Error('data dictionary audit panel empty');
  }
  return {
    uiAuditProbe: true,
    coverageMode: result.coverageMode,
    dictionaryAuditCount: result.dictionaryAuditCount,
    flipPosition: result.flipPosition,
  };
}

function testHydrationFieldLog(t, bundle) {
  hydrateCockpit(t, bundle);
  if (typeof t.renderHydrationFieldLog !== 'function') {
    throw new Error('renderHydrationFieldLog missing from headless harness');
  }
  const state = t.buildStateFromDOM();
  state.hydration = {
    ...(state.hydration || {}),
    ...(t.appState.hydration || {}),
    hydration_audit: bundle.hydration_audit || t.appState.hydration?.hydration_audit,
  };
  t.renderHydrationFieldLog(state);
  const node = t.document.getElementById('hydrationFieldLog');
  if (!node) throw new Error('hydrationFieldLog element missing');
  const audit = bundle.hydration_audit;
  if (!audit?.summary) {
    if (!node.textContent.includes('hydration_audit')) {
      throw new Error('expected hydration field log placeholder');
    }
    return { hydrationFieldLog: 'empty' };
  }
  if (!node.innerHTML.includes('hydration-field-log-table')) {
    throw new Error('hydration field log table not rendered');
  }
  if (!node.innerHTML.includes(String(audit.summary.required_ok))) {
    throw new Error('required_ok not shown in hydration field log');
  }
  return {
    hydrationFieldLog: true,
    requiredOk: audit.summary.required_ok,
    quality: audit.summary.bundle_quality_score,
    session: audit.summary.tc_session_level,
  };
}

function testIngestProvenanceAudit(t, bundle) {
  hydrateCockpit(t, bundle);
  if (typeof t.renderIngestProvenanceAudit !== 'function') {
    throw new Error('renderIngestProvenanceAudit missing from headless harness');
  }
  const state = t.buildStateFromDOM();
  state.hydration = {
    ...(state.hydration || {}),
    ...(t.appState.hydration || {}),
    ingest_provenance: bundle.ingest_provenance || t.appState.hydration?.ingest_provenance,
  };
  t.renderIngestProvenanceAudit(state);
  const node = t.document.getElementById('ingestProvenanceAudit');
  if (!node) throw new Error('ingestProvenanceAudit element missing');
  const ingest = bundle.ingest_provenance;
  if (!ingest?.staged_count) {
    if (!node.textContent.includes('ARCH-1 M3')) {
      throw new Error('expected empty ingest audit placeholder');
    }
    return { ingestAudit: 'empty' };
  }
  if (!node.innerHTML.includes('ingest-audit-table')) {
    throw new Error('ingest audit table not rendered');
  }
  if (!node.innerHTML.includes('Primary output kind:')) {
    throw new Error('primary output kind line missing from ingest audit');
  }
  return {
    ingestAudit: true,
    stagedCount: ingest.staged_count,
    primaryOutputKind: ingest.primary_output_kind || 'unknown',
  };
}

function testImportGuard(t, bundle) {
  hydrateCockpit(t, bundle);
  const healthyScore = t.scoreHydrationBundleQuality(bundle);
  const degraded = { flows_sidecar: { flows_status: 'unavailable' } };
  const guard = t.assessHydrationImportGuard(degraded, t.appState);
  if (!guard.downgrade) throw new Error('expected downgrade guard after healthy session');
  if (guard.allowed) throw new Error('downgrade import should be blocked');
  const applied = t.hydrateFromBundle(degraded, { force: false });
  if (applied !== false) throw new Error('blocked import should return false');
  if (!t.appState.hydration?.node_cockpits) throw new Error('healthy cockpits should remain after blocked import');
  const forced = t.hydrateFromBundle(degraded, { force: true });
  if (forced !== true) throw new Error('forced degraded import should succeed');
  return { healthyScore, blocked: true, forcedOk: true };
}

function runSuite(script, bundle, label) {
  return {
    label,
    chart: testDrawRvBasisChart(boot(script), bundle),
    focus: testFocusMode(boot(script), bundle),
    compare: testCompareMode(boot(script), bundle),
    navigation: testRailNavigation(boot(script), bundle),
    fundsFlow: testFundsFlowCard(boot(script), bundle),
    creditMission: testCreditMissionSurface(boot(script), bundle),
    creditRvHorizonFallback: testCreditRvHorizonFallback(boot(script), bundle),
    liquidityMission: testLiquidityMissionSurface(boot(script), bundle),
    breadthMission: testBreadthMissionSurface(boot(script), bundle),
    highbetaMission: testHighbetaMissionSurface(boot(script), bundle),
    themeToggle: testThemeToggle(boot(script), bundle),
    statePreservation: testStatePreservation(boot(script), bundle),
    importGuard: testImportGuard(boot(script), bundle),
    hydrationBanner: testHydrationBanner(boot(script), bundle),
    nodeCoverage: testNodeCoverageBanner(boot(script), bundle),
    ingestAudit: testIngestProvenanceAudit(boot(script), latestBundle),
    hydrationFieldLog: testHydrationFieldLog(boot(script), latestBundle),
    uiAudit: testUiAuditProbe(boot(script), latestBundle),
  };
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const bundle = JSON.parse(fs.readFileSync(COCKPIT_BUNDLE, 'utf8'));
const latestBundle = fs.existsSync(LATEST_BUNDLE)
  ? JSON.parse(fs.readFileSync(LATEST_BUNDLE, 'utf8'))
  : bundle;
const script = extractScript(html);

const run1 = runSuite(script, bundle, 'run1');
const run2 = runSuite(script, bundle, 'run2');

const snap = (run) => {
  const { label: _l, ...rest } = run;
  return rest;
};
if (JSON.stringify(snap(run1)) !== JSON.stringify(snap(run2))) {
  throw new Error(`run1/run2 mismatch: ${JSON.stringify({ run1: snap(run1), run2: snap(run2) })}`);
}

const out = [
  'html_headless_cockpit_ok',
  `Required functions: ${REQUIRED_FNS.join(', ')}.`,
  'Blocks: drawRvBasisChart (5 horizons), toggleFocusMode, toggleCompareMode, setActiveNode/flipNode, fundsFlowCard, creditMissionSurface.',
  'Executed twice (run1, run2) with identical snapshots.',
  JSON.stringify(run1, null, 2),
].join('\n');
console.log(out);