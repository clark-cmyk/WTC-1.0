# BTC Basis DIG Layer — Build Plan

**Project:** WTC-1.0 (Whinfell Transmission Control)  
**Target:** `btc-basis.html` (BTC Basis DIG Page for Benaiah)  
**Role:** Build (Planning, Review, Master Plan)  
**Date:** 2026-07-16  
**Status:** In progress — btc-basis.html wired to real data/nodes/btc_basis.json; historical from 2020-01-01; data structure assessed and generator fixed.

---

## Current Status (Honest Assessment)

**What exists and works**

- `wtc_1.0.html` + `css/01_console.css` + `js/02_core.js` form a functional Risk Curve (RCV tab) with ARK loading from `data/hydration/latest.json`.
- Real basis data pipeline now produces `data/nodes/btc_basis.json` with:
  - history: 1609 daily records starting 2020-01-01 (spot time series from barchart ^BTCUSD)
  - current: latest spot/futures/basis_pct from basiswatch overlay
  - quartiles (computed, though basis history sparse)
- `btc-basis.html` wired to load real `data/nodes/btc_basis.json` (adapted for its 3-curve view + uses history for charts).
- `documentation/DIG_PAGE_TEMPLATE.md` is committed.
- `btc-basis.html` has charts, sections, A prompts, theme.

**What is partially built or stubbed**

- `btc-basis.html` has chart modules and basic structure but may not yet fully match the exact 3-chart + sidebar + quartile table requirements from DIG_PAGE_TEMPLATE.md.
- `data/nodes/btc_basis.json` provides real numeric data but the page may still rely on partial/hardcoded DIG fields (core_inputs, trades, action_bias, transmissions, etc. not fully wired from ARK yet).
- `.dig-layer` placeholders in main console still non-functional.
- `BTCBasis` in `latest.json` remains SCAN-layer only (separate from new `data/nodes/` payload).

**What is not built**

- No navigation from Risk Curve `BTCBasis` panel (or BAS tab) in `wtc_1.0.html` to `btc-basis.html`.
- No back-link integration or deep linking from console.
- No formal data contract loader in ARK/js for rich DIG payload (page not consuming full `core_inputs` etc. from pipeline).
- Agent skills / Lord-Prompts exist in `documentation/` but integration with DIG page prompt "A" buttons is unclear.
- `modules/02_basis.js` still empty.
- No UI tests for the DIG page.
- Full layered architecture (Abraham in browser, strict Lords) still aspirational.

**Bottom line:**  
`btc-basis.html` now wires to real `data/nodes/btc_basis.json`.

**Assessment of btc_basis.json structure for correct data:**
- Good overall structure for the node: node, timestamp, current (date/spot/futures/basis_dollar/basis_pct), history array of time series objects, quartiles per lookback, meta.
- Historical enforced from 2020-01-01 (1609 records: spot from barchart ^BTCUSD filtered >=2020; futures/basis_pct from latest basiswatch overlay on most recent).
- Captures correct BTC evolution (spot from ~7.2k in 2020-01-01 to current ~63k).
- Limitation: No full historical basis_pct series available in source data (basiswatch provides current curve snapshot across contracts). Quartiles reflect the available basis values. Suitable for spot history in charts + current basis in snapshots.
- Page now consumes it (with adaptation for its 3-curve model).

---

## TODO List — BTC Basis DIG Page (`btc-basis.html`)

Focused exclusively on delivering a working, integrated BTC Basis DIG page.

### Completed / In Progress (as of 2026-07-16)

- [x] Create `btc-basis.html` (evolved; has charts, back button, theme).
- [x] Data pipeline + loader fixed for BTC historical from 2020-01-01.
- [x] `data/nodes/btc_basis.json` assessed and updated (1609 recs, correct start date, structure supports current + history).
- [x] Wire `btc-basis.html` to real `data/nodes/btc_basis.json` (async fetch, adapts to 3 curves, uses history for chart spot series).
- [x] Formalize **DIG_PAGE_TEMPLATE.md** (committed).

### High Priority (Blocking integration)

1. Implement navigation from the Risk Curve `BTCBasis` panel (and BAS tab) in `wtc_1.0.html` to open `btc-basis.html`.
2. Align `btc-basis.html` more closely to DIG_PAGE_TEMPLATE.md (refine hero if needed, ensure snapshot/ quartile tables match exact fields, subtitles).
3. Enhance for richer data: extend json or page to include core_inputs, trades, transmissions etc from contract.
4. Align "A" buttons and prompt generation to agent skills / Lord-Prompts.

### Data & Payload

