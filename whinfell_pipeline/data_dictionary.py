"""Load and query WTM data dictionary — canonical assets, routing, field maps."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DICTIONARY_VERSION = "1.0"


def default_dictionary_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parent
    return root / "data_dictionary.yaml"


@lru_cache(maxsize=1)
def load_data_dictionary(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else default_dictionary_path()
    with p.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return dict(data)


def canonical_asset_for_ticker(vendor: str, ticker: str, data: dict[str, Any] | None = None) -> str | None:
    """Resolve raw vendor ticker to canonical asset id."""
    dd = data or load_data_dictionary()
    t = ticker.strip().upper()
    for asset_id, spec in (dd.get("canonical_assets") or {}).items():
        sources = spec.get("sources") or {}
        raw = sources.get(vendor)
        if raw and str(raw).upper() == t:
            return asset_id
        if raw and str(raw).upper().lstrip("^$") == t.lstrip("^$"):
            return asset_id
    return None


def koyfin_china_policy_universe(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict((dd.get("universes") or {}).get("koyfin_china_policy") or {})


def china_policy_tickers(data: dict[str, Any] | None = None) -> list[str]:
    china = koyfin_china_policy_universe(data)
    return list(china.get("tickers") or [])


def china_policy_industrial_proxy(data: dict[str, Any] | None = None) -> dict[str, Any]:
    china = koyfin_china_policy_universe(data)
    return dict(china.get("industrial_proxy") or {})


def barchart_term_structure_universe(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict((dd.get("universes") or {}).get("barchart_term_structure") or {})


def term_structure_active_screens(data: dict[str, Any] | None = None) -> list[str]:
    ts = barchart_term_structure_universe(data)
    return list(ts.get("active_screens") or [])


def term_structure_ladder_shortcuts(data: dict[str, Any] | None = None) -> list[str]:
    ts = barchart_term_structure_universe(data)
    return list(ts.get("ladder_shortcuts") or [])


def koyfin_provides_term_structure(data: dict[str, Any] | None = None) -> bool:
    dd = data or load_data_dictionary()
    blocked = (dd.get("ticker_standards") or {}).get("koyfin", {}).get("does_not_provide") or []
    return "futures_term_structure" not in blocked


def barchart_core_symbols(data: dict[str, Any] | None = None) -> list[str]:
    dd = data or load_data_dictionary()
    return list((dd.get("universes") or {}).get("barchart_core", {}).get("symbols") or [])


def barchart_curve_symbols(data: dict[str, Any] | None = None) -> list[str]:
    dd = data or load_data_dictionary()
    groups = (dd.get("universes") or {}).get("barchart_curves", {}).get("symbol_groups") or {}
    out: list[str] = []
    for key, syms in groups.items():
        if key == "structured_spreads":
            continue
        out.extend(syms)
    return out


def barchart_spread_symbols(data: dict[str, Any] | None = None) -> list[str]:
    dd = data or load_data_dictionary()
    groups = (dd.get("universes") or {}).get("barchart_curves", {}).get("symbol_groups") or {}
    return list(groups.get("structured_spreads") or [])


def barchart_all_approved_symbols(data: dict[str, Any] | None = None) -> list[str]:
    return barchart_core_symbols(data) + barchart_curve_symbols(data) + barchart_spread_symbols(data)


def barchart_canonical_core_map(data: dict[str, Any] | None = None) -> dict[str, str]:
    dd = data or load_data_dictionary()
    return dict(dd.get("barchart_canonical_core") or {})


def barchart_history_field_map(data: dict[str, Any] | None = None) -> dict[str, str]:
    dd = data or load_data_dictionary()
    return dict(dd.get("barchart_history_fields") or {})


def barchart_instrument_class_map(data: dict[str, Any] | None = None) -> dict[str, str]:
    dd = data or load_data_dictionary()
    return dict(dd.get("barchart_instrument_class") or {})


def source_system_ids(data: dict[str, Any] | None = None) -> list[str]:
    dd = data or load_data_dictionary()
    return list((dd.get("source_systems") or {}).keys())


def legacy_alias(name: str, data: dict[str, Any] | None = None) -> str | None:
    dd = data or load_data_dictionary()
    entry = (dd.get("legacy_aliases") or {}).get(name)
    if isinstance(entry, dict):
        return entry.get("canonical")
    return None


def snapshot_field_map(data: dict[str, Any] | None = None) -> dict[str, str]:
    dd = data or load_data_dictionary()
    return dict((dd.get("field_mappings") or {}).get("snapshot") or {})


def master_dictionary_info(data: dict[str, Any] | None = None) -> dict[str, str]:
    """Return locked Master Data Dictionary version, date, and status."""
    dd = data or load_data_dictionary()
    mdd = dd.get("master_data_dictionary") or {}
    return {
        "version": str(mdd.get("version") or dd.get("version") or DICTIONARY_VERSION),
        "date": str(mdd.get("date") or dd.get("updated") or ""),
        "status": str(mdd.get("status") or dd.get("status") or "Locked"),
        "alignment": str(mdd.get("alignment") or "Aligned"),
    }


def dictionary_status(data: dict[str, Any] | None = None) -> str:
    return master_dictionary_info(data)["status"]


def get_project_structure(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("project_structure") or {})


def get_watchlist_names(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("watchlist_names") or {})


def get_canonical_filename_patterns(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("file_naming_conventions") or {})


def get_json_field_map(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("json_structures") or {})


def get_column_mappings(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("column_mappings") or {})


def get_ticker_standards(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("ticker_standards") or {})


def normalize_glob_rules(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return ordered detect_glob → canonical_template rules from Master DD."""
    fnc = get_canonical_filename_patterns(data)
    rules = fnc.get("normalize_rules")
    if isinstance(rules, list) and rules:
        return [dict(r) for r in rules]
    return []


