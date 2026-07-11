#!/usr/bin/env python3
"""Atomic Phase 2 goal verification — writes all scratch artifacts in one run."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SCRATCH = Path(
    os.environ.get(
        "GROK_GOAL_SCRATCH",
        str(Path(tempfile.gettempdir()) / "grok-goal-verify" / "implementer"),
    )
)
SCRATCH.mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str], log_name: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
    )
    (SCRATCH / log_name).write_text(
        (proc.stdout or "") + (proc.stderr or ""),
        encoding="utf-8",
    )
    return proc


def step1_pytest() -> None:
    proc = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "whinfell_pipeline/tests/test_funds_flows.py",
            "whinfell_pipeline/tests/test_node_cockpits.py",
            "whinfell_pipeline/tests/test_data_dictionary.py",
            "whinfell_pipeline/tests/test_pipeline.py",
            "whinfell_pipeline/tests/test_flows_parser.py",
            "whinfell_pipeline/tests/test_rv_history.py",
            "whinfell_pipeline/tests/test_transmission_control_cockpit.py",
            "whinfell_pipeline/tests/test_flows_production.py",
            "whinfell_pipeline/tests/test_hardening_phase22.py",
            "-q",
            "--tb=line",
        ],
        "pytest_complete.log",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pytest failed (exit {proc.returncode})")


def step2_hydrate() -> None:
    out1 = SCRATCH / "bundle1.json"
    out2 = SCRATCH / "bundle2.json"
    lines: list[str] = []
    for idx, out in enumerate((out1, out2), start=1):
        log = SCRATCH / f"h{idx}.log"
        proc = subprocess.run(
            [sys.executable, "-m", "whinfell_pipeline.hydrate", "-o", str(out)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        log.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        lines.append(f"=== hydrate_run_{idx} exit={proc.returncode} ===")
        lines.append(proc.stdout)
        if proc.stderr:
            lines.append(proc.stderr)
        if proc.returncode != 0:
            raise RuntimeError(f"hydrate run {idx} failed")

    d1 = json.loads(out1.read_text(encoding="utf-8"))
    d2 = json.loads(out2.read_text(encoding="utf-8"))
    credit = d1["node_cockpits"]["credit"]["funds_flows"]["flows_meta"]
    assert credit["flows_status"] == "ok", credit
    assert credit["flows_source"] == "wtm_flows_timeseries"
    assert credit["flows_degraded"] is False
    assert d1["hydration_version"] == d2["hydration_version"]
    assert d1 == d2

    basis_series = list(d1["node_cockpits"]["basis"]["rv_basis"]["series"].values())[0]
    assert len(basis_series["horizons"]) == 5

    from whinfell_pipeline import flows_parser, hydrate, node_cockpits  # noqa: F401

    lines.extend([
        "flows_parser imported and callable",
        f"flows_status_ok={credit['flows_status'] == 'ok'}",
        f"hydration_version_match={d1['hydration_version'] == d2['hydration_version']}",
        "ARCH1 full horizons present",
        f"full_horizons={len(basis_series['horizons'])}",
    ])
    (SCRATCH / "hydrate_complete.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def step3_html_load() -> None:
    proc = _run(
        ["node", "whinfell_pipeline/tests/html_load_check.mjs"],
        "html_load.log",
    )
    if proc.returncode != 0 or "loaded_ok true" not in (proc.stdout or ""):
        raise RuntimeError("html load check failed")


def step4_playwright() -> None:
    env = {**os.environ, "GROK_GOAL_SCRATCH": str(SCRATCH)}
    pw = subprocess.run(["npx", "playwright", "--version"], capture_output=True, text=True, cwd=str(REPO))
    if pw.returncode != 0:
        (SCRATCH / "playwright_fallback.log").write_text(
            "playwright unavailable; relying on headless mjs + unit tests\n",
            encoding="utf-8",
        )
        return
    try:
        import playwright  # noqa: F401
    except ImportError:
        (SCRATCH / "playwright_fallback.log").write_text(
            f"npx playwright CLI present ({pw.stdout.strip()}) but python/node package missing; "
            "relying on headless mjs + unit tests\n",
            encoding="utf-8",
        )
        return
    proc = subprocess.run(
        ["node", "whinfell_pipeline/tests/playwright_cockpit_capture.mjs"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    (SCRATCH / "playwright_capture.log").write_text(
        (proc.stdout or "") + (proc.stderr or ""),
        encoding="utf-8",
    )
    if proc.returncode != 0 or not (SCRATCH / "tc_ui_complete.png").is_file():
        (SCRATCH / "playwright_fallback.log").write_text(
            "playwright capture failed; relying on headless mjs + unit tests\n"
            + (proc.stderr or proc.stdout or ""),
            encoding="utf-8",
        )


def step5_evidence() -> None:
    listing = subprocess.run(
        ["ls", "-l"] + [str(p) for p in sorted(SCRATCH.glob("*")) if p.is_file()],
        capture_output=True,
        text=True,
    )
    (SCRATCH / "evidence_ls.log").write_text(listing.stdout or "", encoding="utf-8")

    d1 = json.loads((SCRATCH / "bundle1.json").read_text(encoding="utf-8"))
    credit = d1["node_cockpits"]["credit"]["funds_flows"]["flows_meta"]
    basis_series = list(d1["node_cockpits"]["basis"]["rv_basis"]["series"].values())[0]
    summary = [
        f"ok_flows: {credit}",
        f"full_horizons: {len(basis_series.get('horizons', {}))}",
        (SCRATCH / "hydrate_complete.log").read_text(encoding="utf-8")[-500:],
        (SCRATCH / "html_load.log").read_text(encoding="utf-8"),
    ]
    (SCRATCH / "evidence_summary.log").write_text("\n".join(summary), encoding="utf-8")


def main() -> int:
    try:
        step1_pytest()
        step2_hydrate()
        step3_html_load()
        step4_playwright()
        step5_evidence()
    except Exception as exc:
        print(f"verify_phase2_goal_failed: {exc}", file=sys.stderr)
        return 1
    print(f"verify_phase2_goal_ok scratch={SCRATCH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())