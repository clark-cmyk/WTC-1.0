#!/usr/bin/env node
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const REPO = process.env.WHINFELL_REPO || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const htmlPath = path.join(REPO, '08_Deliverables/whinfell-transmission-ladder-deep-dive.html');
const url = 'file://' + htmlPath;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForSelector('.decision-grid .d-tile', { timeout: 5000 });

const checks = await page.evaluate(() => {
  const bodyText = document.body.innerText;
  const badPatterns = [
    /EXPORTPRINT/i,
    /console state/i,
    /Fragile Risk-OnEXPORT/i,
    /STAGE 1\*\*/i,
    /Expand for evidence/i,
    /Ranked bottleneck → desk consequence1/i,
  ];
  const bad = badPatterns.filter((p) => p.test(bodyText)).map((p) => p.toString());
  const tiles = [...document.querySelectorAll('.d-tile')].map((t) => ({
    label: t.querySelector('.d-label')?.textContent,
    value: t.querySelector('.d-value')?.textContent,
  }));
  const failRanks = [...document.querySelectorAll('.fail-rank')].map((e) => e.textContent);
  const failNames = [...document.querySelectorAll('.fail-name')].map((e) => e.textContent);
  const statusPills = [...document.querySelectorAll('.status-pill')].map((e) => e.textContent);
  return {
    bad,
    tileCount: tiles.length,
    regime: tiles.find((t) => t.label === 'Regime')?.value,
    weakest: tiles.find((t) => t.label === 'Weakest link')?.value,
    stages: document.querySelectorAll('.stage-card').length,
    failRows: document.querySelectorAll('.fail-row').length,
    failRanks,
    failNames,
    tradeRows: document.querySelectorAll('.trade-table tbody tr').length,
    tables: document.querySelectorAll('.trade-table').length,
    statusPills: statusPills.slice(0, 6),
    themeToggle: document.getElementById('btnTheme')?.textContent,
  };
});

console.log(JSON.stringify(checks, null, 2));
const failed = checks.bad.length || checks.tileCount !== 6 || checks.stages !== 5 || checks.failRows !== 3 || checks.tables !== 2 || checks.tradeRows !== 12;
process.exit(failed ? 1 : 0);