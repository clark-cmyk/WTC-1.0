"""Build Transmission Ladder deep-dive chartLinks from desk_urls.yaml.

Regenerate after Clark pastes Koyfin share links into desk_urls.yaml:

    python3 -m whinfell_pipeline.desk_chart_links
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from whinfell_pipeline.batch_collect import _resolve_url_field, load_desk_urls

KOYFIN_SHARE_PLACEHOLDERS: dict[str, str] = {
    "WTM-Rates-Credit": "REPLACE_WTM_RATES_CREDIT_SHARE_URL",
    "WTM-Credit-Confirmation": "REPLACE_WTM_CREDIT_CONFIRMATION_SHARE_URL",
    "WTM-Equities-Breadth": "REPLACE_WTM_EQUITIES_BREADTH_SHARE_URL",
    "Whinfell-Daily-TimeSeries": "REPLACE_WHINFELL_DAILY_TIMESERIES_URL",
}

ASSIST_PLACEHOLDERS: dict[str, str] = {
    "WTM-Rates-Credit": "REPLACE_USGG2Y10Y_OR_DGS10_URL",
    "WTM-Credit-Confirmation": "REPLACE_HYG_US_OR_LQD_US_URL",
    "WTM-Equities-Breadth": "REPLACE_IWM_SPY_ASSIST_URL",
}

BARCHART_PLACEHOLDERS: dict[str, str] = {
    "WTM-BTC-Basis": "REPLACE_WTM_BTC_BASIS_SPREADS_URL",
    "WTM-Futures-Intraday": "REPLACE_WTM_FUTURES_INTRADAY_URL",
    "WTM-Futures-Daily": "REPLACE_WTM_FUTURES_DAILY_URL",
}

LADDER_CHART_STAGES: dict[str, dict[str, Any]] = {
    "liquidity": {
        "note": "Check the 20D direction of the 2s10s curve and front-end funding impulse.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Rates-Credit",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Rates-Credit",
            "kind": "koyfin_assist",
            "assist_index": 0,
        },
    },
    "credit": {
        "note": "Check whether HY is confirming risk-on: HYG/LQD trend, spread tightening, and 5D follow-through.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Credit-Confirmation",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Credit-Confirmation",
            "kind": "koyfin_assist",
            "assist_index": 0,
        },
    },
    "breadth": {
        "note": "Check whether participation is broadening beyond index strength, especially on 5D and 20D.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Equities-Breadth",
            "kind": "koyfin_share",
        },
        "secondary": {
            "label": "Assist",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "WTM-Equities-Breadth",
            "kind": "koyfin_assist",
            "assist_index": 0,
        },
    },
    "highbeta": {
        "note": "Check whether BTC is leading as high beta or merely reacting, and whether 5D/20D beta transmission is clean.",
        "primary": {
            "label": "View Chart",
            "source": "Koyfin",
            "section": "koyfin",
            "view": "Whinfell-Daily-TimeSeries",
            "kind": "koyfin_share",
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
        "note": "Check front-vs-next calendar richness, contango stability, and whether the 20D basis trend supports warehousing.",
        "primary": {
            "label": "View Chart",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-BTC-Basis",
            "kind": "barchart_view",
        },
        "secondary": {
            "label": "History",
            "source": "Barchart",
            "section": "barchart",
            "view": "WTM-Futures-Daily",
            "kind": "barchart_view",
        },
    },
}


def _view_spec(desk: dict[str, Any], section: str, view: str) -> dict[str, Any]:
    spec = (desk.get(section) or {}).get(view) or {}
    return spec if isinstance(spec, dict) else {}


def resolve_koyfin_share(spec: dict[str, Any], view: str) -> str:
    expanded = _resolve_url_field(str(spec.get("url", "")), None, "")
    if expanded and not expanded.startswith("${"):
        return expanded
    return KOYFIN_SHARE_PLACEHOLDERS.get(view, "")


def resolve_koyfin_assist(spec: dict[str, Any], view: str, assist_index: int = 0) -> str:
    assists = list(spec.get("assist_urls") or [])
    if assists:
        idx = min(max(assist_index, 0), len(assists) - 1)
        return str(assists[idx])
    return ASSIST_PLACEHOLDERS.get(view, "")


def resolve_barchart_view(spec: dict[str, Any], view: str) -> str:
    resolved = _resolve_url_field(
        str(spec.get("url", "")),
        spec.get("wired_url"),
        "",
    )
    if resolved and not resolved.startswith("${"):
        return resolved
    return BARCHART_PLACEHOLDERS.get(view, "")


def resolve_link_url(desk: dict[str, Any], link: dict[str, Any]) -> str:
    spec = _view_spec(desk, str(link["section"]), str(link["view"]))
    kind = link.get("kind", "")
    view = str(link["view"])
    if kind == "koyfin_share":
        return resolve_koyfin_share(spec, view)
    if kind == "koyfin_assist":
        return resolve_koyfin_assist(spec, view, int(link.get("assist_index", 0)))
    if kind == "barchart_view":
        return resolve_barchart_view(spec, view)
    return ""


def build_chart_links(desk: dict[str, Any] | None = None) -> dict[str, Any]:
    desk = desk if desk is not None else load_desk_urls()
    chart_links: dict[str, Any] = {}

    for stage_id, cfg in LADDER_CHART_STAGES.items():
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
            "version": "1.0.0",
            "source": "whinfell_pipeline/desk_urls.yaml",
            "updated": (desk.get("updated") if isinstance(desk.get("updated"), str) else None)
            or date.today().isoformat(),
        },
        "chartLinks": chart_links,
    }


def default_output_paths() -> tuple[Path, Path]:
    repo = Path(__file__).resolve().parents[1]
    deliverables = repo / "08_Deliverables"
    return deliverables / "desk_chart_links.json", deliverables / "desk_chart_links.js"


def write_chart_links(
    desk: dict[str, Any] | None = None,
    json_path: Path | None = None,
    js_path: Path | None = None,
) -> dict[str, Any]:
    payload = build_chart_links(desk)
    json_out, js_out = default_output_paths()
    if json_path:
        json_out = json_path
    if js_path:
        js_out = js_path

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    js_body = "const chartLinks = " + json.dumps(payload["chartLinks"], indent=2) + ";\n"
    js_out.write_text(js_body, encoding="utf-8")
    return payload


def main() -> None:
    payload = write_chart_links()
    links = payload["chartLinks"]
    print(f"Wrote chartLinks for {len(links)} stages")
    for stage_id, stage in links.items():
        print(f"  {stage_id}: primary={stage['primary']['url']} · secondary={stage['secondary']['url']}")


if __name__ == "__main__":
    main()