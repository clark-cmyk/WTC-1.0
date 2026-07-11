"""Operator naming gate — driven by operator_alignment.enforcement in Master DD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.data_dictionary import (
    get_operator_alignment,
    operator_active_files,
    scan_operator_violations,
)


class TestOperatorNamingAlignment(unittest.TestCase):
    def test_enforcement_config_present(self):
        enf = get_operator_alignment()
        self.assertIn("active_globs", enf)
        self.assertIn("forbidden_patterns", enf)
        self.assertGreater(len(enf["active_globs"]), 5)
        self.assertGreater(len(enf["forbidden_patterns"]), 5)

    def test_active_globs_include_desk_chart_links(self):
        paths = [p.name for p in operator_active_files(REPO_ROOT)]
        self.assertTrue(any(n.startswith("desk_chart_links") for n in paths))

    def test_active_operator_files_no_legacy_navigation(self):
        violations = scan_operator_violations(REPO_ROOT)
        self.assertEqual(
            violations,
            [],
            "legacy names in active operator paths:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()