def canonical_dataset_names(data: dict[str, Any] | None = None) -> list[str]:
    fnc = get_canonical_filename_patterns(data)
    return list(fnc.get("canonical_datasets") or [])


def canonical_filename_patterns(data: dict[str, Any] | None = None) -> list[str]:
    """Glob patterns for already-canonical staged filenames."""
    datasets = canonical_dataset_names(data)
    patterns = [f"{ds}_*" for ds in datasets]
    patterns.extend(
        [
            "flows_*",
            "btc_price_chart_*",
            "btc_correl_chart_*",
            "eth_correl_chart_*",
            "xrp_correl_chart_*",
            "sol_correl_chart_*",
            "options_*",
            "greeks_*",
        ]
    )
    return patterns


def raw_patterns_for_dataset(dataset: str, data: dict[str, Any] | None = None) -> list[str]:
    """Vendor detect globs for a canonical dataset (from watchlist_names)."""
    wl = get_watchlist_names(data)
    out: list[str] = []
    for section in ("koyfin_saved_views", "barchart_screens"):
        for view in (wl.get(section) or {}).values():
            if view.get("dataset") == dataset and view.get("vendor_detect_glob"):
                out.append(str(view["vendor_detect_glob"]))
    for rule in normalize_glob_rules(data):
        if rule.get("dataset") == dataset and rule.get("detect_glob"):
            g = str(rule["detect_glob"])
            if g not in out:
                out.append(g)
    return out


def canonical_saved_view_names(data: dict[str, Any] | None = None) -> list[str]:
    views = (get_watchlist_names(data).get("koyfin_saved_views") or {})
    return list(views.keys())


