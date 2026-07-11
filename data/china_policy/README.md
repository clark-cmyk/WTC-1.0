# China Policy Track Data

**Parquet file:** `v1/china_policy_observations.parquet`  
**Schema version:** `1.0.0`  
**Track ID:** `china_policy`

Coexists alongside Global track storage at `data/global/v1/global_observations.parquet`. China ingestion never writes to `data/global/`.

Ingest via:

```bash
python3 -m china_policy_track.ingest --input china_policy_track/examples/sample_perplexity_export.txt
```

See `china_policy_track/data_dictionary.md` for field definitions.