# WTM EXPORT v2.1 — Canonical Handshake Specification

**Status:** Locked (Phase 2.1)  
**Consumers:** Transmission Control, Whinfell Pipeline, SQ3 scoring, Perplexity prompts  
**Supersedes:** WTM EXPORT v2.0 (backward-compatible import)

---

## Purpose

Single label-block contract between research (Perplexity), data pipeline (Parquet), scoring (SQ3), and operator console (Transmission Control). Every field is line-oriented `Label: value` for reliable regex parsing.

---

## Block Structure

```
--- WTM EXPORT v2.1 ---
[Global Core]
[China SQ3]
[Signal Tracer — optional, suggested marks]
[Provenance & Freshness]
```

Blocks terminate at the next `--- WTM EXPORT` header or end of text. v2.0 blocks parse with reduced field set (no provenance, no tracer section).

---

## Field Catalog

### Global Core (required for `parsed`)

| Label | Type | Example | Notes |
|-------|------|---------|-------|
| Whinfell Score | int 0–100 | `58` | Global transmission score |
| Transmission State | enum | `Stressed` | Normal / Stressed / Disorderly / Crisis |
| Regime Tag | string | `Fragile Risk-On` | Desk regime phrase |
| Key Observation | string | `Credit mixed; breadth narrowing.` | 1–2 sentences |
| Gross Risk Recommendation | string | `35% total, Light posture` | Desk sizing handoff |
| BTC Bias | enum | `Neutral` | Confirming / Dragging / Neutral |
| Timestamp | ISO datetime | `2026-06-27T14:00:00` | Observation time (UTC preferred) |

### China SQ3 (required when dual-track active)

| Label | Type | Example |
|-------|------|---------|
| SQ3 Score | int 0–100 | `55` |
| SQ3 Band | string | `Mixed / Fragile` |
| Policy Strength | int 0–100 | `74` |
| State Impulse Score | int −100–100 | `38` |
| Growth Impulse Score | int 0–100 | `61` |
| China Regime Tag | string | `targeted fiscal support` |

### Signal Tracer (optional — hybrid suggest + confirm)

One line per ladder stage. Marks: `↑` (confirming), `→` (neutral), `↓` (impairing).

| Label pattern | Example |
|---------------|---------|
| `Signal Tracer — {Stage Name}: {horizons}` | `Signal Tracer — High-Beta / BTC: 1d: ↑ \| 5d: → \| 20d: ↓ \| 60d: →` |

Stage names (fixed order): Liquidity & Rates · Credit Confirmation · Equity Breadth · High-Beta / BTC · Basis & Term Structure

**Operator rule:** Pipeline/console may *suggest* tracer lines; horizon dropdowns require explicit operator confirmation before gate enforcement.

### Provenance & Freshness (required in pipeline-generated exports)

| Label | Type | Example |
|-------|------|---------|
| Snapshot ID | string | `snap_20260627_koyfin_01` |
| Lineage Hash | string | `sha256:fe1d83d6...` |
| Validation Status | enum | `parsed` / `partial` / `failed` |
| Data As Of | ISO datetime | `2026-06-27T14:00:00Z` |
| Source Channel | enum | `koyfin` / `barchart` / `perplexity` / `transmission_control` / `parquet` |
| Freshness Status | enum | `fresh` / `aging` / `stale` |

**Freshness thresholds (desk default):**

| Status | Age since Data As Of |
|--------|----------------------|
| fresh | &lt; 4 hours |
| aging | 4–24 hours |
| stale | &gt; 24 hours |

---

## Full Example (dual-track + tracer + provenance)