def get_operator_alignment(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict((dd.get("operator_alignment") or {}).get("enforcement") or {})


def operator_active_files(repo_root: Path | None = None, data: dict[str, Any] | None = None) -> list[Path]:
    """Resolve active_globs from Master DD to concrete file paths."""
    root = repo_root or Path(__file__).resolve().parents[1]
    enforcement = get_operator_alignment(data)
    globs = enforcement.get("active_globs") or []
    found: set[Path] = set()
    for pattern in globs:
        for path in root.glob(pattern):
            if path.is_file():
                found.add(path)
    return sorted(found)


def scan_operator_violations(repo_root: Path | None = None, data: dict[str, Any] | None = None) -> list[str]:
    """Return violation lines: rel_path:lineno: text (forbidden_patterns from Master DD)."""
    root = repo_root or Path(__file__).resolve().parents[1]
    enforcement = get_operator_alignment(data)
    patterns = [str(p) for p in (enforcement.get("forbidden_patterns") or [])]
    violations: list[str] = []
    for path in operator_active_files(root, data):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        for i, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.lower() in line.lower():
                    violations.append(f"{rel}:{i}: {line.strip()}")
                    break
    return violations


def get_rv_series_registry(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("rv_series") or {})


def rv_series_catalog(data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return series_id → spec from Master DD rv_series.series."""
    reg = get_rv_series_registry(data)
    raw = reg.get("series") or {}
    return {str(k): dict(v) for k, v in raw.items()}


def rv_series_for_node(node_id: str, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """All RV series owned by a ladder node_id."""
    out: list[dict[str, Any]] = []
    for sid, spec in rv_series_catalog(data).items():
        if spec.get("node_id") == node_id:
            out.append({"series_id": sid, **spec})
    return out


def rv_series_primary(node_id: str, data: dict[str, Any] | None = None) -> str | None:
    for row in rv_series_for_node(node_id, data):
        if row.get("primary"):
            return str(row["series_id"])
    rows = rv_series_for_node(node_id, data)
    return str(rows[0]["series_id"]) if rows else None


def get_node_score_weights(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("node_score_weights") or {})


def node_score_components(node_id: str, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    nodes = (get_node_score_weights(data).get("nodes") or {})
    spec = nodes.get(node_id) or {}
    return list(spec.get("components") or [])


def badge_default_payload(data: dict[str, Any] | None = None) -> dict[str, str]:
    info = master_dictionary_info(data)
    return {
        "version": info["version"],
        "date": info["date"],
        "status": info["status"],
        "alignment": info["alignment"],
        "source": "whinfell_pipeline/data_dictionary.yaml",
        "loadingLabel": "Loading dictionary…",
    }


def get_funds_flow_baskets(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("funds_flow_baskets") or {})


def funds_flow_basket_for_node(node_id: str, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return locked basket spec for a ladder node (includes node_id)."""
    nodes = (get_funds_flow_baskets(data).get("nodes") or {})
    spec = nodes.get(node_id)
    if not spec:
        return None
    return {"node_id": node_id, **dict(spec)}


def funds_flow_node_ids(data: dict[str, Any] | None = None) -> list[str]:
    return list((get_funds_flow_baskets(data).get("nodes") or {}).keys())


def funds_flow_thresholds(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("funds_flow_thresholds") or {})


def get_funds_flow_thresholds(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return funds_flow_thresholds(data)


def funds_flow_column_map(data: dict[str, Any] | None = None) -> dict[str, list[str]]:
    dd = data or load_data_dictionary()
    raw = dd.get("funds_flow_column_patterns") or {}
    return {str(k): list(v) for k, v in raw.items()}


def get_funds_flow_column_patterns(data: dict[str, Any] | None = None) -> dict[str, list[str]]:
    return funds_flow_column_map(data)


def get_funds_flow_ingest(data: dict[str, Any] | None = None) -> dict[str, Any]:
    dd = data or load_data_dictionary()
    return dict(dd.get("funds_flow_ingest") or {})


def funds_flow_sidecar_path(data: dict[str, Any] | None = None) -> str:
    ingest = get_funds_flow_ingest(data)
    return str(ingest.get("sidecar_path") or "data/flows/v1/latest_flows.json")