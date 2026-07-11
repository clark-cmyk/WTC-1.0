"""Atomic Chunk 2.2b verification — scope gate + tests + scratch artifacts.

Usage:
    python3 -m whinfell_pipeline.verify_2_2b_goal /path/to/scratch
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED = frozenset({
    ".gitignore",
    "08_Deliverables/Whinfell_Transmission_Control.html",
    "08_Deliverables/Whinfell_Transmission_Control_Review_Log.md",
    "whinfell_pipeline/WTM_EXPORT_v2.1_SPEC.md",
    "whinfell_pipeline/tests/html_headless_2_2b.mjs",
    "whinfell_pipeline/tests/test_transmission_control_2_2b.py",
    "whinfell_pipeline/verify_2_2b_goal.py",
    "whinfell_pipeline/examples/hydration_bundle.json",
})

HTML = REPO_ROOT / "08_Deliverables/Whinfell_Transmission_Control.html"
WTM_SPEC = REPO_ROOT / "whinfell_pipeline/WTM_EXPORT_v2.1_SPEC.md"
REVIEW_LOG = REPO_ROOT / "08_Deliverables/Whinfell_Transmission_Control_Review_Log.md"
HEADLESS = REPO_ROOT / "whinfell_pipeline/tests/html_headless_2_2b.mjs"

STRUCTURAL_MARKERS = (
    'id="suggestedTracerPanel"',
    'id="tracerHorizonBody"',
    'data-panel="prompts"',
    'class="hz-select',
    "Manual Override",
    "Operator Confirmed",
    "progressive-disclosure",
    "applyIntakeOverride",
    "applyHorizonOverride",
    "getTracerChrome",
)


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def revert_unrelated_tracked() -> None:
    proc = _run(["git", "checkout", "--", "README.md", "data/"])
    if proc.returncode != 0:
        raise RuntimeError(f"git checkout failed: {proc.stderr or proc.stdout}")


def stage_allowed_deliverables() -> None:
    existing = [p for p in sorted(ALLOWED) if (REPO_ROOT / p).exists()]
    if not existing:
        raise RuntimeError("no allowed deliverable paths found on disk")
    proc = _run(["git", "add", "--"] + existing)
    if proc.returncode != 0:
        raise RuntimeError(f"git add failed: {proc.stderr or proc.stdout}")


def collect_delta_paths() -> list[str]:
    paths: set[str] = set()
    for args in (["git", "diff", "--name-only"], ["git", "diff", "--cached", "--name-only"]):
        proc = _run(args)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        paths.update(p for p in proc.stdout.splitlines() if p.strip())
    return sorted(paths)


def collect_status_paths() -> list[str]:
    proc = _run(["git", "status", "--porcelain", "-uall"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        paths.append(path)
    return paths


def assert_scope(delta_paths: list[str], status_paths: list[str]) -> None:
    missing = sorted(ALLOWED - set(delta_paths))
    if missing:
        raise RuntimeError(
            "Deliverable delta incomplete — allowed paths not in git diff:\n  "
            + "\n  ".join(missing)
        )
    extra_delta = sorted(set(delta_paths) - ALLOWED)
    if extra_delta:
        raise RuntimeError(
            "Scope violation (git diff) — paths outside ALLOWED:\n  "
            + "\n  ".join(extra_delta)
        )
    extra_status = sorted(set(status_paths) - ALLOWED)
    if extra_status:
        raise RuntimeError(
            "Scope violation (git status) — paths outside ALLOWED:\n  "
            + "\n  ".join(extra_status)
        )


def run_pipeline_tests(log_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "whinfell_pipeline.tests.test_export_contract",
        "whinfell_pipeline.tests.test_pipeline",
        "whinfell_pipeline.tests.test_transmission_control_2_2b",
    ]
    lines: list[str] = []
    for run in (1, 2):
        lines.append(f"=== Pipeline tests run {run} ===")
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
        lines.append(proc.stdout)
        if proc.stderr:
            lines.append(proc.stderr)
        if proc.returncode != 0:
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            raise RuntimeError(f"pipeline tests run {run} failed (exit {proc.returncode})")
        lines.append("")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_headless_twice(log_path: Path) -> None:
    lines: list[str] = []
    for run in (1, 2):
        lines.append(f"=== Headless 2.2b run {run} ===")
        proc = subprocess.run(
            ["node", str(HEADLESS)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        lines.append(proc.stdout)
        if proc.stderr:
            lines.append(proc.stderr)
        if proc.returncode != 0 or "html_headless_2_2b_ok" not in proc.stdout:
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            raise RuntimeError(f"headless run {run} failed")
        lines.append("")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_structural(path: Path) -> None:
    text = HTML.read_text(encoding="utf-8")
    hits = [f"{marker!r}: {'FOUND' if text.find(marker) >= 0 else 'MISSING'}" for marker in STRUCTURAL_MARKERS]
    path.write_text(
        "=== HTML structural markers ===\n"
        + "\n".join(hits)
        + f"\n\nline_count: {len(text.splitlines())}\n",
        encoding="utf-8",
    )


def write_doc_updates(path: Path) -> None:
    spec = WTM_SPEC.read_text(encoding="utf-8")
    review = REVIEW_LOG.read_text(encoding="utf-8")
    spec_hits = [
        ln for ln in spec.splitlines()
        if any(k in ln for k in ("2.2b", "progressive", "applyHorizonOverride", "getTracerChrome", "confirm_required"))
    ]
    review_hits = [
        ln for ln in review.splitlines()
        if "2.2b" in ln or "Hybrid" in ln or "progressive" in ln.lower()
    ]
    path.write_text(
        "=== WTM_EXPORT_v2.1_SPEC.md excerpts ===\n"
        + "\n".join(spec_hits[:30])
        + "\n\n=== Review_Log excerpts ===\n"
        + "\n".join(review_hits[:20])
        + "\n",
        encoding="utf-8",
    )


def write_deliverables_ls(path: Path) -> None:
    proc = subprocess.run(
        [
            "ls", "-l",
            str(HTML),
            str(WTM_SPEC),
            str(REVIEW_LOG),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ls deliverables failed: {proc.stderr or proc.stdout}")
    for target in (HTML, WTM_SPEC, REVIEW_LOG):
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f"deliverable missing or empty: {target}")
    path.write_text(proc.stdout, encoding="utf-8")


def write_changed_files(path: Path, delta_paths: list[str]) -> None:
    status_proc = _run(["git", "status", "--porcelain", "-uall"])
    path.write_text(
        "=== git diff delta (working + staged) ===\n"
        + "\n".join(delta_paths)
        + "\n\n=== git status --porcelain -uall ===\n"
        + (status_proc.stdout or "(clean)"),
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 -m whinfell_pipeline.verify_2_2b_goal <scratch_dir>", file=sys.stderr)
        return 2

    scratch = Path(argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)

    revert_unrelated_tracked()
    stage_allowed_deliverables()
    delta_paths = collect_delta_paths()
    status_paths = collect_status_paths()

    (scratch / "git_diff_name_only.txt").write_text(
        "\n".join(delta_paths) + ("\n" if delta_paths else ""),
        encoding="utf-8",
    )
    (scratch / "git_status_porcelain.txt").write_text(
        _run(["git", "status", "--porcelain", "-uall"]).stdout or "",
        encoding="utf-8",
    )

    assert_scope(delta_paths, status_paths)

    run_pipeline_tests(scratch / "pipeline_tests.log")
    run_headless_twice(scratch / "html_headless_2.2b.log")
    write_structural(scratch / "html_structural.txt")
    write_doc_updates(scratch / "doc_updates.txt")
    write_deliverables_ls(scratch / "deliverables_ls.txt")
    write_changed_files(scratch / "changed_files.txt", delta_paths)

    (scratch / "verify_2_2b_summary.txt").write_text(
        "verify_2_2b_goal: PASS\n"
        f"allowed_paths: {len(ALLOWED)}\n"
        f"delta_paths: {len(delta_paths)}\n"
        f"status_paths: {len(status_paths)}\n"
        + "\n".join(delta_paths)
        + "\n",
        encoding="utf-8",
    )
    print("verify_2_2b_goal: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))