# staged_raw — Operator CSV staging (Chunk 2.2c)

Drop collector CSV exports here before pipeline ingest. Processed files move to `archived/` under each dataset folder.

## Layout

```
staged_raw/
├── source=barchart/
│   ├── dataset=futures_intraday/
│   ├── dataset=futures_daily/
│   ├── dataset=options/
│   └── dataset=greeks/
├── source=koyfin/
│   ├── dataset=rates/
│   ├── dataset=credit/
│   └── dataset=equities/
├── source=crypto/
│   ├── dataset=crypto_snapshot/
│   ├── dataset=btc_price_chart/
│   ├── dataset=btc_correl_chart/
│   ├── dataset=eth_correl_chart/
│   ├── dataset=xrp_correl_chart/
│   ├── dataset=sol_correl_chart/
│   └── dataset=crypto_corr_series/
└── source=china_policy/
```

## Naming

- `{dataset}_{YYYYMMDD}_{HHMM}.csv`
- `{product}_{flavor}_{YYYYMMDD}.csv`

## Daily chain

1. Export from Transmission Control or Comet collector
2. Save CSV into the matching `source=` / `dataset=` folder
3. `python3 -m whinfell_pipeline.ingest --staged`
4. `python3 -m whinfell_pipeline.hydrate -o /tmp/hydration.json`
5. Import hydration bundle in Transmission Control

Initialize tree: `python3 -m whinfell_pipeline.staged_csv init`
