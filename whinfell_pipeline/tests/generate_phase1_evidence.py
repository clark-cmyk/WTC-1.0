#!/usr/bin/env python3
"""Generate Phase 1 verification artifacts for goal scratch dir."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path(
    os.environ.get(
        "PHASE1_SCRATCH",
        "/var/folders/qn/gdsdhg9j3f77wk7fn889zbq40000gn/T/grok-goal-0eb820e2edd0/implementer",
    )
)
SCRATCH.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO))

from whinfell_pipeline.batch_collect import infer_canonical_name, normalize_drop_dir
from whinfell_pipeline.data_dictionary import (
    badge_default_payload,
    load_data_dictionary,
    master_dictionary_info,
    scan_operator_violations,
)
from whinfell_pipeline.sync_dictionary_meta import (
    DD_BADGE_SYNC_END,
    DD_BADGE_SYNC_START,
    META_JSON,
    TC_HTML,
    build_meta_payload,
    sync_all,
)


def run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def write_dd_v1() -> None:
    dd = load_data_dictionary()
    info = master_dictionary_info(dd)
    sections = [
        "master_data_dictionary",
        "project_structure",
        "watchlist_names",
        "file_naming_conventions",
        "json_structures",
        "column_mappings",
        "ticker_standards",
        "operator_alignment",
    ]
    lines = [
        f"=== Master Data Dictionary v1.0 excerpts ===",
        f"captured: {datetime.now(timezone.utc).isoformat()}",
        f"version: {info['version']}",
        f"date: {info['date']}",
        f"status: {info['status']}",
        f"alignment: {info['alignment']}",
        f"machine_registry: whinfell_pipeline/data_dictionary.yaml",
        "",
        "required_sections_present:",
    ]
    for key in sections:
        present = key in dd or (key == "master_data_dictionary" and "master_data_dictionary" in dd)
        lines.append(f"  - {key}: {'yes' if present else 'MISSING'}")
    lines.extend(
        [
            "",
            "watchlist_names (canonical):",
        ]
    )
    for row in (dd.get("watchlist_names") or {}).get("canonical_saved_views") or []:
        if isinstance(row, dict):
            lines.append(f"  - {row.get('name', row)}")
    lines.extend(
        [
            "",
            "json_structures.hydration_bundle.expected_version:",
            str((dd.get("json_structures") or {}).get("hydration_bundle", {}).get("expected_version")),
        ]
    )
    (SCRATCH / "dd_v1.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_phased_plan() -> None:
    plan = REPO / "08_Deliverables/Whinfell_Phased_Development_Plan_v1.0.md"
    text = plan.read_text(encoding="utf-8")
    required = [
        "Phase 1: Rectification of Names",
        "Phase 2: Node Architecture",
        "Phase 3: Interface Improvements",
        "Phase 4: Validation & Reliability",
        "Recommended order of work",
    ]
    lines = [
        f"=== Phased Development Plan v1.0 ===",
        f"captured: {datetime.now(timezone.utc).isoformat()}",
        f"path: {plan}",
        "",
        "required_sections:",
    ]
    for title in required:
        lines.append(f"  - {title}: {'FOUND' if title.lower() in text.lower() else 'MISSING'}")
    lines.extend(["", "excerpt (executive summary):", ""])
    if "## Executive summary" in text:
        start = text.index("## Executive summary")
        lines.append(text[start : start + 600].strip())
    todo = REPO / "01_Strategy_Docs/BUILD_TODO_List.md"
    progress = REPO / "01_Strategy_Docs/Progress_Log.md"
    lines.extend(
        [
            "",
            f"BUILD_TODO_List.md exists: {todo.is_file()}",
            f"Progress_Log.md exists: {progress.is_file()}",
        ]
    )
    (SCRATCH / "phased_plan.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tc_dd_display() -> None:
    sync_all()
    html = TC_HTML.read_text(encoding="utf-8")
    meta = json.loads(META_JSON.read_text(encoding="utf-8"))
    badge = badge_default_payload()
    m = re.search(
        re.escape(DD_BADGE_SYNC_START) + r"[\s\S]*?" + re.escape(DD_BADGE_SYNC_END),
        html,
    )
    injected = m.group(0) if m else "MISSING SYNC BLOCK"
    badge_el = re.search(r'id="ddVersionBadge"[^>]*>([^<]*)<', html)
    lines = [
        "=== Transmission Control DD badge display ===",
        f"captured: {datetime.now(timezone.utc).isoformat()}",
        "",
        "architecture (intentional):",
        "  1. python sync_dictionary_meta.sync_all() reads data_dictionary.yaml via master_dictionary_info()",
        "  2. Injects window.DICTIONARY_BADGE_DEFAULT into HTML (DD_BADGE_SYNC block)",
        "  3. Writes 08_Deliverables/data_dictionary_meta.json for file:// sibling fetch",
        "  4. TC renderAll() -> renderDataDictionaryBadge() fetches meta.json and validates vs injected DEFAULT",
        "",
        "yaml master_dictionary_info():",
        json.dumps(master_dictionary_info(), indent=2),
        "",
        "badge_default_payload() (injected into HTML):",
        json.dumps(badge, indent=2),
        "",
        "data_dictionary_meta.json on disk:",
        json.dumps(meta, indent=2),
        "",
        "HTML DD_BADGE_SYNC block:",
        injected[:800],
        "",
        "HTML badge element (initial placeholder):",
        badge_el.group(0) if badge_el else "ddVersionBadge not found",
        "",
        "renderAll() calls renderDataDictionaryBadge:",
        str("renderDataDictionaryBadge(true)" in html[html.find("function renderAll()") : html.find("function renderAll()") + 200]),
        "",
        "=== disk-backed headless evidence (file:// fetch path) ===",
        run(["node", str(REPO / "whinfell_pipeline/tests/dd_badge_file_evidence.mjs")]),
        "",
        "=== mocked-fetch headless (async path) ===",
        run(["node", str(REPO / "whinfell_pipeline/tests/dd_badge_headless.mjs")]),
    ]
    (SCRATCH / "tc_dd_display.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_dict_test_log() -> None:
    out = []
    out.append(f"=== dict_test.log captured {datetime.now(timezone.utc).isoformat()} ===")
    for i in (1, 2):
        out.append(f"\n--- test_data_dictionary run {i} ---")
        out.append(run([sys.executable, "-m", "unittest", "whinfell_pipeline.tests.test_data_dictionary", "-v"]))
    out.append("\n--- test_sync_dictionary_meta ---")
    out.append(run([sys.executable, "-m", "unittest", "whinfell_pipeline.tests.test_sync_dictionary_meta", "-v"]))
    out.append("\n--- test_master_dictionary_tc ---")
    out.append(run([sys.executable, "-m", "unittest", "whinfell_pipeline.tests.test_master_dictionary_tc", "-v"]))
    out.append("\n--- test_operator_naming_alignment ---")
    out.append(run([sys.executable, "-m", "unittest", "whinfell_pipeline.tests.test_operator_naming_alignment", "-v"]))
    (SCRATCH / "dict_test.log").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_refresh_evidence() -> None:
    lines = [
        f"=== refresh_evidence.log ===",
        f"captured: {datetime.now(timezone.utc).isoformat()}",
        "",
        "--- sync_dictionary_meta (yaml -> meta.json + HTML injection) ---",
        run([sys.executable, "-m", "whinfell_pipeline.sync_dictionary_meta"]),
        "",
        "--- master_dictionary_info vs injected vs meta.json ---",
        json.dumps(
            {
                "yaml": master_dictionary_info(),
                "badge_default": badge_default_payload(),
                "meta_json": build_meta_payload(),
            },
            indent=2,
        ),
        "",
        "--- scan_operator_violations() ---",
    ]
    violations = scan_operator_violations()
    lines.append(f"count: {len(violations)}")
    for v in violations[:20]:
        lines.append(f"  {v}")
    lines.extend(
        [
            "",
            "--- full test suite (103 tests) ---",
            run([sys.executable, "-m", "unittest", "discover", "-s", "whinfell_pipeline/tests", "-p", "test_*.py", "-v"]),
            "",
            "--- normalize dry-run x2 (dictionary-driven infer_canonical_name) ---",
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        drop = Path(tmp)
        src = drop / "koyfin_WhinPump_evidence.csv"
        src.write_text("Ticker,Last Price\nHYG,75\n", encoding="utf-8")
        for i in (1, 2):
            result = normalize_drop_dir(drop, dry_run=True)
            target = infer_canonical_name(src.name, src)
            lines.append(f"dry_run_{i}: renamed={result.renamed} target={target} actions={result.actions}")
    lines.extend(
        [
            "",
            "--- dd_badge_file_evidence (disk meta.json, no hardcoded fetch payload) ---",
            run(["node", str(REPO / "whinfell_pipeline/tests/dd_badge_file_evidence.mjs")]),
            "",
            "--- dd_badge_headless (async render path) ---",
            run(["node", str(REPO / "whinfell_pipeline/tests/dd_badge_headless.mjs")]),
        ]
    )
    (SCRATCH / "refresh_evidence.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    write_dd_v1()
    write_phased_plan()
    write_dict_test_log()
    write_tc_dd_display()
    write_refresh_evidence()
    print(f"evidence written to {SCRATCH}")
    for name in ("dd_v1.txt", "phased_plan.txt", "dict_test.log", "tc_dd_display.txt", "refresh_evidence.log"):
        p = SCRATCH / name
        print(f"  {name}: {p.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())