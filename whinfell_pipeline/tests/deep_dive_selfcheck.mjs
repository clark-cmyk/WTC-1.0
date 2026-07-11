#!/usr/bin/env node
/** Full self-check against production checklist for Transmission Ladder Deep Dive */
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const REPO = process.env.WHINFELL_REPO || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const htmlPath = path.join(REPO, '08_Deliverables/whinfell-transmission-ladder-deep-dive.html');
const url = 'file://' + htmlPath;

const BAD_PATTERNS = [
  /EXPORTPRINT/i,
  /\*\*CHOSEN\*\*/i,
  /\*\*NOT NOW\*\*/i,
  /\*\*FUTURE\*\*/i,
  /\| TRADE \|/i,
  /\|---\|/i,
  /console state/i,
  /Fragile Risk-OnEXPORT/i,
  /STAGE 1\*\*/i,
  /Expand for evidence/i,
  /Ranked bottleneck → desk consequence1/i,
  /####/,
  /\*\*/,
];

function section(name, items) {
  return { name, items, pass: items.every((i) => i.pass) };
}

const browser = await chromium.launch();
const results = [];

for (const [label, vp] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
  const page = await browser.newPage({ viewport: vp });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForSelector('.decision-grid .d-tile', { timeout: 8000 });

  const data = await page.evaluate((badPatterns) => {
    const text = document.body.innerText;
    const bad = badPatterns.filter((p) => new RegExp(p, 'i').test(text));

    const tiles = [...document.querySelectorAll('.d-tile')].map((t) => ({
      label: t.querySelector('.d-label')?.textContent?.trim(),
      value: t.querySelector('.d-value')?.textContent?.trim(),
    }));

    const regimeTile = document.querySelector('.regime-tile .d-value');
    const regimeStyle = regimeTile ? getComputedStyle(regimeTile) : null;

    const weakest = tiles.find((t) => t.label === 'Weakest link')?.value || '';

    const chinaDecisionTiles = [...document.querySelectorAll('#decisionBandChina .d-tile')].map((t) => ({
      label: t.querySelector('.d-label')?.textContent?.trim(),
      value: t.querySelector('.d-value')?.textContent?.trim(),
    }));

    const stageCards = [...document.querySelectorAll('.stage-card')].map((c) => ({
      num: c.querySelector('.stage-num')?.textContent?.trim(),
      title: c.querySelector('.stage-title')?.textContent?.trim(),
      sub: c.querySelector('.stage-sub')?.textContent?.trim(),
      stageId: c.getAttribute('data-stage-id'),
      chips: [...c.querySelectorAll('.stage-chips .chip')].map((x) => x.textContent?.trim()),
      facts: [...c.querySelectorAll('.fact')].map((f) => ({
        tag: f.querySelector('.fact-tag')?.textContent?.trim(),
        text: f.querySelector('.fact-text')?.textContent?.trim(),
        trigger: f.classList.contains('trigger-fact'),
      })),
      hasChartBlock: !!c.querySelector('.ladder-stage-chart'),
    }));

    const failRows = [...document.querySelectorAll('.fail-row')].map((r) => ({
      rank: r.querySelector('.fail-rank')?.textContent?.trim(),
      name: r.querySelector('.fail-name')?.textContent?.trim(),
      score: r.querySelector('.fail-score-label')?.textContent?.trim(),
      line: r.querySelector('.fail-consequence')?.textContent?.trim(),
      rankRect: r.querySelector('.fail-rank')?.getBoundingClientRect(),
      nameRect: r.querySelector('.fail-name')?.getBoundingClientRect(),
    }));

    const panels = ['panelBtc', 'panelEth'].map((id) => {
      const p = document.getElementById(id);
      return {
        id,
        hasPosture: !!p?.querySelector('.posture-tag'),
        hasStance: !!p?.querySelector('.stance-block'),
        hasYes: !!p?.querySelector('.yes-label'),
        hasNo: !!p?.querySelector('.no-label'),
        hasAttrib: !!p?.querySelector('.attrib-chip'),
        h3Count: p?.querySelectorAll('h3').length || 0,
        ulCount: p?.querySelectorAll('ul').length || 0,
        hasMenu: !!p?.querySelector('.trade-table'),
        menuRows: p?.querySelectorAll('.trade-table tbody tr').length || 0,
        headers: [...(p?.querySelectorAll('.trade-table thead th') || [])].map((h) => h.textContent?.trim()),
      };
    });

    const sectionOrder = [...document.querySelectorAll('section')].map((s) => s.id);
    const playbook = {
      cards: document.querySelectorAll('.play-card').length,
      scenarioRows: document.querySelectorAll('.scenario-row').length,
      bandSegs: document.querySelectorAll('.band-scale-track .band-seg').length,
      playTitles: [...document.querySelectorAll('.play-title')].map((h) => h.textContent?.trim()),
      h3Count: document.querySelectorAll('h3').length,
      ulCount: document.querySelectorAll('ul').length,
      liCount: document.querySelectorAll('li').length,
    };

    const triggerFirst = (() => {
      const card = document.querySelector('.stage-card');
      if (!card) return false;
      const first = card.querySelector('.stage-facts > .fact');
      return first?.classList.contains('trigger-fact');
    })();

    const decisionBand = document.getElementById('decisionBand');
    const bandRect = decisionBand?.getBoundingClientRect();
    const regimeTileEl = document.querySelector('.regime-tile');
    const weakestTileEl = document.querySelector('.weakest-tile');

    const overflowX = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;

    return {
      bad,
      tiles,
      regimeFontSize: regimeStyle?.fontSize,
      regimeFontWeight: regimeStyle?.fontWeight,
      weakest,
      stageCount: stageCards.length,
      stageCards,
      failRows,
      panels,
      sectionOrder,
      playbook,
      regimeBeforeWeakest: regimeTileEl && weakestTileEl ? regimeTileEl.getBoundingClientRect().left <= weakestTileEl.getBoundingClientRect().left : false,
      primaryTag: document.querySelector('.fail-primary-tag')?.textContent?.trim(),
      overflowX,
      hasThemeBtn: !!document.getElementById('btnTheme'),
      hasPrintBtn: !!document.getElementById('btnPrint'),
      pageTitle: document.querySelector('.page-title')?.textContent?.trim(),
      bodyText: text,
      statusPillCount: document.querySelectorAll('.status-pill').length,
      triggerFirst: triggerFirst,
      mathStageCards: document.querySelectorAll('.math-stage-card').length,
      compTables: document.querySelectorAll('.comp-table').length,
      hzCompare: document.querySelectorAll('.hz-cmp').length,
      methodCard: !!document.getElementById('methodCard')?.textContent?.trim(),
      mathStageTexts: [...document.querySelectorAll('.math-stage-card')].map((c) => ({
        id: c.id,
        hasWeightedTotal: c.textContent.includes('Weighted total'),
        hasFormula: c.textContent.includes('Score ='),
        hasHorizon: c.textContent.includes('30D') && c.textContent.includes('1Y'),
        rows: c.querySelectorAll('.comp-table tbody tr').length,
      })),
      strongestTags: document.querySelectorAll('strong').length,
      detailsCount: document.querySelectorAll('details').length,
      chartBlocks: document.querySelectorAll('section.ladder-stage-chart').length,
      chartKickers: document.querySelectorAll('.ladder-stage-chart__kicker').length,
      chartActionRows: document.querySelectorAll('[data-chart-actions]').length,
      chartNotes: document.querySelectorAll('[data-chart-note]').length,
      chartHrefs: [...document.querySelectorAll('.ladder-chart-btn')].map((a) => ({
        href: a.getAttribute('href'),
        blank: a.getAttribute('target') === '_blank',
        rel: a.getAttribute('rel'),
        label: a.querySelector('.ladder-chart-btn__label')?.textContent?.trim(),
        badge: a.querySelector('.ladder-chart-btn__badge')?.textContent?.trim(),
      })),
      chinaDecisionTiles,
      chinaHandicapLine: document.querySelector('.china-handicap-line')?.textContent?.trim() || '',
      chinaStageFactsText: [...document.querySelectorAll('#chinaStageList .stage-card')].map((c) => c.textContent || ''),
      globalStageCount: document.querySelectorAll('#stageList .stage-card').length,
      chinaStageCount: document.querySelectorAll('#chinaStageList .stage-card').length,
      ladderTrackToggle: document.querySelectorAll('.ladder-track-btn').length,
      ladderCols: document.querySelectorAll('.ladder-track-col').length,
    };
  }, BAD_PATTERNS.map(String));

  const text = data.bodyText;

  const failCollision = data.failRows.some((r) => {
    if (!r.rankRect || !r.nameRect) return true;
    return Math.abs(r.rankRect.right - r.nameRect.left) > 2 && r.nameRect.left < r.rankRect.right - 5;
  });

  const stageNames = [
    'Liquidity & Rates',
    'Credit Confirmation',
    'Equity Breadth',
    'High-Beta / BTC',
    'Basis & Term Structure',
  ];

  const chinaStageNames = [
    'Liquidity & Rates',
    'Credit Confirmation',
    'Equity Breadth',
    'High-Beta / China Cyclical Transmission',
    'Basis & Term Structure',
  ];

  const stageIds = ['liquidity', 'credit', 'breadth', 'highbeta', 'basis'];

  const globalStageCards = data.stageCards.filter((_, i) => i < 5);
  const chinaStageCards = data.stageCards.filter((_, i) => i >= 5);

  const sections = [
    section('1. Header and summary band', [
      { id: 'title-clean', pass: data.pageTitle === 'Deep Dive · Daily Regime Note' && !/[#*]/.test(data.pageTitle) },
      { id: 'timestamp-own', pass: data.tiles.some((t) => t.label === 'As of' && t.value && t.value.length > 5) },
      { id: 'regime-dominant', pass: data.tiles.some((t) => t.label === 'Regime' && t.value === 'Fragile Risk-On') && parseInt(data.regimeFontSize, 10) >= 14 },
      { id: 'no-exportprint', pass: data.bad.length === 0 && !data.hasPrintBtn },
      { id: 'separate-containers', pass: data.tiles.length === 6 },
      { id: 'weakest-format', pass: /Liquidity & Rates · \d+ \/ 100/.test(data.weakest) },
      { id: 'weakest-is-liquidity', pass: data.weakest.startsWith('Liquidity & Rates') },
      { id: 'top-answers', pass: ['Regime', 'Weakest link', 'BTC posture', 'ETH posture'].every((l) => data.tiles.some((t) => t.label === l)) },
    ]),
    section('2. Text collision', [
      { id: 'no-bad-patterns', pass: data.bad.length === 0 },
      { id: 'fail-separate', pass: data.failRows.length === 3 && !failCollision },
      { id: 'stages-structured', pass: data.stageCards.every((s) => s.num && s.title && s.facts.length === 3) },
    ]),
    section('3. Artifacts', [
      { id: 'no-markdown', pass: !/####|\*\*/.test(text) },
      { id: 'no-print', pass: !data.hasPrintBtn },
    ]),
    section('4. Ladder', [
      { id: 'dual-track', pass: data.ladderTrackToggle === 3 && data.ladderCols === 2 },
      { id: 'ten-stages-both', pass: data.stageCount === 10 && data.globalStageCount === 5 && data.chinaStageCount === 5 },
      { id: 'stage-names', pass: stageNames.every((n, i) => globalStageCards[i]?.title === n) },
      { id: 'stage-ids', pass: stageIds.every((id, i) => globalStageCards[i]?.stageId === id) },
      { id: 'chips', pass: globalStageCards.every((s) => s.chips.length >= 2) },
      { id: 'trigger-emphasis', pass: globalStageCards.every((s) => s.facts.find((f) => f.tag === 'Trigger')?.trigger) },
      { id: 'trigger-first', pass: data.triggerFirst },
      { id: 'chart-on-cards', pass: globalStageCards.every((s) => s.hasChartBlock) },
    ]),
    section('4c. China ladder overlay', [
      { id: 'china-stage-names', pass: chinaStageNames.every((n, i) => chinaStageCards[i]?.title === n) },
      { id: 'china-stage-ids', pass: stageIds.every((id, i) => chinaStageCards[i]?.stageId === id) },
      { id: 'china-final-adj-label', pass: data.chinaDecisionTiles.some((t) => t.label === 'China final (adj.)' && /Impaired|Mixed \/ Fragile|Constructive|Strong/.test(t.value || '')) },
      { id: 'china-sq3-policy-label', pass: data.chinaDecisionTiles.some((t) => t.label === 'SQ3 policy' && /Mixed \/ Fragile/.test(t.value || '')) },
      { id: 'china-ladder-raw-label', pass: data.chinaDecisionTiles.some((t) => t.label === 'Ladder raw') },
      { id: 'china-desk-meaning', pass: data.chinaDecisionTiles.some((t) => t.label === 'Desk meaning' && (t.value || '').length > 8) },
      { id: 'china-handicap-line', pass: /Ladder \d+ × SQ3/.test(data.chinaHandicapLine) && /Final \d+/.test(data.chinaHandicapLine) },
      { id: 'china-weakest-composite', pass: data.chinaDecisionTiles.some((t) => t.label === 'China weakest' && t.value?.startsWith('Liquidity & Rates')) },
      { id: 'china-no-btc-copy', pass: !data.chinaStageFactsText.some((t) => /IBIT|QQQ|BTC beta/i.test(t)) },
      { id: 'china-has-proxies', pass: data.chinaStageFactsText.some((t) => /CSI300|HSTECH|KHYB|2829|Copper|iron ore/i.test(t)) },
      { id: 'china-chart-blocks', pass: chinaStageCards.every((s) => s.hasChartBlock) },
    ]),
    section('4a. Chart access', [
      { id: 'chart-blocks', pass: data.chartBlocks === 10 },
      { id: 'chart-kickers', pass: data.chartKickers === 10 },
      { id: 'chart-action-rows', pass: data.chartActionRows === 10 },
      { id: 'chart-notes', pass: data.chartNotes === 10 },
      {
        id: 'chart-hrefs',
        pass: data.chartHrefs.length >= 6 && data.chartHrefs.every((h) => h.href && h.href.indexOf('http') === 0 && h.blank && h.rel === 'noopener noreferrer' && h.label && h.badge),
      },
      { id: 'chart-barchart-primary', pass: data.chartHrefs.filter((h) => h.label === 'View Chart' && h.badge === 'Barchart').length >= 1 },
      {
        id: 'chart-desk-wiring',
        pass: data.chartHrefs.some((h) => h.href.includes('USGG2Y10Y'))
          && data.chartHrefs.some((h) => h.href.includes('spreads'))
          && data.chartHrefs.some((h) => h.href.includes('major-commodities')),
      },
    ]),
    section('4b. Stage math', [
      { id: 'math-stage-cards', pass: data.mathStageCards === 5 },
      { id: 'comp-tables', pass: data.compTables === 5 },
      { id: 'hz-compare', pass: data.hzCompare === 20 },
      { id: 'methodology', pass: data.methodCard },
      { id: 'all-math-complete', pass: data.mathStageTexts.length === 5 && data.mathStageTexts.every((m) => m.hasWeightedTotal && m.hasFormula && m.hasHorizon && m.rows === 5) },
      { id: 'no-strong-tags', pass: data.strongestTags === 0 },
      { id: 'no-details', pass: data.detailsCount === 0 },
    ]),
    section('5. Failure points', [
      { id: 'ranked-rows', pass: data.failRows.length === 3 },
      { id: 'rank-separate', pass: data.failRows.every((r) => r.rank && r.name && r.rank !== r.name) },
      { id: 'primary-liquidity', pass: data.failRows[0]?.name === 'Liquidity & Rates' },
    ]),
    section('6. BTC/ETH', [
      { id: 'parallel-panels', pass: data.panels.every((p) => p.hasPosture && p.hasStance && p.hasYes && p.hasNo && p.hasAttrib && p.hasMenu) },
      { id: 'menu-rows', pass: data.panels.every((p) => p.menuRows === 6) },
      { id: 'no-h3-markdown', pass: data.panels.every((p) => p.h3Count === 0) },
      { id: 'no-ul-lists', pass: data.panels.every((p) => p.ulCount === 0) },
    ]),
    section('7. Trade menu', [
      { id: 'schema', pass: data.panels.every((p) => JSON.stringify(p.headers) === JSON.stringify(['Trade', 'Setup', 'Status', 'Sizing'])) },
      { id: 'status-pills', pass: data.statusPillCount >= 12 },
    ]),
    section('8. Playbook', [
      { id: 'two-cards', pass: data.playbook.cards === 2 },
      { id: 'scenario-rows', pass: data.playbook.scenarioRows >= 8 },
      { id: 'band-scale', pass: data.playbook.bandSegs === 4 },
      { id: 'no-playbook-h3', pass: data.playbook.h3Count === 0 },
    ]),
    section('3b. No markdown UI', [
      { id: 'no-page-h3', pass: data.playbook.h3Count === 0 },
      { id: 'no-page-ul', pass: data.playbook.ulCount === 0 },
      { id: 'no-page-li', pass: data.playbook.liCount === 0 },
    ]),
    section('9. IA order', [
      { id: 'section-order', pass: JSON.stringify(data.sectionOrder) === JSON.stringify(['ladder', 'scoring', 'weak', 'crypto', 'playbook']) },
      { id: 'regime-first', pass: data.regimeBeforeWeakest },
      { id: 'primary-tag', pass: data.primaryTag === 'Primary bottleneck' },
    ]),
    section('10. Mobile', [
      { id: 'no-overflow', pass: !data.overflowX },
    ]),
  ];

  const overall = sections.every((s) => s.pass);
  results.push({ label, overall, sections });
  await page.close();
}

await browser.close();

let allPass = true;
for (const r of results) {
  console.log(`\n=== ${r.label.toUpperCase()} === ${r.overall ? 'PASS' : 'FAIL'}`);
  for (const s of r.sections) {
    const mark = s.pass ? 'PASS' : 'FAIL';
    console.log(`  [${mark}] ${s.name}`);
    if (!s.pass) {
      allPass = false;
      for (const item of s.items.filter((i) => !i.pass)) {
        console.log(`    ✗ ${item.id}`);
      }
    }
  }
}

console.log(`\nOVERALL: ${allPass ? 'PASS' : 'FAIL'}`);
process.exit(allPass ? 0 : 1);