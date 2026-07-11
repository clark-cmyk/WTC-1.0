"""Operator confirm — validate production hydration bundle against desk criteria."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = REPO_ROOT / "data/hydration/latest.json"
FEEDBACK_LOG = REPO_ROOT / "08_Deliverables/Desk_Feedback_Log.md"
CANONICAL_NODES = ("liquidity", "credit", "breadth", "highbeta", "basis")


@dataclass
class ConfirmResult:
    passed: int = 0
    failed: int = 0
    checks: list[dict[str, str]] = field(default_factory=list)
    lineage_hash: str = ""
    as_of: str = ""


def _check(name: str, ok: bool, detail: str = "") -> dict[str, str]:
    return {"name": name, "result": "PASS" if ok else "FAIL", "detail": detail}


def run_operator_confirm(bundle_path: Path | None = None) -> ConfirmResult:
    """Validate production bundle fields required for desk sign-off."""
    out = ConfirmResult()
    path = bundle_path or DEFAULT_BUNDLE

    if not path.is_file():
        out.checks.append(_check("bundle_exists", False, str(path)))
        out.failed += 1
        return out

    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        out.checks.append(_check("bundle_parse", False, str(exc)))
        out.failed += 1
        return out

    out.lineage_hash = str(bundle.get("lineage_hash") or "")
    out.as_of = str(bundle.get("as_of") or "")

    checks = [
        _check(
            "hydration_version",
            bool(bundle.get("hydration_version")),
            str(bundle.get("hydration_version", "")),
        ),
        _check(
            "lineage_hash",
            str(bundle.get("lineage_hash", "")).startswith("sha256:"),
            str(bundle.get("lineage_hash", ""))[:24] + "…",
        ),
        _check(
            "freshness_status",
            bundle.get("freshness_status") in ("fresh", "stale"),
            str(bundle.get("freshness_status", "")),
        ),
        _check(
            "node_cockpits",
            set((bundle.get("node_cockpits") or {}).keys()) == set(CANONICAL_NODES),
            f"{len(bundle.get('node_cockpits') or {})}/5 nodes",
        ),
        _check(
            "wtm_export_v22",
            "WTM EXPORT v2.2" in str(bundle.get("wtm_export_v22") or ""),
            "present" if bundle.get("wtm_export_v22") else "missing",
        ),
        _check(
            "flows_sidecar",
            (bundle.get("flows_sidecar") or {}).get("flows_status") in ("ok", "fallback_1d", "unavailable"),
            str((bundle.get("flows_sidecar") or {}).get("flows_status", "")),
        ),
        _check(
            "ingest_provenance",
            bool(bundle.get("ingest_provenance")),
            f"{(bundle.get('ingest_provenance') or {}).get('staged_count', 0)} staged routes",
        ),
        _check(
            "funds_flow_export_lines",
            "Funds Flow Verdict:" in str(bundle.get("wtm_export_v22") or ""),
            "PR-5 flow lines in export",
        ),
    ]

    for row in checks:
        out.checks.append(row)
        if row["result"] == "PASS":
            out.passed += 1
        else:
            out.failed += 1

    return out


def append_feedback_summary(result: ConfirmResult) -> Path:
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "",
        f"## BUILD Operator Confirm ({when})",
        "",
        f"**Bundle:** `data/hydration/latest.json`",
        f"**lineage_hash:** `{result.lineage_hash}`",
        f"**as_of:** {result.as_of}",
        f"**Result:** {result.passed} PASS · {result.failed} FAIL",
        "",
        "| Check | Result | Detail |",
        "|-------|--------|--------|",
    ]
    for row in result.checks:
        lines.append(f"| {row['name']} | {row['result']} | {row['detail'][:80]} |")
    lines.extend([
        "",
        "**Clark action:** Complete live Focus-mode walk-through; log node ratings in checklist above.",
        "",
    ])
    text = FEEDBACK_LOG.read_text(encoding="utf-8") if FEEDBACK_LOG.is_file() else ""
    marker = f"## BUILD Operator Confirm ({when})"
    if marker not in text:
        FEEDBACK_LOG.write_text(text + "\n".join(lines), encoding="utf-8")
    return FEEDBACK_LOG


def main() -> int:
    result = run_operator_confirm()
    for row in result.checks:
        print(f"{row['result']:4} {row['name']}: {row['detail']}")
    print(f"\noperator_confirm: {result.passed} PASS · {result.failed} FAIL")
    append_feedback_summary(result)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())