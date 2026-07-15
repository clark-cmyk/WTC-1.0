# BTC Basis DIG Layer — Build Plan

**Project:** WTC-1.0 (Whinfell Transmission Control)  
**Target:** `btc-basis.html` (BTC Basis DIG Page for Benaiah)  
**Role:** Build (Planning, Review, Master Plan)  
**Date:** 2026-07-15  
**Status:** Planning phase — execution primarily by Abraham in browser

---

## Current Status (Honest Assessment)

**What exists and works (Scan Layer)**

- `wtc_1.0.html` + `css/01_console.css` + `js/02_core.js` form a functional Risk Curve (RCV tab).
- ARK can load data from `data/hydration/latest.json` (including a basic `BTCBasis` node) or fall back cleanly.
- Risk Curve panels display score, status, quartile, description, and basic commentary.
- Hovering a panel reveals a basic SCAN layer with additional metadata.
- Global and per-panel “A” buttons exist and can copy prompts.
- Some real basis-related data exists in the repo (e.g. `data/downloads/wtm_basiswatch_BTC_*.csv` files containing spot, forward curves, and basis calculations).

**What is partially built or stubbed**

- Placeholder `.dig-layer` divs exist inside the Risk Curve panels but are non-functional.
- A standalone prototype for a BTC Basis deep dive page exists locally (`btc_basis_deep_dive.html`). It contains a more complete structure (hero, chart section, inputs, trades, cross-node transmission, regime, Truth from Fact, etc.).
- The current `BTCBasis` node in `latest.json` only contains flat SCAN-layer fields. It does **not** yet contain the richer DIG-layer payload the prototype expects (e.g. `core_inputs`, `core_trades`, `action_bias`, `chart_takeaways`, `outbound_transmission`, `truth_real`, etc.).

**What is not built**

- No navigation from the Risk Curve (or BAS tab) to any DIG page. Clicking a node does not open a deep view.
- No integration between the standalone DIG prototype and the main console.
- The main HTML currently loads `js/02_core.js` plus inline scripts.
- No formal **DIG Page Template** standard committed to the repo.
- No agent skills (`.md` files) committed to the repository yet (they exist locally from this session but are not in Git).
- No `BLACKBOARD` implementation in the active JavaScript.
- `modules/02_basis.js` is empty (0 bytes).
- No data contract or hydration logic yet for rich DIG payloads.
- The full vision (browser-based Abraham as Sovereign PM + strict Lord separation + layered Scan → DIG → Iterate) is still aspirational. The current codebase is closer to the old monolithic style.

**Bottom line:**  
A visual and structural foundation for the Risk Curve exists and is usable. A more complete standalone prototype for the BTC Basis DIG page exists locally. However, **integration, navigation, data shape, template formalization, and connection to the main console are not done**. The gap between the current code and the new layered architecture is still significant.

---

## TODO List — BTC Basis DIG Page (`btc-basis.html`)

Focused exclusively on delivering a working, integrated BTC Basis DIG page.

### High Priority (Blocking integration)

1. Create `btc-basis.html` (evolve from the existing `btc_basis_deep_dive.html` prototype).
2. Implement navigation from the Risk Curve `BTCBasis` panel (and ideally the BAS tab) to `btc-basis.html`.
3. Add a reliable back link from `btc-basis.html` to the main Risk Curve view.
4. Define a minimal data contract for DIG-layer payloads (what fields a DIG page can expect from ARK or a loader).

### Data & Payload

5. Decide where rich DIG data lives (extend `BTCBasis` node, add a parallel `dig` section, or create a dedicated basis dig payload).
6. Populate (or realistically stub) the richer fields the DIG page needs: `core_inputs`, `core_trades`, `action_bias`, `chart_takeaways`, `outbound_transmission`, `inbound_dependencies`, `truth_real`, `truth_fleeting`, etc.
7. Wire the page to consume real basis data where available (especially `wtm_basiswatch_BTC_*.csv` for curves and spreads).

### Template & Standards

