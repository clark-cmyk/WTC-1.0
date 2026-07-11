"""Automated desk mission-surface walk-through (headless proxy for live session)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADLESS = REPO_ROOT / "whinfell_pipeline/tests/html_headless_cockpit.mjs"
BUNDLE = REPO_ROOT / "data/hydration/latest.json"
FALLBACK_BUNDLE = REPO_ROOT / "whinfell_pipeline/examples/cockpit_hydration_snippet.json"
FEEDBACK_LOG = REPO_ROOT / "08_Deliverables/Desk_Feedback_Log.md"

NODES = ("basis", "credit", "liquidity", "breadth", "highbeta")
PROBE_KEYS = {
    "credit": "creditMission",
    "liquidity": "liquidityMission",
    "breadth": "breadthMission",
    "highbeta": "highbetaMission",
}


@dataclass
class WalkthroughResult:
    passed: int = 0
    failed: int = 0
    checks: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_headless_suite() -> dict:
    if not HEADLESS.is_file():
        raise FileNotFoundError(f"missing {HEADLESS}")
    proc = subprocess.run(
        ["node", str(HEADLESS)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    text = proc.stdout
    start = text.rfind('{\n  "label"')
    if start < 0:
        raise RuntimeError("headless output missing JSON snapshot")
    return json.loads(text[start:])


def resolve_walkthrough_bundle() -> Path:
    if BUNDLE.is_file():
        return BUNDLE
    return FALLBACK_BUNDLE


def run_walkthrough() -> WalkthroughResult:
    out = WalkthroughResult()
    try:
        snap = run_headless_suite()
    except Exception as exc:
        out.errors.append(str(exc))
        out.failed += 1
        return out

    for node in NODES:
        key = PROBE_KEYS.get(node)
        if key:
            block = snap.get(key) or {}
            ok = any(
                v for k, v in block.items()
                if "MissionSurface" in k and v is True
            ) or bool(block.get("tacticalLead"))
            tactical = block.get("tacticalLead", "")
            out.checks.append({
                "node": node,
                "result": "PASS" if ok and tactical else "FAIL",
                "tactical": tactical[:120],
                "rating": "4" if ok else "2",
            })
            if ok:
                out.passed += 1
            else:
                out.failed += 1
        else:
            # Basis regression — chart + mission banner via credit probe baseline
            chart = snap.get("chart") or {}
            ok = chart.get("drew") and chart.get("pointCount") == 5
            out.checks.append({
                "node": "basis",
                "result": "PASS" if ok else "FAIL",
                "tactical": "Basis mission-surface regression (RV chart 5 horizons)",
                "rating": "4" if ok else "2",
            })
            if ok:
                out.passed += 1
            else:
                out.failed += 1

    ui_ok = snap.get("themeToggle", {}).get("themeToggle") and snap.get("focus", {}).get("focusToggle")
    out.checks.append({
        "node": "UI refactor",
        "result": "PASS" if ui_ok else "PARTIAL",
        "tactical": "Focus + theme + drawer hierarchy (badge 2.2-UI-2026-06-30)",
        "rating": "4" if ui_ok else "3",
    })
    if ui_ok:
        out.passed += 1
    else:
        out.failed += 1

    return out


def append_feedback_summary(result: WalkthroughResult) -> Path:
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "",
        f"## BUILD Automated Desk Session ({when})",
        "",
        f"**Result:** {result.passed} PASS · {result.failed} FAIL · bundle `{resolve_walkthrough_bundle().name}`",
        "",
        "| Node / Area | Result | Rating | Tactical / Notes |",
        "|-------------|--------|--------|------------------|",
    ]
    for row in result.checks:
        lines.append(
            f"| {row['node']} | {row['result']} | {row['rating']}/5 | {row['tactical'][:100]} |"
        )
    lines.extend([
        "",
        "**Operator action:** Confirm ratings after live Focus-mode walk on `data/hydration/latest.json`.",
        "",
    ])
    text = FEEDBACK_LOG.read_text(encoding="utf-8") if FEEDBACK_LOG.is_file() else ""
    if f"## BUILD Automated Desk Session ({when})" not in text:
        FEEDBACK_LOG.write_text(text + "\n".join(lines), encoding="utf-8")
    return FEEDBACK_LOG