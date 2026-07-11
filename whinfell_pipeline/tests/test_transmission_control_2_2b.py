"""Headless Transmission Control 2.2b hybrid tracer verification."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADLESS = REPO_ROOT / "whinfell_pipeline/tests/html_headless_2_2b.mjs"
HTML = REPO_ROOT / "08_Deliverables/Whinfell_Transmission_Control.html"


class TestTransmissionControl22b(unittest.TestCase):
    def test_html_contains_hybrid_tracer_markers(self):
        text = HTML.read_text(encoding="utf-8")
        for marker in (
            'id="suggestedTracerPanel"',
            'id="tracerHorizonBody"',
            'data-panel="prompts"',
            'class="hz-select',
            "Manual Override",
            "Operator Confirmed",
            "progressive-disclosure",
            "disclosure-panel",
            "applySuggestedMarks",
            "applyIntakeOverride",
            "applyHorizonOverride",
            "getTracerChrome",
            "getTracerFlowState",
        ):
            self.assertIn(marker, text, f"missing {marker}")

    def test_headless_hybrid_tracer_flow_twice(self):
        if not HEADLESS.exists():
            self.skipTest("headless script missing")
        node = "node"
        for attempt in range(2):
            proc = subprocess.run(
                [node, str(HEADLESS)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertIn("html_headless_2_2b_ok", proc.stdout)
            self.assertIn("Operator Confirmed", proc.stdout)
            self.assertIn("Manual Override", proc.stdout)
            self.assertIn("provenanceNote", proc.stdout)
            self.assertIn("horizonSetsManualOverride", proc.stdout)
            self.assertIn("testPureTransitions", proc.stdout)
            self.assertIn("testNonHydratedHorizonDom", proc.stdout)
            self.assertIn("dryHorizonSetsManualOverride", proc.stdout)
            self.assertIn("horizon-only override", proc.stdout)
            self.assertIn("decoupled intake", proc.stdout)
            self.assertIn("applyIntakeOverride", proc.stdout)
            self.assertIn("applyHorizonOverride", proc.stdout)
            self.assertIn('"provenanceNote": "Manual override active"', proc.stdout)


if __name__ == "__main__":
    unittest.main()