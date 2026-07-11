"""Build China ladder chartLinks from desk_urls.yaml (canonical stage IDs)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from whinfell_pipeline.batch_collect import _resolve_url_field, load_desk_urls

KOYFIN_SHARE_PLACEHOLDERS: dict[str, str] = {
    "WTM-China-Liquidity": "REPLACE_WTM_CHINA_RATES_SHARE_URL",
    "WTM-China-Credit": "REPLACE_WTM_CHINA_CREDIT_OR_WHINPUMP_URL",
    "WTM-China-Breadth": "REPLACE_WTM_CHINA_BREADTH_SHARE_URL",
    "WTM-China-Cyclical": "REPLACE_WTM_CHINA_CYCLICAL_SHARE_URL",
}

ASSIST_PLACEHOLDERS: dict[str, str] = {
    "WTM-China-Liquidity": "REPLACE_GCN10YR_OR_USDCNH_URL",
    "WTM-China-Credit": "REPLACE_KHYB_OR_2829HK_URL",
    "WTM-China-Breadth": "REPLACE_CSI300_OR_HSTECH_URL",
}

BARCHART_PLACEHOLDERS: dict[str, str] = {
    "WTM-China-Cyclical": "REPLACE_WTM_CHINA_FUTURES_INTRADAY_URL",
    "WTM-China-Basis": "REPLACE_WTM_CHINA_COMMODITY_SPREADS_URL",
    "WTM-China-Futures-Daily": "REPLACE_WTM_CHINA_FUTURES_DAILY_URL",
}

# Canonical Whinfell stage IDs
CHINA_CHART_STAGES: dict[str, dict[str, Any]] = {
    "liquidity": {
        "note": "Check the 20D direction of China 10Y and USDCNH funding impulse.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Liquidity",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Liquidity",
            "kind": "koyfin_assist",
            "assist_index": 0,
        },
    },
    "credit": {
        "note": "Check whether KHYB is confirming vs 2829.HK — provisional proxy; validate live.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Credit",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Credit",
            "kind": "koyfin_assist",
            "assist_index": 0,
        },
    },
    "breadth": {
        "note": "Check whether HSTECH is broadening vs CSI300 on 5D and 20D.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Breadth",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-China-Breadth",
            "kind": "koyfin_assist",
            "assist_index": 1,
        },
    },
    "highbeta": {
        "note": "Check whether copper and iron ore are leading cyclical beta on 5D/20D.",
        "primary": {
            "label": "View Chart",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-China-Cyclical",
            "kind": "barchart_view",
        },
        "secondary": {
            "label": "Futures",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-Futures-Intraday",
            "kind": "barchart_view",
        },
    },
    "basis": {
        "note": "Check front-vs-deferred richness and whether 20D curve supports warehousing.",
        "primary": {
            "label": "View Chart",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-China-Basis",
            "kind": "barchart_view",
        },
        "secondary": {
            "label": "History",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-China-Futures-Daily",
            "kind": "barchart_view",
        },
    },
}


def _view_spec(desk: dict[str, Any], section: str, view: str) -> dict[str, Any]:
    spec = (desk.get(section) or {}).get(view) or {}
    return spec if isinstance(spec, dict) else {}


def resolve_link_url(desk: dict[str, Any], link: dict[str, Any]) -> str:
    spec = _view_spec(desk, str(link["section"]), str(link["view"]))
    kind = link.get("kind", "")
    view = str(link["view"])
    if kind == "koyfin_share":
        resolved = _resolve_url_field(
            str(spec.get("url", "")),
            spec.get("wired_url"),
            "",
        )
        if resolved and not resolved.startswith("${"):
            return resolved
        return KOYFIN_SHARE_PLACEHOLDERS.get(view, "")
    if kind == "koyfin_assist":
        assists = list(spec.get("assist_urls") or [])
        if assists:
            idx = min(max(int(link.get("assist_index", 0)), 0), len(assists) - 1)
            return str(assists[idx])
        return ASSIST_PLACEHOLDERS.get(view, "")
    if kind == "barchart_view":
        resolved = _resolve_url_field(
            str(spec.get("url", "")),
            spec.get("wired_url"),
            "",
        )
        if resolved and not resolved.startswith("${"):
            return resolved
        return BARCHART_PLACEHOLDERS.get(view, "")
    return ""


def build_china_chart_links(desk: dict[str, Any] | None = None) -> dict[str, Any]:
    desk = desk if desk is not None else load_desk_urls()
    chart_links: dict[str, Any] = {}
    for stage_id, cfg in CHINA_CHART_STAGES.items():
        primary_spec = dict(cfg["primary"])
        secondary_spec = dict(cfg["secondary"])
        chart_links[stage_id] = {
            "primary": {
                "label": primary_spec["label"],
                "source": primary_spec["source"],
                "url": resolve_link_url(desk, primary_spec),
            },
            "secondary": {
                "label": secondary_spec["label"],
                "source": secondary_spec["source"],
                "url": resolve_link_url(desk, secondary_spec),
            },
            "note": cfg["note"],
        }
    return {
        "_meta": {
            "version": "1.1.0",
            "source": "whinfell_pipeline/desk_urls.yaml",
            "track": "china",
            "updated": (desk.get("updated") if isinstance(desk.get("updated"), str) else None)
            or date.today().isoformat(),
        },
        "chartLinks": chart_links,
    }


def default_output_paths() -> tuple[Path, Path]:
    repo = Path(__file__).resolve().parents[1]
    deliverables = repo / "08_Deliverables"
    return deliverables / "desk_china_chart_links.json", deliverables / "desk_china_chart_links.js"


def write_china_chart_links(
    desk: dict[str, Any] | None = None,
    json_path: Path | None = None,
    js_path: Path | None = None,
) -> dict[str, Any]:
    payload = build_china_chart_links(desk)
    json_out, js_out = default_output_paths()
    if json_path:
        json_out = json_path
    if js_path:
        js_out = js_path
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    js_body = "const chinaChartLinks = " + json.dumps(payload["chartLinks"], indent=2) + ";\n"
    js_out.write_text(js_body, encoding="utf-8")
    return payload


def main() -> None:
    payload = write_china_chart_links()
    links = payload["chartLinks"]
    print(f"Wrote chinaChartLinks for {len(links)} stages")
    for stage_id, stage in links.items():
        print(f"  {stage_id}: primary={stage['primary']['url']} · secondary={stage['secondary']['url']}")


if __name__ == "__main__":
    main()