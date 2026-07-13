"""Tests for China Transmission Ladder v1.1."""

import unittest

from china_policy_track.china_ladder import (
    CANONICAL_STAGE_IDS,
    CHINA_FINAL_BANDS,
    CHINA_LADDER_FINAL_BANDS,
    CHINA_STAGE_MODELS,
    calculate_final_china_score,
    composite_stage_score,
    compute_raw_ladder_score,
    interpretation_band_for_final_score,
    score_china_ladder,
    sq3_multiplier,
    stage_health_band,
    stage_map_for_desk,
    weakest_stage,
)

FIXTURE_CHINA_HORIZONS = {
    "liquidity": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
    "credit": {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "down"},
    "breadth": {"d1": "up", "d5": "flat", "d20": "flat", "d60": "flat"},
    "highbeta": {"d1": "flat", "d5": "down", "d20": "flat", "d60": "flat"},
    "basis": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
}


class TestChinaLadderSQ3(unittest.TestCase):
    def test_multipliers(self):
        self.assertEqual(sq3_multiplier(85), 1.00)
        self.assertEqual(sq3_multiplier(70), 0.95)
        self.assertEqual(sq3_multiplier(55), 0.80)
        self.assertEqual(sq3_multiplier(40), 0.60)

    def test_calculate_final_strong(self):
        out = calculate_final_china_score(80, 82)
        self.assertEqual(out["multiplier"], 1.00)
        self.assertEqual(out["final_china_score"], 80)
        self.assertEqual(out["band"], "Strong")
        self.assertIn("aligned with ladder", out["desk_meaning"])

    def test_calculate_final_impaired(self):
        out = calculate_final_china_score(50, 45)
        self.assertEqual(out["multiplier"], 0.60)
        self.assertEqual(out["final_china_score"], 30)
        self.assertEqual(out["band"], "Impaired")
        self.assertIn("avoid new exposure", out["desk_meaning"])

    def test_clamp_final_score(self):
        out = calculate_final_china_score(100, 80)
        self.assertEqual(out["final_china_score"], 100)


class TestChinaLadderComposite(unittest.TestCase):
    def test_canonical_stage_ids_match_global(self):
        self.assertEqual(
            CANONICAL_STAGE_IDS,
            ("liquidity", "credit", "breadth", "highbeta", "basis"),
        )

    def test_flat_horizons_score_fifty(self):
        hz = {sid: {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "flat"} for sid in CANONICAL_STAGE_IDS}
        raw, stages = compute_raw_ladder_score(hz)
        self.assertEqual(raw, 50)
        self.assertTrue(all(v == 50 for v in stages.values()))

    def test_score_china_ladder_end_to_end(self):
        hz = {sid: {"d1": "up", "d5": "up", "d20": "up", "d60": "flat"} for sid in CANONICAL_STAGE_IDS}
        result = score_china_ladder(hz, sq3_score=54)
        self.assertGreater(result.raw_ladder_score, 50)
        self.assertEqual(result.multiplier, 0.80)
        self.assertEqual(
            result.final_china_score,
            int(round(result.raw_ladder_score * 0.80)),
        )

    def test_credit_marked_provisional(self):
        credit = next(r for r in stage_map_for_desk() if r["id"] == "credit")
        self.assertEqual(credit["status"], "provisional")
        self.assertIn("KHYB", credit["proxies"][0])


class TestWeakestStage(unittest.TestCase):
    def _fixture_rows(self):
        rows = []
        for sid in CANONICAL_STAGE_IDS:
            m = CHINA_STAGE_MODELS[sid]
            hz = FIXTURE_CHINA_HORIZONS[sid]
            net = sum(
                {"up": 1, "flat": 0, "down": -1}[hz[k]]
                for k in ("d1", "d5", "d20", "d60")
            )
            rows.append(
                {
                    "id": sid,
                    "name": m["name"],
                    "score": composite_stage_score(sid, FIXTURE_CHINA_HORIZONS),
                    "net": net,
                }
            )
        return rows

    def test_weakest_composite_fixture(self):
        w = weakest_stage(self._fixture_rows(), "composite")
        self.assertEqual(w.stage_id, "liquidity")
        self.assertEqual(w.value, 40)

    def test_weakest_net_can_differ_from_composite(self):
        rows = [
            {"id": "liquidity", "name": "Liquidity & Rates", "score": 60, "net": -2},
            {"id": "credit", "name": "Credit Confirmation", "score": 50, "net": 0},
        ]
        wc = weakest_stage(rows, "composite")
        wn = weakest_stage(rows, "net")
        self.assertEqual(wc.stage_id, "credit")
        self.assertEqual(wn.stage_id, "liquidity")

    def test_fixture_stage_scores(self):
        self.assertEqual(composite_stage_score("liquidity", FIXTURE_CHINA_HORIZONS), 40)
        self.assertEqual(composite_stage_score("breadth", FIXTURE_CHINA_HORIZONS), 56)
        self.assertEqual(stage_health_band(40)[0], "Broken")


class TestChinaFinalBands(unittest.TestCase):
    def test_band_table_locked(self):
        self.assertEqual(len(CHINA_LADDER_FINAL_BANDS), 4)
        self.assertEqual(CHINA_LADDER_FINAL_BANDS[0][2], "Strong")

    def test_interpretation_bands(self):
        self.assertEqual(interpretation_band_for_final_score(85).band, "Strong")
        self.assertEqual(interpretation_band_for_final_score(70).band, "Constructive")
        self.assertEqual(interpretation_band_for_final_score(55).band, "Mixed / Fragile")
        self.assertEqual(interpretation_band_for_final_score(30).band, "Impaired")

    def test_score_china_ladder_includes_band(self):
        hz = {sid: {"d1": "flat", "d5": "flat", "d20": "flat", "d60": "flat"} for sid in CANONICAL_STAGE_IDS}
        result = score_china_ladder(hz, sq3_score=54)
        self.assertEqual(result.raw_ladder_score, 50)
        self.assertEqual(result.final_china_score, 40)
        self.assertEqual(result.band, "Impaired")
        self.assertIn("avoid new exposure", result.desk_meaning)


if __name__ == "__main__":
    unittest.main()