5. `data/nodes/btc_basis.json` assessed: 
   - Structure: solid for node (node/timestamp/current/history[]/quartiles{per period}/meta).
   - Historical: now 1609 recs starting exactly 2020-01-01 (spot from barchart, latest overlay basis/futures from basiswatch).
   - Limitation noted: full basis time series not available in sources (only current basis_pct); quartiles use snapshot values. History captures correct BTC price evolution from ~7k (2020) to current. Good enough for chart spot series + current basis.
6. Populate/stub remaining DIG fields: core_inputs, core_trades, action_bias, chart_takeaways, transmissions etc in page or extend json.

### Template & Standards

7. (Done) DIG_PAGE_TEMPLATE.md exists — ensure `btc-basis.html` and future Lords comply.
8. Bring any remaining local agent skills / `dig_reference.md` into repo if not already.

### Content & Polish (Benaiah-specific)

9. Complete / verify all sections:
    - Hero + action bias
    - Exactly 3 chart modules per template
    - Core Inputs, Score Methodology, Trades, Cross-Node, Dig Deeper, Regime, Truth from Fact
10. Ensure the “A” button produces high-quality prompt.
11. Theme/responsiveness match + zoom safety.

### Testing & Quality

12. **Suggest / implement UI test** for `btc-basis.html`:
    - Use Playwright (project already has .mjs tests in `whinfell_pipeline/tests/`) or lightweight browser test.
    - Cover: page loads without error, back button works, charts render (canvas present), PNG/CSV/A buttons functional or at least present, sections visible, theme toggle, data values appear (spot/futures/basis), prompt copy on "A".
    - Add smoke test script (e.g. `tests/test_btc_basis_dig.mjs`) runnable via `node` or `playwright test`.
    - Goal: prevent regression on navigation and rendering.

### Cleanup / Technical Debt (scoped)

13. Decide fate of empty `modules/02_basis.js`.
14. Ensure graceful degradation when rich data missing.
15. Clean any remaining duplicate files (zarchive, old deep_dive.html).

---

## Recommended Plan (for Abraham)

This plan is designed to be executed primarily by editing files directly (browser + local edits). Keep scope strictly to the BTC Basis DIG page.

### Phase 0: Alignment (Quick)
- Review current `btc-basis.html` against `documentation/DIG_PAGE_TEMPLATE.md`.
- Confirm target data source (`data/nodes/btc_basis.json` + any ARK extension).
- Agree on data contract shape.

### Phase 1: Navigation & Wiring (High Priority)
1. Add click handler / DIG button in `wtc_1.0.html` Risk Curve BTCBasis panel (and BAS tab) to open `btc-basis.html`.
2. Ensure back button in `btc-basis.html` reliably returns to `wtc_1.0.html`.
3. Add lightweight loader (or extend ARK) so page can read real data from `data/nodes/btc_basis.json` (or richer DIG payload).

### Phase 2: Template Alignment + Content
- Align `btc-basis.html` to DIG_PAGE_TEMPLATE.md (ensure exactly 3 chart modules with required header/sidebar/footer + quartile table).
- Populate or stub missing sections using real basis data where possible:
  - Hero, Core Inputs, Trades, Cross-Node Transmission, etc.
- Improve “A” buttons to use structured prompts.

### Phase 3: Polish
- Theming, responsiveness, error states, graceful degradation.
- Verify flow end-to-end in browser.

### Phase 4: Testing (New)
- **UI Test suggestion (add now):** Create a simple Playwright test (leverage existing `whinfell_pipeline/tests/` pattern with .mjs).
  - Recommended file: `whinfell_pipeline/tests/test_btc_basis_dig.mjs` (or `tests/ui/test_btc_dig.js`).
  - Test cases:
    - Page loads successfully (`btc-basis.html`).
    - Back button navigates correctly.
    - At least 3 chart canvases present and Chart.js initialized.
    - Key values (spot, basis %) visible.
    - "A" button(s) copy text to clipboard.
    - PNG/CSV buttons exist (or trigger without crash).
    - Theme toggle works.
    - No console errors on load.
  - Run command example: `npx playwright test tests/test_btc_basis_dig.mjs --headed` or headless.
  - Add to CI later if project adopts full Playwright.
- This prevents regressions on integration and rendering.

### Phase 5: Handoff
- Commit `btc-basis.html`, any data updates, and UI test.
- Document data contract.
- Update this plan + hand off to Abraham for other Lords.

### Guiding Principles
- Prioritize **navigation + template compliance + test** now that data + skeleton exist.
- Use real basis data.
- Placeholders OK but explicit.
- Goal: solid reference for Benaiah DIG.

---

**Next Action Recommendation:**  
- Abraham: wire navigation from wtc_1.0.html Risk Curve to btc-basis.html.
- Test the real data wiring (open btc-basis.html locally, check charts use 2020+ history).
- Add UI test as suggested.
- Assess/extend json for multi-curve rich fields if needed for other sections.

This document is the master reference for the BTC Basis DIG effort. Update it after each milestone.
