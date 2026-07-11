#!/usr/bin/env python3
"""Phase 2.2 Final E2E verifier — morning-style daily chain."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "whinfell_pipeline" / "examples" / "staged"


def _seed_downloads(downloads: Path) -> None:
    mapping = {
        "koyfin_rates_20260627_1400.csv": "rates_20260627_1400.csv",
        "barchart_futures_intraday_20260627_1400.csv": "futures_intraday_20260627_1400.csv",
        "china_policy_20260627_1400.csv": "china_policy_20260627_1400.csv",
    }
    for src_name, dest_name in mapping.items():
        (downloads / dest_name).write_text(
            (EXAMPLES / src_name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        downloads = Path(tmp) / "downloads"
        staged = Path(tmp) / "staged_raw"
        hydrate = Path(tmp) / "hydration.json"
        downloads.mkdir()

        _seed_downloads(downloads)
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "run_csv_download.py"),
                "daily",
                "--downloads",
                str(downloads),
                "--staged-root",
                str(staged),
                "--hydrate-output",
                str(hydrate),
                "--operator",
                "e2e-verify",
                "--window",
                "24h",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            errors.append(f"daily chain exit={proc.returncode}")
            errors.append(proc.stderr or proc.stdout)
        if "csv_download_daily_ok" not in proc.stdout:
            errors.append("missing csv_download_daily_ok")
        if not hydrate.exists():
            errors.append("hydration bundle missing")
        else:
            bundle = json.loads(hydrate.read_text(encoding="utf-8"))
            if bundle.get("global", {}).get("whinfell_score") is None:
                errors.append("missing whinfell_score in bundle")
            if not bundle.get("suggested_tracer"):
                errors.append("missing suggested_tracer")
            if bundle.get("tracer_apply_mode") != "confirm_required":
                errors.append("tracer_apply_mode not confirm_required")
            if not bundle.get("freshness_status"):
                errors.append("missing freshness_status")
        manifests = list((staged / "manifests").glob("daily_manifest__*.json"))
        if not manifests:
            errors.append("daily_manifest missing")

        html = (REPO_ROOT / "08_Deliverables" / "Whinfell_Transmission_Control.html").read_text(encoding="utf-8")
        for needle in (
            "Import Latest Hydration Bundle",
            "renderHydrationImportStatus",
            "hydrationImportStatus",
        ):
            if needle not in html:
                errors.append(f"HTML missing: {needle}")

        blueprint = REPO_ROOT / "08_Deliverables" / "Comet_Browser_Operations_Blueprint.md"
        if not blueprint.exists():
            errors.append("Comet_Browser_Operations_Blueprint.md missing")
        else:
            text = blueprint.read_text(encoding="utf-8")
            for needle in ("WTM-Rates-Credit", "wtm daily csv", "Supervised Comet Control Prompt", "Saved Prompts Utility Block"):
                if needle not in text:
                    errors.append(f"blueprint missing: {needle}")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "whinfell_pipeline.tests.test_csv_download", "whinfell_pipeline.tests.test_staged_2_2c"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if tests.returncode != 0:
        errors.append("unit tests failed")
        errors.append(tests.stdout[-2000:] if tests.stdout else tests.stderr)

    if errors:
        print("verify_2_2_final: FAIL")
        for e in errors:
            print(f"error={e}")
        return 1

    print("verify_2_2_final: PASS")
    print("chain=export_sim → stage → collect → hydrate → bundle_ok")
    print("html=Import Latest Hydration Bundle + status chip")
    print("docs=Comet_Browser_Operations_Blueprint.md + Operator Guide v1.4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())