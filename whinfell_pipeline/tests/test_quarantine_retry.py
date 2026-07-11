"""Quarantine retry — canonical + normalize paths."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.csv_download import cmd_init
from whinfell_pipeline.quarantine_retry import retry_quarantine_normalize


class TestQuarantineRetry(unittest.TestCase):
    def test_normalize_retry_stages_koyfin_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staged_raw"
            cmd_init(root)
            qdir = root / "quarantine" / "20260630"
            qdir.mkdir(parents=True, exist_ok=True)
            src = qdir / "130935__koyfin_2026-06-29 (2).csv"
            src.write_text(
                "Date,HYG Close,IWM Close\n06-30-2026,75,190\n",
                encoding="utf-8",
            )
            result = retry_quarantine_normalize(root, max_files=5)
            self.assertGreaterEqual(result.scanned, 1)
            self.assertGreaterEqual(result.staged, 1, result.errors)


if __name__ == "__main__":
    unittest.main()