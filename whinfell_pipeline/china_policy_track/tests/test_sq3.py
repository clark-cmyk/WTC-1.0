"""Tests for China Policy SQ3 scoring engine."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from china_policy_track.data_parser import parse_input
from china_policy_track.package_isolation import (
    PRODUCTION_MODULES,
    SQ3_BASE_REF,
    SQ3_RANGE_END,
    _shasum_hex_from_output,
    cat_file_shasum,
    git_show_shasum,
    parse_ls_tree_global,
    run_git_isolation_checks,
    scan_production_imports,
    verify_global_blob_parity,
    assert_sq3_deliverable_scope,
)
from china_policy_track.sq3 import (
    INTERPRETATION_BANDS,
    WEIGHT_GROWTH_MARKET,
    WEIGHT_POLICY_HIERARCHY,
    WEIGHT_STATE_CONTROL,
    calculate_sq3,
    interpret_sq3_band,
    normalize_state_control_impulse,
    score_from_mapping,
    score_input,
    score_observation,
)

VALID_BANDS = {label for _, _, label in INTERPRETATION_BANDS}


class TestSQ3Scoring(unittest.TestCase):
    def _load_perplexity_obs(self):
        text = (REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt").read_text()
        return parse_input(text)

    def _load_koyfin_obs(self):
        raw = json.loads(
            (REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text()
        )
        return parse_input(raw)

    def test_weights_sum_to_one(self):
        total = WEIGHT_POLICY_HIERARCHY + WEIGHT_STATE_CONTROL + WEIGHT_GROWTH_MARKET
        self.assertAlmostEqual(total, 1.0)

    def test_state_control_normalization_endpoints(self):
        self.assertEqual(normalize_state_control_impulse(100), 0.0)
        self.assertEqual(normalize_state_control_impulse(0), 50.0)
        self.assertEqual(normalize_state_control_impulse(-100), 100.0)

    def test_calculate_sq3_returns_bounded_score_and_band(self):
        result = calculate_sq3(policy_strength=74, state_impulse_score=38, growth_impulse_score=61)
        self.assertGreaterEqual(result.sq3_score, 0)
        self.assertLessEqual(result.sq3_score, 100)
        self.assertIn(result.interpretation_band, VALID_BANDS)
        self.assertEqual(result.interpretation_band, interpret_sq3_band(result.sq3_score))

    def test_score_observation_perplexity_sample(self):
        obs = self._load_perplexity_obs()
        first = score_observation(obs)
        second = score_observation(obs)
        self.assertGreaterEqual(first.sq3_score, 0)
        self.assertLessEqual(first.sq3_score, 100)
        self.assertTrue(first.interpretation_band)
        self.assertIn(first.interpretation_band, VALID_BANDS)
        self.assertEqual(first.sq3_score, second.sq3_score)
        self.assertEqual(first.interpretation_band, second.interpretation_band)

    def test_score_observation_koyfin_sample(self):
        obs = self._load_koyfin_obs()
        first = score_observation(obs)
        second = score_observation(obs)
        self.assertGreaterEqual(first.sq3_score, 0)
        self.assertLessEqual(first.sq3_score, 100)
        self.assertTrue(first.interpretation_band)
        self.assertEqual(first.sq3_score, second.sq3_score)
        self.assertEqual(first.interpretation_band, second.interpretation_band)

    def test_score_from_mapping_koyfin_dict(self):
        raw = json.loads(
            (REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text()
        )
        first = score_from_mapping(raw)
        second = score_from_mapping(raw)
        self.assertGreaterEqual(first.sq3_score, 0)
        self.assertLessEqual(first.sq3_score, 100)
        self.assertTrue(first.interpretation_band)
        self.assertIn(first.interpretation_band, VALID_BANDS)
        self.assertEqual(first.sq3_score, second.sq3_score)
        self.assertEqual(first.interpretation_band, second.interpretation_band)

    def test_score_from_mapping_observation_object(self):
        obs = self._load_perplexity_obs()
        result = score_from_mapping(obs)
        self.assertGreaterEqual(result.sq3_score, 0)
        self.assertLessEqual(result.sq3_score, 100)
        self.assertTrue(result.interpretation_band)
        self.assertEqual(result.sq3_score, score_observation(obs).sq3_score)

    def test_score_input_end_to_end(self):
        text = (REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt").read_text()
        raw = json.loads(
            (REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text()
        )
        for payload in (text, raw):
            a = score_input(payload)
            b = score_input(payload)
            d = a.to_dict()
            self.assertIn("sq3_score", d)
            self.assertIn("interpretation_band", d)
            self.assertGreaterEqual(d["sq3_score"], 0)
            self.assertLessEqual(d["sq3_score"], 100)
            self.assertTrue(d["interpretation_band"])
            self.assertEqual(a.sq3_score, b.sq3_score)
            self.assertEqual(a.interpretation_band, b.interpretation_band)

    def test_result_dict_includes_audit_components(self):
        obs = self._load_perplexity_obs()
        d = score_observation(obs).to_dict()
        self.assertAlmostEqual(
            d["weights"]["policy_hierarchy"] + d["weights"]["state_control"] + d["weights"]["growth_market"],
            1.0,
        )
        self.assertIn("components", d)
        self.assertIn("normalized_inputs", d)

    def test_sq3_git_isolation(self):
        """Subprocess git checks: SQ3 did not modify Global paths; blob shasums match ls-tree."""
        checks = run_git_isolation_checks(REPO_ROOT)
        by_cmd = {cmd: out for cmd, out in checks}

        china_cmd = next(
            c
            for c in by_cmd
            if c.startswith("git diff --name-only")
            and c.endswith("-- china_policy_track/")
        )
        china_paths = [p for p in by_cmd[china_cmd].splitlines() if p.strip()]
        self.assertTrue(china_paths, "expected china_policy_track changes in SQ3 deliverable scope")
        for path in china_paths:
            self.assertTrue(path.startswith("china_policy_track/"), path)

        scope_paths = assert_sq3_deliverable_scope(REPO_ROOT)
        self.assertEqual(set(scope_paths), set(china_paths))

        ls_ds_cmd = "git ls-files .DS_Store"
        self.assertEqual(by_cmd[ls_ds_cmd].strip(), "")

        score_diff = next(c for c in by_cmd if "04_Score_Calculation/" in c and "diff " in c)
        global_diff = next(c for c in by_cmd if "data/global/" in c and "diff " in c and "name-only" not in c)
        self.assertEqual(by_cmd[score_diff].strip(), "")
        self.assertEqual(by_cmd[global_diff].strip(), "")

        base_tree_cmd = f"git ls-tree -r {SQ3_BASE_REF} -- data/global/"
        head_tree_cmd = f"git ls-tree -r {SQ3_RANGE_END} -- data/global/"
        base_entries = parse_ls_tree_global(by_cmd[base_tree_cmd])
        head_entries = parse_ls_tree_global(by_cmd[head_tree_cmd])
        self.assertEqual(base_entries, head_entries)

        parity = verify_global_blob_parity(REPO_ROOT)
        self.assertGreaterEqual(len(parity), 1)

        for repo_path, blob_oid in head_entries.items():
            _, base_out = git_show_shasum(SQ3_BASE_REF, repo_path, REPO_ROOT)
            _, head_out = git_show_shasum(SQ3_RANGE_END, repo_path, REPO_ROOT)
            _, cat_out = cat_file_shasum(blob_oid, REPO_ROOT)
            base_hex = _shasum_hex_from_output(base_out)
            head_hex = _shasum_hex_from_output(head_out)
            cat_hex = _shasum_hex_from_output(cat_out)
            self.assertEqual(base_hex, head_hex)
            self.assertEqual(base_hex, cat_hex)
            self.assertEqual(base_hex, parity[repo_path]["shasum"])
            self.assertEqual(blob_oid, parity[repo_path]["blob_oid"])

            show_cmd = f"git show {SQ3_RANGE_END}:{repo_path} | shasum"
            cat_cmd = f"git cat-file -p {blob_oid} | shasum"
            self.assertEqual(_shasum_hex_from_output(by_cmd[show_cmd]), base_hex)
            self.assertEqual(_shasum_hex_from_output(by_cmd[cat_cmd]), base_hex)

    def test_sq3_package_isolated_from_global(self):
        """Full production package must not import Global score logic; scoring must not touch data/global/."""
        import china_policy_track
        from china_policy_track.package_isolation import global_data_files

        for module_name in PRODUCTION_MODULES:
            self.assertTrue(
                (REPO_ROOT / "china_policy_track" / module_name).exists(),
                f"missing production module: {module_name}",
            )

        hits = scan_production_imports()
        self.assertEqual(hits, [], f"forbidden imports found: {hits}")

        # Drive real public package import path (not only sq3.py in isolation).
        self.assertTrue(hasattr(china_policy_track, "score_input"))
        self.assertTrue(hasattr(china_policy_track, "calculate_sq3"))

        mtimes_before = {p: p.stat().st_mtime for p in global_data_files()}

        text = (REPO_ROOT / "china_policy_track/examples/sample_perplexity_export.txt").read_text()
        raw = json.loads(
            (REPO_ROOT / "china_policy_track/examples/sample_koyfin_export.json").read_text()
        )
        for payload in (text, raw):
            china_policy_track.score_input(payload)

        for path, mtime in mtimes_before.items():
            self.assertEqual(path.stat().st_mtime, mtime, f"SQ3 scoring modified {path}")


if __name__ == "__main__":
    unittest.main()