```
--- WTM EXPORT v2.1 ---
Whinfell Score: 58
Transmission State: Stressed
Regime Tag: Fragile Risk-On
Key Observation: Credit mixed; breadth narrowing; BTC lagging SPY.
Gross Risk Recommendation: 35% total, Light posture
BTC Bias: Neutral
Timestamp: 2026-06-27T14:00:00
SQ3 Score: 55
SQ3 Band: Mixed / Fragile
Policy Strength: 74
State Impulse Score: 38
Growth Impulse Score: 61
China Regime Tag: targeted fiscal support
Signal Tracer — Liquidity & Rates: 1d: → | 5d: → | 20d: ↓ | 60d: ↓
Signal Tracer — Credit Confirmation: 1d: ↓ | 5d: ↓ | 20d: → | 60d: →
Signal Tracer — Equity Breadth: 1d: → | 5d: ↑ | 20d: ↑ | 60d: →
Signal Tracer — High-Beta / BTC: 1d: ↓ | 5d: ↓ | 20d: → | 60d: →
Signal Tracer — Basis & Term Structure: 1d: → | 5d: → | 20d: → | 60d: ↑
Snapshot ID: snap_20260627_koyfin_01
Lineage Hash: sha256:fe1d83d6a1ea739b2e8b3b5b96d9186393762f682498e0c82b76d745f231339f
Validation Status: parsed
Data As Of: 2026-06-27T14:00:00Z
Source Channel: koyfin
Freshness Status: fresh
```

---

## End-to-end operator chain (Phase 2.2c + Comet runbook)

```
Comet CSV export → ~/Downloads
     → python3 run_csv_download.py daily (copy → staged_raw/, .meta.json, manifests)
     → collect → Parquet + execution sidecar (ingest --staged under the hood)
     → hydrate → data/hydration/latest.json
     → Transmission Control "Import Latest Hydration Bundle"
     → Suggested Tracer (Accept / Dismiss) — hybrid confirm_required
```

**Runbook commands:** `init` · `stage` · `collect` · `hydrate` · `daily`  
**Flags:** `--downloads` · `--staged-root` · `--operator` · `--window` · `--export` · `--hydrate-output`

Alternate path (manual drop): `python3 -m whinfell_pipeline.ingest --staged` → `hydrate`

Initialize folders: `scripts/init_daily_csv.sh` or `python3 run_csv_download.py init`

Browser blueprint (backup views, Comet shortcuts, supervised prompt): `08_Deliverables/Comet_Browser_Operations_Blueprint.md`

### Staged CSV layout (`staged_raw/`)

| Source folder | Dataset subfolders |
|---------------|-------------------|
| `source=barchart/` | `futures_intraday`, `futures_daily`, `options`, `greeks` |
| `source=koyfin/` | `rates`, `credit`, `equities` |
| `source=china_policy/` | *(CSV at source root)* |

**Naming:** `{dataset}_{YYYYMMDD}_{HHMM}.csv` or `{product}_{flavor}_{YYYYMMDD}.csv`

**Ingest:** `python3 -m whinfell_pipeline.ingest --staged [--staged-root staged_raw] [--dry-run] [--no-archive]`

Processed CSVs move to `archived/` under each dataset folder. Staged rows route through the existing adapter registry (`KoyfinAdapter`, `BarchartAdapter`, etc.).

## Parquet Hydration Flow

```
Parquet (global + china) → python -m whinfell_pipeline.hydrate → hydration_bundle.json
     → Transmission Control "Import Latest Hydration Bundle" → high-signal field populate
     → Suggested Tracer panel (Accept / Dismiss) — hybrid confirm_required
     → Operator Save State
```

### High-signal auto-population

`python -m whinfell_pipeline.hydrate` reads the latest Global and China Parquet rows and emits a **hydration bundle** with deterministic, auditable derivations:

| Bundle key | Populates in console | Notes |
|------------|---------------------|-------|
| `global` | Whinfell score, transmission state, regime, key observation | Includes derived `btc_bias` from observation text |
| `china` | Policy strength, state impulse, growth impulse, regime tag | SQ3 score/band when present |
| `execution` | BTC bias (research readout), L3 near/far/basis/ref* | Basis fields empty until execution data is present in Parquet |
| `suggested_tracer` | Amber **Suggested Tracer** panel only | Stages: Liquidity & Rates, Credit, Breadth, High-Beta / BTC, Basis & Term Structure |
| `freshness_status` + provenance | Command-bar chip + Data Provenance panel | Snapshot ID, lineage hash, source channel, data as-of |

**Rates / credit / BTC basis** do not add new intake fields. They surface through:

