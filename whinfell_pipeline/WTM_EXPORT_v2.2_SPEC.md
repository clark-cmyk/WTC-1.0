# WTM EXPORT v2.2 — Node Cockpit Extension

**Status:** Locked (Phase 2)  
**Date:** June 29, 2026  
**Consumers:** Transmission Control, Whinfell Pipeline, Perplexity prompts  
**Supersedes:** WTM EXPORT v2.1 (backward-compatible — v2.1 block unchanged; v2.2 appends node cockpit blocks)

---

## Purpose

Extend the locked v2.1 handshake with **per-node cockpit blocks** so each ladder stage round-trips through research, hydration, and operator console without key drift. v2.2 is additive: parsers that only understand v2.1 continue to work on the global core.

---

## Block Structure

```
--- WTM EXPORT v2.1 ---
[Global Core]
[China SQ3]
[Signal Tracer — optional]
[Provenance & Freshness]
[CHINA LADDER EXPORT v1.1 — optional]

--- NODE COCKPIT: {Display Name} ---
[Node Cockpit Fields]
(repeated × 5 nodes, fixed order)

--- NODE COCKPIT: Basis & Term Structure ---
...
```

**Termination:** Each `NODE COCKPIT` block ends at the next `--- NODE COCKPIT:` header, `--- WTM EXPORT`, or end of text.

**Node order (fixed):** Liquidity & Rates · Credit Confirmation · Equity Breadth · High-Beta / BTC · Basis & Term Structure

---

## Field Catalog (per node)

All labels are line-oriented `Label: value` for regex parsing. Values use snake_case enums unless noted.

### Identity & signal (required)

| Label | Type | Example | Notes |
|-------|------|---------|-------|
| Node ID | string | `basis` | Canonical `node_id` |
| Composite Score | int 0–100 | `42` | Weighted components primary; `horizon_net` fallback |
| Composite Score Source | enum | `weighted_components` | `weighted_components` \| `horizon_net_fallback` |
| Band | string | `Fragile` | Desk band label |
| Band Key | string | `fragile` | `supportive` \| `mixed` \| `fragile` \| `blocked` |
| Freshness Status | enum | `fresh` | Reuse hydration freshness |
| Horizon Net | int | `-1` | Sum of `HZ_SCORE` over horizon marks |
| Horizon Marks | string | `d1→ d5→ d20↓ d60→` | Marks: `↑` up, `→` flat, `↓` down |
| Key Observation | string | `Calendar rich vs 3Y median.` | One-line node signal |

### Recommendations (required)

| Label | Type | Example |
|-------|------|---------|
| Directional | string | `neutral (low) — Calendar rich but gate caps directional beta.` |
| Relative Value | string | `short_spread — BT near vs deferred calendar (medium)` |

**Directional format:** `{posture} ({conviction}) — {rationale}`  
Postures: `long` \| `short` \| `neutral` \| `no_trade`

**Relative Value format:** `{posture} — {structure} ({conviction})`  
Postures: `long_spread` \| `short_spread` \| `neutral` \| `no_trade`

### Implementation & RV (required when populated)

| Label | Type | Example | Notes |
|-------|------|---------|-------|
| Selected Implementation | string | `basis_btc_calendar` | Operator choice; `—` if none |
| RV Series | string | `btc_calendar_bt_near_deferred` | Active `series_id` |
| RV Direction | enum | `higher_is_richer` | Per-series `quartile_direction` from Master DD |
| RV Horizon | string | `3m` | Active horizon key |
| RV Quartile | string | `Q4` | Q1–Q4 from empirical percentile |
| RV Percentile | int 0–100 | `82` | Per-series, per-horizon |
| RV Richness | enum | `extreme` | `cheap` \| `fair` \| `rich` \| `extreme` |

**Omit RV lines** when no horizon is populated for the active series (cockpit still valid per MVP degrade rules).

### China parallel (optional)

| Label | Type | Example |
|-------|------|---------|
| China Parallel | string | `present — horizon_net -1` |
| China Parallel Note | string | `China basis stage aligned with global calendar read` |

When absent: omit both lines. Cockpit remains fully operable.

---

## Full Example (basis node excerpt)

```
--- NODE COCKPIT: Basis & Term Structure ---
Node ID: basis
Composite Score: 42
Composite Score Source: weighted_components
Band: Fragile
Band Key: fragile
Freshness Status: fresh
Horizon Net: -1
Horizon Marks: d1→ d5→ d20↓ d60→
Directional: neutral (low) — Calendar rich but gate caps directional beta.
Relative Value: short_spread — BT near vs deferred calendar (medium)
Selected Implementation: —
RV Series: btc_calendar_bt_near_deferred
RV Direction: higher_is_richer
RV Horizon: 3m
RV Quartile: Q4
RV Percentile: 82
RV Richness: extreme
China Parallel: present — horizon_net -1
China Parallel Note: China basis stage aligned with global calendar read
Key Observation: Calendar rich vs 3Y median; 20D trend deteriorating.
```

---

## Hydration bundle coupling

| Bundle key | WTM v2.2 mapping |
|------------|------------------|
| `node_cockpits.{node_id}` | Source object for each `NODE COCKPIT` block |
| `cockpit_context` | Not exported line-by-line; used for `is_weakest_link` derivation |
| `hydration_version` | `1.1.0` when `node_cockpits` present |
| `wtm_export_v22` | Full text: v2.1 core + five node blocks |

**Build path:** `build_hydration_bundle()` → `build_node_cockpits()` → `build_wtm_export_v22()`.

---

## Parser rules

1. **Backward compatibility:** If only `--- WTM EXPORT v2.1 ---` is present, parse as v2.1.
2. **v2.2 detection:** Presence of any `--- NODE COCKPIT:` header marks export as v2.2.
3. **Node ID authority:** `Node ID:` line is canonical; display name in header is cosmetic.
4. **Round-trip:** `build_node_cockpit_export_block(cockpit)` must reproduce all required labels from a hydration `node_cockpits` object.

---

## Versioning

| Version | Schema | Notes |
|---------|--------|-------|
| v2.0 | Global core only | Legacy Perplexity |
| v2.1 | Global + SQ3 + Tracer + Provenance | Phase 2.1 canonical |
| v2.2 | v2.1 + five `NODE COCKPIT` blocks | **Phase 2 node cockpit** |

Parser priority: v2.2 if node blocks present, else v2.1, else v2.0.

---

## Related documents

- [Phase2_Node_Cockpit_Data_Model.md](../01_Strategy_Docs/Phase2_Node_Cockpit_Data_Model.md) — JSON schema authority
- [WTM_EXPORT_v2.1_SPEC.md](WTM_EXPORT_v2.1_SPEC.md) — global core unchanged
- `whinfell_pipeline/node_cockpits.py` — builder implementation
- `whinfell_pipeline/export_contract.py` — `build_node_cockpit_export_block`, `build_wtm_export_v22`