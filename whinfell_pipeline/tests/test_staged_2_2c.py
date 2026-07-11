"""Chunk 2.2c staged CSV folder + ingest integration tests."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.staged_csv import (
    BARCHART_DATASETS,
    KOYFIN_DATASETS,
    SOURCE_BARCHART,
    SOURCE_CHINA,
    SOURCE_KOYFIN,
    archive_staged_file,
    ingest_staged_root,
    init_staged_tree,
    scan_staged_root,
    staged_dataset_dir,
    staged_source_dir,
    validate_filename,
    validate_staged_file,
)

EXAMPLES = REPO_ROOT / "whinfell_pipeline" / "examples" / "staged"


class TestStagedLayout(unittest.TestCase):
    def test_init_creates_full_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_staged_tree(Path(tmp) / "staged_raw")
            for ds in BARCHART_DATASETS:
                self.assertTrue((staged_dataset_dir(root, SOURCE_BARCHART, ds) / "archived").is_dir())
            for ds in KOYFIN_DATASETS:
                self.assertTrue((staged_dataset_dir(root, SOURCE_KOYFIN, ds) / "archived").is_dir())
            self.assertTrue((staged_source_dir(root, SOURCE_CHINA) / "archived").is_dir())
            self.assertTrue((root / "README.md").exists())

    def test_filename_patterns(self):
        self.assertTrue(validate_filename("rates_20260627_1400.csv").ok)
        self.assertTrue(validate_filename("btc_basis_20260627.csv").ok)
        self.assertFalse(validate_filename("bad-name.csv").ok)


class TestStagedIngest(unittest.TestCase):
    def _seed_from_examples(self, root: Path) -> None:
        init_staged_tree(root)
        mapping = {
            "koyfin_rates_20260627_1400.csv": staged_dataset_dir(root, SOURCE_KOYFIN, "rates"),
            "barchart_futures_intraday_20260627_1400.csv": staged_dataset_dir(root, SOURCE_BARCHART, "futures_intraday"),
            "china_policy_20260627_1400.csv": staged_source_dir(root, SOURCE_CHINA),
        }
        for name, dest in mapping.items():
            src = EXAMPLES / name
            self.assertTrue(src.exists(), f"missing example {name}")
            (dest / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    def test_staged_ingest_to_parquet_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staged_raw"
            g_out = Path(tmp) / "global.parquet"
            c_out = Path(tmp) / "china.parquet"
            self._seed_from_examples(root)

            files = scan_staged_root(root)
            self.assertEqual(len(files), 3)
            for f in files:
                self.assertTrue(validate_staged_file(f).ok)

            result = ingest_staged_root(
                root,
                global_output=g_out,
                china_output=c_out,
                append=False,
                archive=True,
            )
            self.assertEqual(result.files_processed, 3)
            self.assertEqual(result.files_failed, 0)
            self.assertEqual(result.global_written, 1)
            self.assertEqual(result.china_written, 1)
            self.assertEqual(result.execution_records, 1)
            self.assertFalse(list(staged_dataset_dir(root, SOURCE_KOYFIN, "rates").glob("*.csv")))
            archived = list(staged_dataset_dir(root, SOURCE_KOYFIN, "rates").joinpath("archived").glob("*.csv"))
            self.assertEqual(len(archived), 1)
            self.assertTrue(g_out.exists())
            self.assertTrue(c_out.exists())
            self.assertEqual(pq.read_table(g_out).num_rows, 1)

    def test_ingest_cli_staged_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staged_raw"
            g_out = Path(tmp) / "global.parquet"
            self._seed_from_examples(root)
            proc = subprocess.run(
                [
                    sys.executable, "-m", "whinfell_pipeline.ingest",
                    "--staged", "--staged-root", str(root),
                    "--global-output", str(g_out),
                    "--no-append",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertIn("pipeline_staged_ingest_ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()