1. **Tracer stage suggestions** — heuristics on `key_observation`, Whinfell score, transmission state, and China impulses (`derive_suggested_tracer` in `hydrate.py`).
2. **BTC bias** — `Dragging` / `Confirming` / `Neutral` from observation keywords; written to `global.btc_bias`, `execution.btc_bias`, and WTM `BTC Bias:` line.
3. **L3 basis** — `execution.near_month`, `far_month`, `basis_spread`, `ref_low/mid/high` when available. Ingest writes the latest Barchart execution payload to `data/execution/v1/latest_execution.json`; hydrate merges those fields into `global` and `execution` automatically (override via `--execution-json`).

### Hybrid human-in-loop model

- `tracer_apply_mode` is always **`confirm_required`** on hydration bundles.
- Import **never** writes `suggested_tracer` marks into the horizon matrix.
- WTM EXPORT v2.1 tracer lines embedded in `wtm_export_v21` are stripped on hydration import (provenance and scalar fields still apply).
- Operator must click **Accept Suggestions** to apply marks; **Dismiss** clears the banner with no matrix change.
- Manual edits after import set `manualOverride` on provenance until the next hydration re-import.

### Freshness & provenance display

| Field | Display |
|-------|---------|
| `snapshot_id` | Provenance panel · optional WTM line |
| `lineage_hash` | Provenance panel (truncated) |
| `as_of` | Provenance panel · freshness computation |
| `freshness_status` | Command-bar chip + provenance (`fresh` / `aging` / `stale`) |
| `source` / channel | Provenance panel (`parquet` on hydration path) |

### Phase 2.2 — Authoritative command bar

After Parquet hydration or WTM EXPORT v2.1 import, Transmission Control locks a **command bar authority** snapshot (`commandBarAuthority` in browser state):

| Metric | Pipeline source |
|--------|-----------------|
| Whinfell Score + zone | `global.whinfell_score` |
| SQ3 score + band | `china.sq3_score` / `sq3_band` (fallback: computed from dimensions) |
| Gate label | Derived from score + optional `gate_status`; China SQ3 &lt;50 adds caution suffix |
| Gross Risk % | WTM gross recommendation when present; else score-tier default (e.g. 30% at score 58) |
| Freshness | `freshness_status` + colored dot, source channel, snapshot ID, data as-of |

- Blue **Pipeline** badge = command bar reflects hydrated bundle (not manually overridden).
- Amber **Override** badge = operator edited intake after hydration; bar shows live-derived values until re-import.

### Phase 2.2b — Hybrid Signal Tracer + progressive disclosure

**Tracer flow states** (matrix header badge + table border):

| State | Trigger | Matrix |
|-------|---------|--------|
| Suggestions Pending | Hydration import with `suggested_tracer` | Empty until Accept |
| Operator Confirmed | Accept on suggested panel | Marks applied; green chrome |
| Manual Override | Manual Override button or horizon `.hz-select` edit after hydration | Amber chrome; `tracer.flow = override`; `provenance.manualOverride = true`; command bar **Override** badge |

Intake/gross/L3-only edits call pure `applyIntakeOverride(prov)` — always sets `manualOverride`; command bar **Override** badge renders only when `hydratedAt` is set. Horizon edits call `applyHorizonOverride(state)` — sets `tracer.flow`, clears `suggestedTracer`, and `provenance.manualOverride` (even without hydration). Chrome reads via `getTracerChrome(tracer, suggested)` — never `manualOverride`.

Pure helpers (`applySuggestedMarks`, `applyIntakeOverride`, `applyHorizonOverride`, `getTracerChrome`) support headless verification. `confirm_required` is unchanged — import never auto-writes tracer horizons.

**Progressive disclosure (center pane):** WTM prompts expand on click; Gross Risk posture/capital/handover, shock configuration, and tracer snapshots use collapsible `<details>` panels closed by default.

---

## Versioning

| Version | Schema | Notes |
|---------|--------|-------|
| v2.0 | Global core only | Legacy Perplexity prompts |
| v2.1 | Global + SQ3 + Tracer + Provenance | **Canonical** Phase 2.1 |

Parser priority: v2.1 block if present, else v2.0 fallback.