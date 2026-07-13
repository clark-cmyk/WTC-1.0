"""Verify generated desk_china_ladder_models.js matches china_ladder.py."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from china_policy_track.china_ladder import china_ladder_js_spec
from whinfell_pipeline.desk_china_ladder_models import write_desk_china_ladder_models

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_JS = REPO_ROOT / "08_Deliverables/desk_china_ladder_models.js"


def _parse_js_spec(text: str) -> dict:
    match = re.search(r"const CHINA_LADDER_SPEC = (\{.*?\});\n", text, re.DOTALL)
    if not match:
        raise ValueError("CHINA_LADDER_SPEC not found in generated JS")
    return json.loads(match.group(1))


class TestChinaLadderJsSync(unittest.TestCase):
    def test_generated_js_matches_python_spec(self):
        write_desk_china_ladder_models(OUT_JS)
        py_spec = china_ladder_js_spec()
        js_spec = _parse_js_spec(OUT_JS.read_text(encoding="utf-8"))
        self.assertEqual(py_spec, js_spec)

    def test_js_file_has_version_header(self):
        text = OUT_JS.read_text(encoding="utf-8")
        self.assertIn("AUTO-GENERATED", text)
        self.assertIn("china_ladder.v1.1", text)
        self.assertIn("compositeChinaStageScore", text)
        self.assertIn("weakestStage", text)


if __name__ == "__main__":
    unittest.main()