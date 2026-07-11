"""Comet CSV download runbook tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.csv_download import (  # noqa: E402
    cmd_collect,
    cmd_daily,
    cmd_hydrate,
    cmd_init,
    cmd_stage,
    infer_staged_destination,
    stage_file,
)
from whinfell_pipeline.staged_csv import staged_dataset_dir, staged_source_dir, SOURCE_BARCHART, SOURCE_CHINA, SOURCE_KOYFIN

EXAMPLES = REPO_ROOT / "whinfell_pipeline" / "examples" / "staged"


class TestCsvDownloadRouting(unittest.TestCase):
    def test_infer_koyfin_rates(self):
        self.assertEqual(infer_staged_destination("rates_20260627_1400.csv"), (SOURCE_KOYFIN, "rates"))

    def test_infer_barchart_intraday(self):
        self.assertEqual(
            infer_staged_destination("futures_intraday_20260627_1400.csv"),
            (SOURCE_BARCHART, "futures_intraday"),
        )

    def test_infer_china_policy(self):
        self.assertEqual(infer_staged_destination("china_policy_20260627_1400.csv"), (SOURCE_CHINA, None))


class TestCsvDownloadStage(unittest.TestCase):
    def test_copy_not_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "rates_20260627_1400.csv"
            src.write_text((EXAMPLES / "koyfin_rates_20260627_1400.csv").read_text(encoding="utf-8"), encoding="utf-8")
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "staged")
            self.assertTrue(src.exists(), "source download must remain after copy")
            dest = staged_dataset_dir(staged_root, SOURCE_KOYFIN, "rates") / src.name
            self.assertTrue(dest.exists())
            meta = dest.with_suffix(dest.suffix + ".meta.json")
            self.assertTrue(meta.exists())
            meta_data = json.loads(meta.read_text(encoding="utf-8"))
            self.assertEqual(meta_data["operator"], "test")
            self.assertEqual(meta_data["status"], "staged")

    def test_stage_flows_wide_csv_without_transform(self):
        flows_src = REPO_ROOT / "whinfell_pipeline" / "examples" / "flows" / "WTM-Flows-Global-head.csv"
        self.assertTrue(flows_src.is_file(), f"missing fixture {flows_src}")
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "flows_20260629_1017.csv"
            src.write_text(flows_src.read_text(encoding="utf-8"), encoding="utf-8")
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "staged", fr.errors)
            self.assertEqual(fr.dataset, "flows")
            dest = staged_dataset_dir(staged_root, SOURCE_KOYFIN, "flows") / src.name
            self.assertTrue(dest.exists())
            self.assertIn("Date", dest.read_text(encoding="utf-8"))

    def test_quarantine_bad_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            src = downloads / "bad-name.csv"
            src.write_text("a,b\n1,2\n", encoding="utf-8")
            cmd_init(staged_root)
            fr = stage_file(src, staged_root, operator="test")
            self.assertEqual(fr.status, "quarantined")
            self.assertTrue(src.exists())


class TestCsvDownloadChain(unittest.TestCase):
    def _seed_downloads(self, downloads: Path) -> None:
        for name in (
            "koyfin_rates_20260627_1400.csv",
            "barchart_futures_intraday_20260627_1400.csv",
            "china_policy_20260627_1400.csv",
        ):
            (downloads / name.replace("koyfin_", "").replace("barchart_", "")).write_text(
                (EXAMPLES / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def test_stage_manifest_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            downloads.mkdir()
            self._seed_downloads(downloads)
            result = cmd_stage(
                downloads_dir=downloads,
                staged_root=staged_root,
                operator="test",
                window="24h",
            )
            self.assertTrue(result.manifest_path)
            manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(manifest["manifest_type"], "stage")
            self.assertEqual(result.files_staged, 3)

    def test_daily_chain_collect_hydrate(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            hydrate_out = Path(tmp) / "hydration.json"
            g_out = Path(tmp) / "global.parquet"
            c_out = Path(tmp) / "china.parquet"
            downloads.mkdir()
            self._seed_downloads(downloads)

            result = cmd_daily(
                downloads_dir=downloads,
                staged_root=staged_root,
                operator="test",
                window="24h",
                export_path=None,
                hydrate_output=hydrate_out,
            )
            self.assertTrue(Path(result.manifest_path).exists())
            manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(manifest["manifest_type"], "daily")

            collect_code, _ = cmd_collect(
                staged_root,
                export_path=None,
            )
            self.assertIn(collect_code, (0, 1))

    def test_run_csv_download_cli_daily(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = Path(tmp) / "downloads"
            staged_root = Path(tmp) / "staged_raw"
            hydrate_out = Path(tmp) / "hydration.json"
            downloads.mkdir()
            self._seed_downloads(downloads)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "run_csv_download.py"),
                    "daily",
                    "--downloads",
                    str(downloads),
                    "--staged-root",
                    str(staged_root),
                    "--hydrate-output",
                    str(hydrate_out),
                    "--operator",
                    "cli-test",
                    "--window",
                    "24h",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertIn("csv_download_daily_ok", proc.stdout)
            self.assertTrue(hydrate_out.exists())
            bundle = json.loads(hydrate_out.read_text(encoding="utf-8"))
            self.assertIn("global", bundle)
            self.assertIn("suggested_tracer", bundle)


if __name__ == "__main__":
    unittest.main()