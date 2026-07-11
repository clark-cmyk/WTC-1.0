# Global Track Parquet Storage (v1)

**Track ID:** `global`  
**Schema version:** `2.0.0` (aligned with WTM EXPORT v2.0)  
**Parquet file:** `global_observations.parquet`

Reserved for Global track observations (Whinfell Score, transmission state, regime tags) produced by Transmission Control and future batch pipelines.

## Layout (parallel to China Policy track)

| Track  | Path |
|--------|------|
| Global | `data/global/v1/global_observations.parquet` |
| China Policy | `data/china_policy/v1/china_policy_observations.parquet` |

## Coexistence rule

- Global data lives only under `data/global/`.
- China Policy ingestion (`china_policy_track`) writes only under `data/china_policy/`.
- Neither module reads or modifies the other track's Parquet files.

## Stub schema (v1)

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | string | Always `global` |
| `schema_version` | string | e.g. `2.0.0` |
| `observation_id` | string | Unique observation key |
| `as_of` | timestamp (UTC) | Observation timestamp |
| `whinfell_score` | int32 | 0–100 |
| `transmission_state` | string | Normal / Stressed / Disorderly / Crisis |
| `regime_tag` | string | Regime label from WTM EXPORT v2.0 |
| `source` | string | e.g. `perplexity`, `manual` |

The committed `global_observations.parquet` is an empty stub (0 rows) so both track directories can coexist in version control. Populate via Transmission Control export or a future Global ingestion module.