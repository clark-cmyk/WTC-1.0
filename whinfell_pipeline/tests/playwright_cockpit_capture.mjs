#!/usr/bin/env node
/** Verification plan step 4: Playwright keyboard drive + screenshot. */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from 'playwright';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HTML = path.join(REPO, '08_Deliverables/Whinfell_Transmission_Control.html');
const BUNDLE = path.join(REPO, 'whinfell_pipeline/examples/cockpit_hydration_snippet.json');
const SCRATCH = process.env.GROK_GOAL_SCRATCH
  || '/var/folders/qn/gdsdhg9j3f77wk7fn889zbq40000gn/T/grok-goal-9f124befa95c/implementer';

const errors = [];
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(msg.text());
});

const fileUrl = `file://${HTML}`;
await page.goto(fileUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForFunction(() => typeof window.hydrateFromBundle === 'function', null, { timeout: 30000 });

const bundle = JSON.parse(fs.readFileSync(BUNDLE, 'utf8'));
await page.evaluate((b) => {
  window.hydrateFromBundle(b);
  window.applyWorkspaceView('cockpit');
}, bundle);

await page.keyboard.press('c');
await page.waitForTimeout(300);
const compareHidden = await page.evaluate(() => document.getElementById('cockpitCompareLayer')?.classList.contains('zone-hidden'));
if (compareHidden) throw new Error('compare layer should be visible after c');

await page.keyboard.press('Escape');
await page.keyboard.press('f');
await page.waitForTimeout(300);
const focusHidden = await page.evaluate(() => document.getElementById('cockpitFocusLayer')?.classList.contains('zone-hidden'));
if (focusHidden) throw new Error('focus layer should be visible after f');

await page.keyboard.press('ArrowRight');
await page.keyboard.press('3');
const canvas = page.locator('#cockpitRvCanvas');
await canvas.waitFor({ state: 'attached', timeout: 10000 });
const box = await canvas.boundingBox();
if (!box || box.width < 50 || box.height < 50) throw new Error(`canvas bbox too small: ${JSON.stringify(box)}`);

fs.mkdirSync(SCRATCH, { recursive: true });
await page.screenshot({ path: path.join(SCRATCH, 'tc_ui_complete.png'), fullPage: false });

if (errors.length) {
  fs.writeFileSync(path.join(SCRATCH, 'playwright_console_errors.log'), errors.join('\n'));
  throw new Error(`console errors: ${errors.join('; ')}`);
}

await browser.close();
console.log('playwright_capture_ok');