8. Formalize a **DIG Page Template** standard (structure, required sections, CSS approach, data expectations) so it can be reused by other Lords.
9. Bring local agent skills and `dig_reference.md` (if they exist) into the repo or document their key principles in a committed file.

### Content & Polish (Benaiah-specific)

10. Implement or stub all major sections in the DIG page:
    - Hero + status + action bias
    - Chart of the Day + takeaways
    - Core Inputs
    - Score methodology
    - Core Trades + Secondary Trades
    - Cross-Node Transmission
    - Dig Deeper links
    - Regime + Truth from Fact
11. Ensure the “A” button produces a high-quality, structured prompt suitable for Abraham/Articulate.
12. Match console theming and ensure reasonable responsiveness.

### Cleanup / Technical Debt (scoped)

13. Address the empty `modules/02_basis.js` (decide whether it is needed for this phase or can stay empty).
14. Ensure the page degrades gracefully when rich DIG data is missing.

---

## Recommended Plan (for Abraham)

This plan is designed to be executed primarily by editing files directly in the browser environment. Keep scope strictly to the BTC Basis DIG page.

### Phase 0: Alignment & Inputs (Do First)
- Confirm the local agent skills and `dig_reference.md` (or equivalent) and decide what needs to be committed or summarized into the repo.
- Review the existing `btc_basis_deep_dive.html` thoroughly as the seed.
- Agree on target filename: `btc-basis.html`.
- Define the minimal data contract (a short section or small JSON example) that DIG pages will receive.

### Phase 1: Foundation & Navigation
1. Create `btc-basis.html` by copying/adapting the current prototype.
2. Update the back button to return cleanly to `wtc_1.0.html` (Risk Curve view).
3. In `wtc_1.0.html`, add navigation so clicking the BTCBasis card (or a “DIG” affordance inside it) opens `btc-basis.html`.
4. Optionally add a secondary entry point from the BAS tab.
5. Test that the page loads and the basic structure renders (it will show many placeholders initially).

### Phase 2: Data Contract + Basic Wiring
1. Extend ARK (in `js/02_core.js`) or add a lightweight loader so the DIG page can request richer data for BTCBasis.
2. Create a starter DIG payload (can be hardcoded in JS at first) that matches the sections the prototype expects.
3. Wire the render functions in `btc-basis.html` to this data. Replace “Awaiting drone payload” text with real or realistic values derived from existing basis CSVs and the current `BTCBasis` node.
4. Lock in the score methodology text.

### Phase 3: Content Population (Benaiah)
- Work section by section:
  - Hero + action bias
  - Chart of the Day + takeaways (use curve data from the basis watch CSV)
  - Core Inputs (map actual basis signals)
  - Trades (core carry/roll + secondary)
  - Cross-node transmission (use the `adjacent` logic already present in the SCAN node as a starting point)
  - Regime and Truth from Fact
- Improve the “A” prompt generator to output structured, high-signal context.

### Phase 4: Template Formalization
- Once the page is reasonably populated, extract the repeatable patterns into a clear DIG template standard (could be a short `docs/DIG_PAGE_TEMPLATE.md` or a comment block + example).
- Document the data contract clearly so other Lords can follow the same pattern.

### Phase 5: Integration Polish & Handoff
- Ensure theming, loading states, and error handling are acceptable.
- Verify the flow: Risk Curve → BTC Basis DIG → back to Risk Curve.
- Update any local notes or the master plan with what was learned.
- Commit the new `btc-basis.html` + any supporting data contract or template docs.

### Guiding Principles for this phase
- Prioritize **integration** over perfect content.
- Use real data from the repo wherever possible (basis watch CSV is gold here).
- When data is missing, use clear placeholders rather than hiding sections.
- The goal is a working reference implementation for one Lord (Benaiah), not a complete system.

---

**Next Action Recommendation:**  
Abraham should begin with Phase 0 + Phase 1 (creating `btc-basis.html` + basic navigation).

This document is the master reference for the BTC Basis DIG effort.
