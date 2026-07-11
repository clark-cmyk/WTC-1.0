"""Tests for funds flow sponsorship builder and credit fallback — PR-2/PR-3b."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.tests.goal_scratch import goal_scratch

SCRATCH = goal_scratch()

from whinfell_pipeline.flows_fallback import merge_fallback_into_sidecar, parse_credit_cross_section_flows
from whinfell_pipeline.funds_flows import (
    apply_confidence_delta,
    build_funds_flows,
    build_flows_sidecar_metadata,
    load_flows_sidecar,
    merge_flow_rationale,
)
from whinfell_pipeline.hydrate import build_hydration_bundle
from whinfell_pipeline.node_cockpits import build_node_cockpit, build_node_cockpits


def _ticker_row(ticker: str, d1: float, d5: float, asset_id: str | None = None) -> dict:
    aid = asset_id or (ticker.lower() if ticker != "LQD" else "jaaa")
    return {
        "ticker": ticker,
        "asset_id": aid,
        "latest": {"date": "2026-06-29", "flow_pct_aum_1d": d1, "flow_usd_1d": d1 * 100},
        "rolling": {
            "flow_pct_aum_5d": d5,
            "flow_usd_5d": d5 * 100,
            "sessions_in_5d": 5,
            "persistence_score_20d": 0.65,
        },
    }


def _sidecar_from_tickers(rows: list[tuple[str, float, float]], *, ingest_mode: str = "timeseries_primary") -> dict:
    tickers = {t: _ticker_row(t, d1, d5) for t, d1, d5 in rows}
    return {
        "version": "1.0.0",
        "as_of": "2026-06-29",
        "source_file": "flows_20260629_1525.csv",
        "ingest_mode": ingest_mode,
        "tickers": tickers,
    }


def _supportive_credit_sidecar() -> dict:
    """Weighted 5D aggregate >= supportive_5d_pct (0.15); breadth 4/4 positive."""
    return _sidecar_from_tickers([
        ("HYG", 0.10, 0.40),
        ("LQD", 0.06, 0.22),
        ("BKLN", 0.05, 0.18),
        ("CWB", 0.04, 0.15),
    ])


def _partial_credit_sidecar() -> dict:
    """Primary timeseries with only 2/4 credit basket ETFs — triggers partial_basket."""
    return _sidecar_from_tickers([
        ("HYG", 0.08, 0.31),
        ("LQD", 0.02, 0.09),
    ])


def _credit_cockpit_draft() -> dict:
    """Node cockpit draft with bullish directional + RV for supportive overlay."""
    return {
        "node_id": "credit",
        "display_name": "Credit Confirmation",
        "confidence": "low",
        "as_of": "2026-06-29T15:00:00+00:00",
        "directional": {
            "posture": "long",
            "conviction": "medium",
            "rationale": "Credit horizons confirming risk-on transmission.",
        },
        "relative_value": {
            "posture": "long_spread",
            "conviction": "medium",
            "rationale": "Cheap vs history on HY OAS proxy.",
        },
        "rv_basis": {"richness_label": "cheap", "active_series_id": "hy_oas_proxy"},
    }


class TestFlowsFallback(unittest.TestCase):
    def test_parse_credit_cross_section(self):
        rows = [
            {"Ticker": "HYG", "AUM": "14500", "Fund Flows/Periodic (D)": "120.5"},
            {"Ticker": "LQD", "AUM": "42000", "Fund Flows/Periodic (D)": "45.0"},
            {"Ticker": "SPY", "AUM": "500000", "Fund Flows/Periodic (D)": "200"},
        ]
        parsed = parse_credit_cross_section_flows("", rows=rows)
        tickers = {r["ticker"] for r in parsed}
        self.assertEqual(tickers, {"HYG", "LQD"})
        hyg = next(r for r in parsed if r["ticker"] == "HYG")
        self.assertAlmostEqual(hyg["flow_pct_aum_1d"], (120.5 / 14500) * 100, places=3)

    def test_merge_fallback_into_sidecar_no_5d(self):
        rows = parse_credit_cross_section_flows(
            "",
            rows=[
                {"Ticker": "HYG", "AUM": "14500", "Fund Flows/Periodic (D)": "120.5"},
                {"Ticker": "LQD", "AUM": "42000", "Fund Flows/Periodic (D)": "45.0"},
            ],
        )
        sidecar = merge_fallback_into_sidecar(None, rows, as_of="2026-06-29")
        self.assertEqual(sidecar["ingest_mode"], "fallback_1d_only")
        self.assertTrue(sidecar["fallback_overlay"]["active"])
        hyg = sidecar["tickers"]["HYG"]
        self.assertIn("flow_pct_aum_1d", hyg["latest"])
        self.assertEqual(hyg.get("rolling"), {})
        self.assertNotIn("flow_pct_aum_5d", hyg.get("rolling", {}))


class TestFundsFlowsBuilder(unittest.TestCase):
    def test_build_credit_supportive_full(self):
        result = build_funds_flows(
            "credit",
            sidecar=_supportive_credit_sidecar(),
            node_cockpit=_credit_cockpit_draft(),
            as_of="2026-06-29",
        )
        self.assertTrue(result["enabled"])
        self.assertEqual(result["flows_meta"]["flows_status"], "ok")
        self.assertEqual(result["degrade_mode"], "full")
        self.assertEqual(result["aggregate"]["verdict"], "supportive")
        self.assertEqual(result["aggregate"]["confidence_delta"], 1)
        self.assertAlmostEqual(result["aggregate"]["flow_pct_aum_5d"], 0.264, places=2)
        primary = next(e for e in result["etfs"] if e["basket_role"] == "primary")
        self.assertEqual(primary["ticker"], "HYG")
        self.assertEqual(primary["data_status"], "ok")
        self.assertTrue(result["interpretation"]["supports_node_thesis"])
        self.assertEqual(result["interpretation"]["degrade_notice"], "")
        (SCRATCH / "funds_flows_sample.json").write_text(
            json.dumps(result, indent=2),
            encoding="utf-8",
        )

    def test_build_credit_partial_basket(self):
        result = build_funds_flows(
            "credit",
            sidecar=_partial_credit_sidecar(),
            node_cockpit=_credit_cockpit_draft(),
        )
        self.assertTrue(result["enabled"])
        self.assertEqual(result["flows_meta"]["flows_status"], "partial")
        self.assertEqual(result["degrade_mode"], "partial_basket")
        self.assertEqual(result["flows_meta"]["fallback_reason"], "missing_basket_etfs")
        self.assertEqual(result["aggregate"]["verdict"], "neutral")
        self.assertEqual(result["aggregate"]["confidence_delta"], 0)
        missing = [e for e in result["etfs"] if e["data_status"] == "missing"]
        self.assertEqual(len(missing), 2)
        self.assertEqual(
            result["interpretation"]["degrade_notice"],
            "Partial flow coverage — some basket ETFs missing from WTM-Flows.",
        )

    def test_build_credit_fallback_1d(self):
        rows = parse_credit_cross_section_flows(
            "",
            rows=[
                {"Ticker": "HYG", "AUM": "14500", "Fund Flows/Periodic (D)": "120.5"},
                {"Ticker": "LQD", "AUM": "42000", "Fund Flows/Periodic (D)": "45.0"},
            ],
        )
        sidecar = merge_fallback_into_sidecar(None, rows, as_of="2026-06-29")
        result = build_funds_flows("credit", sidecar=sidecar, node_cockpit=_credit_cockpit_draft())
        self.assertTrue(result["enabled"])
        self.assertEqual(result["flows_meta"]["flows_status"], "fallback_1d")
        self.assertEqual(result["degrade_mode"], "fallback_1d_credit")
        self.assertIsNone(result["aggregate"]["flow_pct_aum_5d"])
        self.assertIn(result["aggregate"]["verdict"], ("neutral", "mixed"))
        self.assertNotIn(result["aggregate"]["verdict"], ("supportive", "diverging"))
        self.assertEqual(result["aggregate"]["confidence_delta"], 0)
        self.assertEqual(result["flows_meta"]["flows_confidence_penalty"], 1)
        self.assertEqual(
            result["interpretation"]["degrade_notice"],
            "5D flows unavailable — using 1D Credit cross-section fallback.",
        )
        hyg = next(e for e in result["etfs"] if e["ticker"] == "HYG")
        self.assertEqual(hyg["data_status"], "partial_1d_only")

    def test_build_breadth_unavailable_without_sidecar(self):
        cockpit = build_node_cockpit(
            "breadth",
            global_payload={"whinfell_score": 65},
            horizon_marks={"d1": "up", "d5": "up", "d20": "flat", "d60": "flat"},
            as_of=datetime(2026, 6, 29, tzinfo=timezone.utc),
            freshness_status="fresh",
            flows_sidecar=None,
        )
        result = cockpit["funds_flows"]
        self.assertFalse(result["enabled"])
        self.assertEqual(result["flows_meta"]["flows_status"], "unavailable")
        self.assertEqual(result["flows_meta"]["fallback_reason"], "missing_wtm_flows_file")
        self.assertEqual(result["aggregate"]["verdict"], "neutral")
        self.assertEqual(result["aggregate"]["confidence_delta"], 0)

    def test_apply_confidence_delta_boosts_low_to_medium(self):
        funds = build_funds_flows(
            "credit",
            sidecar=_supportive_credit_sidecar(),
            node_cockpit=_credit_cockpit_draft(),
        )
        self.assertEqual(funds["aggregate"]["confidence_delta"], 1)
        self.assertEqual(funds["flows_meta"]["flows_confidence_penalty"], 0)
        self.assertEqual(apply_confidence_delta("low", funds), "medium")
        self.assertEqual(apply_confidence_delta("medium", funds), "high")

    def test_merge_flow_rationale_supportive_suffix(self):
        funds = build_funds_flows(
            "credit",
            sidecar=_supportive_credit_sidecar(),
            node_cockpit=_credit_cockpit_draft(),
        )
        self.assertEqual(funds["aggregate"]["verdict"], "supportive")
        merged = merge_flow_rationale("Base rationale.", funds)
        self.assertIn("Flows: supportive.", merged)
        self.assertIn("Base rationale.", merged)

    def test_sidecar_metadata_unavailable_when_missing(self):
        meta = build_flows_sidecar_metadata(None)
        self.assertEqual(meta["flows_status"], "unavailable")
        self.assertEqual(meta["ingest_mode"], "disabled")
        self.assertEqual(meta["ticker_count"], 0)


class TestNodeCockpitFundsWire(unittest.TestCase):
    def _tracer(self) -> dict[str, dict[str, str]]:
        return {nid: {"d1": "up", "d5": "up", "d20": "flat", "d60": "flat"} for nid in (
            "liquidity", "credit", "breadth", "highbeta", "basis"
        )}

    def test_confidence_delta_and_rationale_on_credit(self):
        as_of = datetime(2026, 6, 29, tzinfo=timezone.utc)
        baseline = build_node_cockpit(
            "credit",
            global_payload={"whinfell_score": 65, "transmission_state": "normal"},
            horizon_marks={"d1": "up", "d5": "up", "d20": "up", "d60": "flat"},
            as_of=as_of,
            freshness_status="fresh",
            flows_sidecar=None,
        )
        boosted = build_node_cockpit(
            "credit",
            global_payload={"whinfell_score": 65, "transmission_state": "normal"},
            horizon_marks={"d1": "up", "d5": "up", "d20": "up", "d60": "flat"},
            as_of=as_of,
            freshness_status="fresh",
            flows_sidecar=_supportive_credit_sidecar(),
        )
        self.assertEqual(baseline["confidence"], "low")
        self.assertEqual(boosted["confidence"], "medium")
        self.assertEqual(boosted["funds_flows"]["aggregate"]["verdict"], "supportive")
        self.assertEqual(boosted["funds_flows"]["aggregate"]["confidence_delta"], 1)
        self.assertIn("Flows: supportive.", boosted["directional"]["rationale"])

    def test_all_nodes_supportive_credit_sidecar_capture(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 65, "transmission_state": "normal"},
            suggested_tracer=self._tracer(),
            as_of=datetime(2026, 6, 29, tzinfo=timezone.utc),
            freshness_status="fresh",
            flows_sidecar=_supportive_credit_sidecar(),
        )
        credit_ff = cockpits["credit"]["funds_flows"]
        self.assertEqual(credit_ff["flows_meta"]["flows_status"], "ok")
        self.assertEqual(credit_ff["aggregate"]["verdict"], "supportive")
        self.assertEqual(credit_ff["aggregate"]["confidence_delta"], 1)
        (SCRATCH / "node_cockpits_funds.json").write_text(
            json.dumps({k: v.get("funds_flows") for k, v in cockpits.items()}, indent=2),
            encoding="utf-8",
        )

    def test_no_sidecar_unavailable_degrade(self):
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 65},
            suggested_tracer=self._tracer(),
            as_of=datetime(2026, 6, 29, tzinfo=timezone.utc),
            freshness_status="fresh",
            flows_sidecar=None,
        )
        self.assertEqual(cockpits["breadth"]["funds_flows"]["flows_meta"]["flows_status"], "unavailable")
        self.assertFalse(cockpits["breadth"]["funds_flows"]["enabled"])
        self.assertEqual(cockpits["breadth"]["funds_flows"]["aggregate"]["verdict"], "neutral")

    def test_fallback_credit_only(self):
        rows = parse_credit_cross_section_flows(
            "",
            rows=[{"Ticker": "HYG", "AUM": "14500", "Fund Flows/Periodic (D)": "120.5"}],
        )
        sidecar = merge_fallback_into_sidecar(None, rows, as_of="2026-06-29")
        cockpits = build_node_cockpits(
            global_payload={"whinfell_score": 65},
            suggested_tracer=self._tracer(),
            as_of=datetime(2026, 6, 29, tzinfo=timezone.utc),
            freshness_status="fresh",
            flows_sidecar=sidecar,
        )
        self.assertEqual(cockpits["credit"]["funds_flows"]["flows_meta"]["flows_status"], "fallback_1d")
        self.assertEqual(cockpits["breadth"]["funds_flows"]["flows_meta"]["flows_status"], "unavailable")

    def test_load_flows_sidecar_from_disk(self):
        sidecar = _supportive_credit_sidecar()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data" / "flows" / "v1" / "latest_flows.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(sidecar), encoding="utf-8")
            loaded = load_flows_sidecar(root)
            self.assertIsNotNone(loaded)
            meta = build_flows_sidecar_metadata(loaded)
            self.assertEqual(meta["ingest_mode"], "timeseries_primary")
            self.assertEqual(meta["ticker_count"], 4)


class TestHydrateFundsIntegration(unittest.TestCase):
    def test_hydration_bundle_always_has_flows_sidecar_block(self):
        bundle = build_hydration_bundle()
        self.assertIn("flows_sidecar", bundle)
        self.assertIn(
            bundle["flows_sidecar"]["flows_status"],
            ("ok", "partial", "unavailable", "fallback_1d"),
        )

    def test_live_hydrate_flows_status_ok(self):
        """Acceptance #2: representative flows data → credit funds_flows.flows_status exactly ok."""
        bundle = build_hydration_bundle()
        credit_ff = bundle["node_cockpits"]["credit"]["funds_flows"]
        self.assertEqual(credit_ff["flows_meta"]["flows_status"], "ok")
        self.assertEqual(credit_ff["flows_meta"]["flows_source"], "wtm_flows_timeseries")
        self.assertFalse(credit_ff["flows_meta"]["flows_degraded"])
        self.assertEqual(bundle["flows_sidecar"]["flows_status"], "ok")
        self.assertGreaterEqual(bundle["flows_sidecar"]["ticker_count"], 10)

    def test_hydration_bundle_with_sidecar_param(self):
        bundle = build_hydration_bundle(flows_sidecar=_supportive_credit_sidecar())
        self.assertEqual(bundle["flows_sidecar"]["flows_status"], "ok")
        self.assertEqual(bundle["flows_sidecar"]["ticker_count"], 4)
        credit = bundle["node_cockpits"]["credit"]["funds_flows"]
        self.assertTrue(credit["enabled"])
        self.assertEqual(credit["aggregate"]["verdict"], "supportive")

    def test_verification_plan_step5_cli_hydrate_twice_identical_ok(self):
        """Verification plan: CLI hydrate twice — ensure_flows_sidecar restores ok from fixture."""
        sidecar_path = REPO_ROOT / "data" / "flows" / "v1" / "latest_flows.json"
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        had_file = sidecar_path.is_file()
        prior = sidecar_path.read_text(encoding="utf-8") if had_file else None
        if sidecar_path.is_file():
            sidecar_path.unlink()

        out1 = SCRATCH / "hydration_v120.json"
        out2 = SCRATCH / "hydration_v120_run2.json"
        log_lines: list[str] = []
        cmd = [sys.executable, "-m", "whinfell_pipeline.hydrate"]

        try:
            for idx, out_path in enumerate((out1, out2), start=1):
                proc = subprocess.run(
                    [*cmd, "-o", str(out_path)],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log_lines.append(f"=== hydrate_cli_run_{idx} ===")
                log_lines.append(proc.stdout)
                if proc.stderr:
                    log_lines.append(proc.stderr)
                self.assertEqual(proc.returncode, 0, proc.stderr)

            bundle1 = json.loads(out1.read_text(encoding="utf-8"))
            bundle2 = json.loads(out2.read_text(encoding="utf-8"))
            self.assertEqual(bundle1, bundle2, "successive CLI hydrate outputs must be identical")

            for bundle in (bundle1, bundle2):
                self.assertEqual(bundle["hydration_version"], "1.2.0")
                self.assertIn("flows_sidecar", bundle)
                self.assertEqual(bundle["flows_sidecar"]["flows_status"], "ok")
                credit_ff = bundle["node_cockpits"]["credit"]["funds_flows"]
                self.assertIn("flows_meta", credit_ff)
                self.assertTrue(credit_ff["enabled"])
                self.assertEqual(credit_ff["flows_meta"]["flows_status"], "ok")
                self.assertEqual(credit_ff["flows_meta"]["flows_source"], "wtm_flows_timeseries")
                self.assertFalse(credit_ff["flows_meta"]["flows_degraded"])

            self.assertTrue(sidecar_path.is_file(), "ensure_flows_sidecar should recreate L1 sidecar")

            evidence_script = (
                "import json,sys\n"
                f"d=json.load(open({str(out1)!r}))\n"
                "print(d.get('hydration_version'))\n"
                "print(d['node_cockpits']['credit']['funds_flows']['flows_meta']['flows_status'])\n"
                "sys.stdout.flush()\n"
            )
            evidence = subprocess.run(
                [sys.executable, "-c", evidence_script],
                capture_output=True,
                text=True,
                check=False,
            )
            log_lines.append("=== evidence_step6 ===")
            log_lines.append(evidence.stdout)
            self.assertEqual(evidence.returncode, 0, evidence.stderr)
            evidence_lines = evidence.stdout.strip().splitlines()
            self.assertEqual(evidence_lines[0], "1.2.0")
            self.assertEqual(evidence_lines[1], "ok")

            (SCRATCH / "hydrate_v12.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        finally:
            if had_file and prior is not None:
                sidecar_path.write_text(prior, encoding="utf-8")
            elif sidecar_path.is_file():
                sidecar_path.unlink()


if __name__ == "__main__":
    unittest.main()