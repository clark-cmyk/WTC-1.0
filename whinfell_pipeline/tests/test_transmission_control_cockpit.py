"""Headless Transmission Control Phase 2 cockpit verification."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADLESS = REPO_ROOT / "whinfell_pipeline/tests/html_headless_cockpit.mjs"
HTML = REPO_ROOT / "08_Deliverables/Whinfell_Transmission_Control.html"
COCKPIT_BUNDLE = REPO_ROOT / "whinfell_pipeline/examples/cockpit_hydration_snippet.json"


class TestTransmissionControlCockpit(unittest.TestCase):
    def test_html_contains_cockpit_markers(self):
        text = HTML.read_text(encoding="utf-8")
        for marker in (
            'id="cockpitRvCanvas"',
            'id="cockpitFocusLayer"',
            'id="cockpitCompareLayer"',
            'id="btnHeresWhy"',
            'id="btnCompareMode"',
            "function drawRvBasisChart",
            "function toggleFocusMode",
            "function toggleCompareMode",
            "function setActiveNode",
            "function renderNodeCockpitShell",
            "function flipNode",
            "function renderFundsFlowSponsorshipCard",
            'id="hydrationBanner"',
            "function assessHydrationSession",
            "function renderHydrationBanner",
            "function maybePromptFirstHydrationImport",
            "TC_CONSOLE_BUILD",
            'id="tcConsoleBuildBadge"',
            "basis-summary",
            "function formatPercentile",
            "function formatOrdinalPercentile",
            "function buildBasisTacticalSentence",
            "function renderBasisImplicationRail",
            "MISSION_SURFACE_NODES",
            "function isMissionSurfaceNode",
            "function buildMissionTacticalLead",
            "function buildMissionChinaSuffix",
            "function buildMissionImplicationChips",
            "function resolveMissionGateChipLabel",
            "function renderMissionImplicationRail",
            'id="basisTacticalSuffix"',
            "Composite fallback",
            "horizon-net fallback",
            'id="basisSummaryStrip"',
            'id="basisTacticalBanner"',
            "__creditMissionProbe",
            "__liquidityMissionProbe",
            "__breadthMissionProbe",
            "__highbetaMissionProbe",
            "function runMissionSurfaceProbe",
            'id="btnTheme"',
            "function applyConsoleTheme",
            "function initConsoleTheme",
            "'liquidity'",
            'id="cockpitHorizonRow"',
            "header-instrument-stack",
            "node-coverage-banner--status-rail",
            "basis-reading-primary",
            "basis-tactical-banner",
            "basis-implication-rail",
            "operator-actions-strip",
            "2.2-UX-TIPS-2026-06-30",
            "renderMetricTips",
            'id="tipWhinfellScore"',
            'id="btnDeskDocs"',
            'id="deskDocsDrawer"',
            "DESK_DOC_CATALOG",
            'id="deskDocsPanel"',
            'id="headerLinkKoyfin"',
            'id="headerLinkBarchart"',
            "filterAuditRowsByScope",
            'id="cockpitRvTableWrap"',
            "metric-tip",
            "function buildSignalDiagnostics",
            "why-list--labeled",
            "hydration-session-degraded",
            'id="nodeCoverageBanner"',
            "function assessCockpitHydrationMode",
            "function buildNodeGateDecisionSentence",
            "function renderPostImportWorkflowStrip",
            'id="postImportWorkflow"',
            "node-coverage-banner--partial",
            ".gate-decision-sentence",
            ".funds-flow-card",
            ".funds-flow-etf-row",
            ".funds-flow-degrade-banner",
            ".funds-flow-verdict-supportive",
            'id="ingestProvenanceAudit"',
            "function renderIngestProvenanceAudit",
            "ingest-audit-table",
            "ingest_provenance",
        ):
            self.assertIn(marker, text, f"missing {marker}")

    def test_cockpit_hydration_snippet_present(self):
        self.assertTrue(COCKPIT_BUNDLE.is_file(), "cockpit hydration snippet missing")
        import json

        snippet = json.loads(COCKPIT_BUNDLE.read_text(encoding="utf-8"))
        self.assertIn("node_cockpits", snippet)
        self.assertEqual(set(snippet["node_cockpits"].keys()), {
            "liquidity", "credit", "breadth", "highbeta", "basis",
        })

    def test_headless_cockpit_flow_twice(self):
        if not HEADLESS.exists():
            self.skipTest("headless cockpit script missing")
        node = "node"
        for _ in range(2):
            proc = subprocess.run(
                [node, str(HEADLESS)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertIn("html_headless_cockpit_ok", proc.stdout)
            self.assertIn("drawRvBasisChart", proc.stdout)
            self.assertIn('"pointCount": 5', proc.stdout)
            self.assertIn("focusToggle", proc.stdout)
            self.assertIn("compareToggle", proc.stdout)
            self.assertIn("railRendered", proc.stdout)
            self.assertIn("fundsFlowCardRendered", proc.stdout)
            self.assertIn("creditMissionSurface", proc.stdout)
            self.assertIn("creditRvHorizonFallback", proc.stdout)
            self.assertIn("liquidityMissionSurface", proc.stdout)
            self.assertIn("breadthMissionSurface", proc.stdout)
            self.assertIn("highbetaMissionSurface", proc.stdout)
            self.assertIn("themeToggle", proc.stdout)
            self.assertIn("Composite fallback", proc.stdout)
            self.assertIn("horizon-net fallback", proc.stdout)
            self.assertIn("tacticalLead", proc.stdout)
            self.assertIn("tacticalSuffix", proc.stdout)
            self.assertIn("Tight + China Caution", proc.stdout)
            self.assertIn("ingestAudit", proc.stdout)


if __name__ == "__main__":
    unittest.main()