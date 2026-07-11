"""Tests for Phase 2 node cockpit builder and WTM EXPORT v2.2."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.export_contract import build_node_cockpit_export_block, build_wtm_export_v22
from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.node_cockpits import (
    CANONICAL_NODE_IDS,
    build_cockpit_context,
    build_node_cockpit,
    build_node_cockpits,
)
from whinfell_pipeline.version import DECISION_EXPORT_FORMAT_V22, NODE_COCKPIT_EXPORT_PREFIX


class TestNodeCockpits(unittest.TestCase):
    def _sample_tracer(self) -> dict[str, dict[str, str]]:
        return {
            "liquidity": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
            "credit": {"d1": "down", "d5": "down", "d20": "flat", "d60": "flat"},
            "breadth": {"d1": "up", "d5": "up", "d20": "flat", "d60": "flat"},
            "highbeta": {"d1": "down", "d5": "down", "d20": "flat", "d60": "flat"},
            "basis": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
        }

    def test_build_all_five_nodes(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed", "key_observation": "Credit mixed."},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, 14, 0, 0, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        self.assertEqual(set(cockpits.keys()), set(CANONICAL_NODE_IDS))
        for node_id in CANONICAL_NODE_IDS:
            cockpit = cockpits[node_id]
            self.assertEqual(cockpit["node_id"], node_id)
            self.assertIn("composite_score", cockpit)
            self.assertIn(cockpit["composite_score_source"], ("weighted_components", "horizon_net_fallback"))
            self.assertIn("directional", cockpit)
            self.assertIn("relative_value", cockpit)
            self.assertIn("rv_basis", cockpit)
            self.assertGreaterEqual(len(cockpit["implementations"]), 1)

    def test_liquidity_can_use_weighted_components_with_history(self):
        from whinfell_pipeline.rv_history import ensure_dated_series_fixture, load_rv_history

        ensure_dated_series_fixture(REPO_ROOT, sessions=120)
        history = load_rv_history(REPO_ROOT)
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed"},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 30, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            spread_history=history,
        )
        liq = cockpits["liquidity"]
        live = [c for c in liq["component_inputs"] if c.get("source") == "rv_history"]
        if live:
            self.assertIn(liq["composite_score_source"], ("weighted_components", "horizon_net_fallback"))

    def test_credit_uses_horizon_fallback(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 50},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        credit = cockpits["credit"]
        self.assertEqual(credit["composite_score_source"], "horizon_net_fallback")
        self.assertEqual(credit["horizon_net"], -2)

    def test_weakest_link_tiebreak(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 50},
            suggested_tracer={
                nid: {"d1": "down", "d5": "down", "d20": "down", "d60": "down"}
                for nid in CANONICAL_NODE_IDS
            },
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            spread_history={},
        )
        weakest = [nid for nid, c in cockpits.items() if c["is_weakest_link"]]
        self.assertEqual(weakest, ["liquidity"])

    def test_basis_rv_from_execution(self):
        cockpit = build_node_cockpit(
            "basis",
            global_payload={"whinfell_score": 58, "transmission_state": "normal"},
            horizon_marks={"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            execution={"basis_spread": "1.25", "near_month": "Jul", "far_month": "Dec"},
        )
        self.assertIn("1.25", cockpit["key_observation"])
        self.assertEqual(cockpit["rv_basis"]["active_series_id"], "btc_calendar_bt_near_deferred")

    def test_china_parallel_soft_coupling(self):
        china_ladder = {
            "horizons": {
                "basis": {"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
            }
        }
        cockpit = build_node_cockpit(
            "basis",
            global_payload={"whinfell_score": 58},
            horizon_marks={"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            china_ladder=china_ladder,
        )
        self.assertTrue(cockpit["china_parallel"]["present"])
        self.assertEqual(cockpit["china_parallel"]["horizon_net"], -1)

    def test_cockpit_context(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed"},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        ctx = build_cockpit_context(global_payload={"whinfell_score": 58, "transmission_state": "stressed"}, node_cockpits=cockpits)
        self.assertIn(ctx["weakest_node_id"], CANONICAL_NODE_IDS)
        self.assertEqual(ctx["whinfell_score"], 58)

    def test_export_block_roundtrip_labels(self):
        cockpit = build_node_cockpit(
            "basis",
            global_payload={"whinfell_score": 42, "btc_bias": "Neutral"},
            horizon_marks={"d1": "flat", "d5": "flat", "d20": "down", "d60": "flat"},
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
            execution={"basis_spread": "1.25"},
        )
        block = build_node_cockpit_export_block(cockpit)
        self.assertIn(f"--- {NODE_COCKPIT_EXPORT_PREFIX}: Basis & Term Structure ---", block)
        self.assertIn("Node ID: basis", block)
        self.assertIn("Composite Score Source:", block)
        self.assertIn("RV Direction: higher_is_richer", block)
        self.assertIn("Key Observation:", block)

    def test_export_block_includes_funds_flow_lines(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed"},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        block = build_node_cockpit_export_block(cockpits["credit"])
        self.assertIn("Funds Flow Verdict:", block)
        self.assertIn("Funds Flow Status:", block)
        self.assertIn("Funds Flow Summary:", block)

    def test_wtm_export_v22_includes_all_nodes(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed", "regime_tag": "Test"},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        block = build_wtm_export_v22(
            global_data={"whinfell_score": 58, "transmission_state": "stressed", "regime_tag": "Test"},
            node_cockpits=cockpits,
            include_provenance=False,
        )
        self.assertIn(DECISION_EXPORT_FORMAT_V22, block)
        self.assertEqual(block.count(f"--- {NODE_COCKPIT_EXPORT_PREFIX}:"), 5)

    def test_hydration_bundle_includes_node_cockpits(self):
        bundle = build_hydration_bundle()
        self.assertEqual(bundle["hydration_version"], "1.2.0")
        self.assertIn("node_cockpits", bundle)
        self.assertIn("cockpit_context", bundle)
        self.assertIn("wtm_export_v22", bundle)
        self.assertIn("ingest_provenance", bundle)
        self.assertEqual(set(bundle["node_cockpits"].keys()), set(CANONICAL_NODE_IDS))
        self.assertIn(DECISION_EXPORT_FORMAT_V22, bundle["wtm_export_v22"])
        self.assertIn("WTM EXPORT v2.1", bundle["wtm_export_v21"])
        credit = bundle["node_cockpits"]["credit"]
        self.assertIn("funds_flows", credit)
        self.assertIn("flows_meta", credit["funds_flows"])
        self.assertIn("flows_sidecar", bundle)
        sidecar_path = REPO_ROOT / "data" / "flows" / "v1" / "latest_flows.json"
        expected_flows = "ok" if sidecar_path.is_file() else "unavailable"
        self.assertEqual(bundle["flows_sidecar"]["flows_status"], expected_flows)

    def test_funds_flows_on_all_nodes(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 58, "transmission_state": "stressed"},
            suggested_tracer=self._sample_tracer(),
            as_of=__import__("datetime").datetime(2026, 6, 27, 14, 0, 0, tzinfo=__import__("datetime").timezone.utc),
            freshness_status="fresh",
        )
        for node_id in CANONICAL_NODE_IDS:
            self.assertIn("funds_flows", cockpits[node_id])
            self.assertIn("flows_meta", cockpits[node_id]["funds_flows"])


if __name__ == "__main__":
    unittest.main()