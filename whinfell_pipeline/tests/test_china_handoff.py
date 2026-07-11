"""Phase 2 China handoff — export, Grok, and cross-surface parity tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from china_policy_track.china_ladder import (
    CHINA_STAGE_MODELS,
    score_china_ladder,
    weakest_stage,
    composite_stage_score,
    HZ_SCORE,
    CANONICAL_STAGE_IDS,
)
from whinfell_pipeline.export_contract import (
    build_china_ladder_export_v11,
    build_wtm_export_v21,
    parse_china_ladder_export_v11,
    parse_wtm_export_v21,
)
from whinfell_pipeline.hydrate import build_hydration_bundle

FIXTURE_CHINA_HORIZONS = {
    "liquidity": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
    "credit": {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "down"},
    "breadth": {"d1": "up", "d5": "flat", "d20": "flat", "d60": "flat"},
    "highbeta": {"d1": "flat", "d5": "down", "d20": "flat", "d60": "flat"},
    "basis": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
}
FIXTURE_SQ3 = 54

HEADLESS = REPO_ROOT / "whinfell_pipeline/tests/china_handoff_headless.mjs"


def _fixture_rows():
    rows = []
    for sid in CANONICAL_STAGE_IDS:
        hz = FIXTURE_CHINA_HORIZONS[sid]
        net = sum(HZ_SCORE.get(hz[k], 0) for k in ("d1", "d5", "d20", "d60"))
        rows.append(
            {
                "id": sid,
                "name": CHINA_STAGE_MODELS[sid]["name"],
                "score": composite_stage_score(sid, FIXTURE_CHINA_HORIZONS),
                "net": net,
            }
        )
    return rows


def _kernel_read():
    result = score_china_ladder(FIXTURE_CHINA_HORIZONS, FIXTURE_SQ3)
    weakest = weakest_stage(_fixture_rows(), "composite")
    return {
        "raw": result.raw_ladder_score,
        "final": result.final_china_score,
        "band": result.band,
        "sq3": result.sq3_score,
        "weakest_stage": weakest.name,
        "weakest_score": weakest.value,
    }


class TestChinaLadderExportBlock(unittest.TestCase):
    def test_build_parse_roundtrip_matches_kernel(self):
        kernel = _kernel_read()
        block = build_china_ladder_export_v11(FIXTURE_CHINA_HORIZONS, FIXTURE_SQ3)
        self.assertIn("CHINA LADDER EXPORT v1.1", block)
        parsed = parse_china_ladder_export_v11(block)
        self.assertEqual(parsed.china_raw_score, kernel["raw"])
        self.assertEqual(parsed.china_final_score, kernel["final"])
        self.assertEqual(parsed.china_final_band, kernel["band"])
        self.assertEqual(parsed.sq3_policy_score, kernel["sq3"])
        self.assertEqual(parsed.weakest_china_stage, kernel["weakest_stage"])
        self.assertTrue(parsed.key_china_observation)

    def test_wtm_export_appends_china_ladder_block(self):
        combined = build_wtm_export_v21(
            global_data={"whinfell_score": 58, "transmission_state": "stressed", "regime_tag": "Test"},
            china_data={"sq3_score": FIXTURE_SQ3, "sq3_band": "Mixed / Fragile"},
            china_ladder_horizons=FIXTURE_CHINA_HORIZONS,
            include_provenance=False,
            include_tracer=False,
        )
        self.assertIn("WTM EXPORT v2.1", combined)
        self.assertIn("CHINA LADDER EXPORT v1.1", combined)
        parsed = parse_wtm_export_v21(combined)
        self.assertIsNotNone(parsed.china_ladder)
        kernel = _kernel_read()
        self.assertEqual(parsed.china_ladder.china_raw_score, kernel["raw"])
        self.assertEqual(parsed.china_ladder.china_final_score, kernel["final"])
        self.assertEqual(parsed.china_ladder.weakest_china_stage, kernel["weakest_stage"])

    def test_hydration_bundle_wtm_includes_china_ladder_when_china_present(self):
        bundle = build_hydration_bundle()
        if not bundle.get("china"):
            self.skipTest("no china parquet row")
        wtm = bundle.get("wtm_export_v21", "")
        if not bundle.get("china_ladder", {}).get("horizons"):
            self.skipTest("no china_ladder horizons in bundle")
        self.assertIn("CHINA LADDER EXPORT v1.1", wtm)
        parsed = parse_china_ladder_export_v11(wtm)
        hz = bundle["china_ladder"]["horizons"]
        sq3 = bundle["china_ladder"].get("sq3_score") or bundle["china"].get("sq3_score")
        kernel = score_china_ladder(hz, int(sq3))
        rows = []
        for sid in CANONICAL_STAGE_IDS:
            hz_s = hz.get(sid, {})
            net = sum(HZ_SCORE.get(str(hz_s.get(k, "flat")).lower(), 0) for k in ("d1", "d5", "d20", "d60"))
            rows.append(
                {
                    "id": sid,
                    "name": CHINA_STAGE_MODELS[sid]["name"],
                    "score": composite_stage_score(sid, hz),
                    "net": net,
                }
            )
        weakest = weakest_stage(rows, "composite")
        self.assertEqual(parsed.china_raw_score, kernel.raw_ladder_score)
        self.assertEqual(parsed.china_final_score, kernel.final_china_score)
        self.assertEqual(parsed.weakest_china_stage, weakest.name)


class TestChinaHandoffHeadless(unittest.TestCase):
    def test_tc_deep_dive_grok_export_parity(self):
        if not HEADLESS.exists():
            self.skipTest("china_handoff_headless.mjs missing")
        proc = subprocess.run(
            ["node", str(HEADLESS)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("china_handoff_headless_ok", proc.stdout)
        payload = json.loads(proc.stdout.strip().split("\n")[-1])
        kernel = _kernel_read()
        self.assertEqual(payload["kernel"]["raw"], kernel["raw"])
        self.assertEqual(payload["kernel"]["final"], kernel["final"])
        self.assertEqual(payload["kernel"]["band"], kernel["band"])
        self.assertEqual(payload["kernel"]["weakest_stage"], kernel["weakest_stage"])
        self.assertEqual(payload["tc_cluster"]["raw"], kernel["raw"])
        self.assertEqual(payload["tc_cluster"]["final"], kernel["final"])
        self.assertEqual(payload["tc_cluster"]["weakest_stage"], kernel["weakest_stage"])
        self.assertEqual(payload["deep_dive"]["raw"], kernel["raw"])
        self.assertEqual(payload["deep_dive"]["final"], kernel["final"])
        self.assertEqual(payload["deep_dive"]["weakest_stage"], kernel["weakest_stage"])
        self.assertEqual(payload["grok"]["china_ladder"]["raw"], kernel["raw"])
        self.assertEqual(payload["grok"]["china_ladder"]["final"], kernel["final"])
        self.assertEqual(payload["grok"]["china_ladder"]["band"], kernel["band"])
        self.assertEqual(payload["grok"]["china_ladder"]["weakest_stage"], kernel["weakest_stage"])
        self.assertEqual(payload["grok"]["china_ladder"]["sq3_score"], kernel["sq3"])
        self.assertIn("CHINA LADDER EXPORT v1.1", payload["wtm_export"])
        self.assertIn(f"China Raw Score: {kernel['raw']}", payload["wtm_export"])
        self.assertIn(f"Weakest China Stage: {kernel['weakest_stage']}", payload["wtm_export"])


if __name__ == "__main__":
    unittest.main()