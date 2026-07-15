# DIG_PAGE_TEMPLATE — Standard for All DIG Layer Pages

**Status:** Official Template (v1.0)  
**Owner:** ARK (Infrastructure)  
**Applies to:** Every DIG Layer page (Benaiah, Leviathan, Cassius, Ephraim, Hiram, etc.)

---

## 1. Purpose

This document defines the **mandatory structure, layout, behavior, and data expectations** for every DIG Layer page in WTC-1.0. All DIG pages must follow this template with minimal deviation so the system remains consistent and maintainable.

---

## 2. Page Structure (Required Order)

Every DIG page must contain the following sections, in this order:

### 2.1 Header
- Back button that returns to `wtc_1.0.html` (Risk Curve view)
- Page title (e.g., "BTC Basis — DIG Layer (Benaiah)")
- Top-right controls:
  - Global **"A" button** (Articulate for the full page)
  - Dark/Light mode toggle button

### 2.2 Hero Summary
- Large score display
- Status + Quartile (e.g., "Strong Q1")
- Short description
- Action bias / key takeaway

### 2.3 Chart Modules (Exactly 3 Charts)

Each DIG page must contain **exactly three chart modules** stacked vertically.

**Each chart module must include:**

- **Chart Header**
  - Clear title + subtitle
  - Three buttons on the right: **PNG**, **CSV**, **A** (Articulate)

- **Chart Container** (two-column layout)
  - Main chart area (minimum 420px height)
  - Right sidebar containing:
    - **Today's Snapshot** box (Spot Price, Futures Price, Basis $, Basis %)
    - Small, clean **Legend**
    - The three buttons can also live here if preferred

- **Chart Footer**
  - **Quartile Ranking** table showing:
    - 30d, 60d, 90d, 1y, 3y, Since 2020
    - Current basis value
    - Percentile rank
    - Quartile (Q1–Q4)

**Chart Requirements:**
- Must show **three lines**: Spot Price, Futures/Perp Price, and Basis (%)
- Must support **mouse hover** (bullseye) showing: Spot, Futures Price, Basis Dollars, Basis %, and Annualized Basis (both simple and industry methods where applicable)
- Must use CSS variables for theming (supports both dark and light mode)
- Must scale cleanly when the user zooms (use `rem` units)
- Must have a clean background when taking PNG screenshots

### 2.4 Additional Sections (Below Charts)

These sections must appear after the three chart modules:

- **Core Inputs / Signals**
- **Score Methodology**
- **Core Trades + Secondary Trades**
- **Cross-Node Transmission** (Outbound + Inbound)
- **Dig Deeper** (research links)
- **Regime**
- **Truth from Fact** (Real vs Fleeting)

---

## 3. Data Expectations (Data Contract)

Every DIG page should expect the following data shape from ARK or a loader:

### Required Fields (Minimum)
- `score`, `status`, `quartile`, `description`, `action_bias`
- `core_inputs` (array of signals)
- `core_trades` + `secondary_trades`
- `chart_takeaways`
- `outbound_transmission` + `inbound_dependencies`
- `regime_summary`
- `truth_real` + `truth_fleeting`
- `barchart_links` + `koyfin_links` (optional but preferred)

If rich DIG data is not yet available, the page must show clear placeholder text (e.g., “Benaiah payload pending”) instead of hiding sections.

---

## 4. Styling & Technical Rules

- Must use the same CSS variables as `wtc_1.0.html` (`--bg-card`, `--border`, `--text-primary`, `--accent`, etc.)
- All sizing must use `rem` units (not `px`) for proper zoom/scaling behavior
- Must be responsive and maintain layout integrity when zoomed
- Chart modules should follow the structure defined in `dig_reference.md`
- Hover states and transitions should feel consistent with the main console
- Buttons should use the existing `.a-btn` class for the Articulate button

---

## 5. Button Behavior

| Button | Scope       | Action |
|--------|-------------|--------|
| **A** (per chart) | Individual chart | Copies a focused, structured prompt for that chart only |
| **A** (global)    | Whole page     | Copies a comprehensive prompt covering the entire DIG page |
| **PNG**           | Per chart      | Takes a clean screenshot of just that chart (transparent or clean background) |
| **CSV**           | Per chart      | Downloads the data used in that specific chart |

---

## 6. Integration Rules

- DIG pages must be reachable from the main console (`wtc_1.0.html`)
- Clicking a node in the Risk Curve (or BAS tab) should open its corresponding DIG page
- Every DIG page must have a reliable way to return to the Risk Curve
- DIG pages should be able to load with just `ARK` + the relevant node data (self-contained where possible)

---

## 7. Ownership & Maintenance

- **Template Owner**: ARK
- **Enforcement**: Abraham is responsible for ensuring new DIG pages follow this standard
- Any deviation from this template must be explicitly approved by Abraham

---

**This template is mandatory.** All future DIG pages must follow this structure.