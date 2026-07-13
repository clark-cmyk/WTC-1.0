"""Shared helpers to prove China Policy track isolation from Global score logic."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = Path(__file__).resolve().parent

# Production modules scanned for forbidden Global-score dependencies.
PRODUCTION_MODULES: tuple[str, ...] = (
    "__init__.py",
    "version.py",
    "models.py",
    "schema.py",
    "data_parser.py",
    "storage.py",
    "ingest.py",
    "sq3.py",
)

FORBIDDEN_GLOBAL_MARKERS: tuple[str, ...] = (
    "04_Score_Calculation",
    "Credit_Confirmation",
    "Whinfell_Credit_Confirmation",
)

SQ3_FIRST_COMMIT = "9f7ae5b"
SQ3_BASE_REF = f"{SQ3_FIRST_COMMIT}^"
SQ3_RANGE_END = "HEAD"

_LS_TREE_LINE = re.compile(r"^\d+ blob ([0-9a-f]{40})\s*(data/global/.+)$")


def production_py_paths() -> list[Path]:
    return [PKG_ROOT / name for name in PRODUCTION_MODULES if (PKG_ROOT / name).exists()]


def scan_production_imports() -> list[tuple[str, int, str]]:
    """AST import scan across all production china_policy_track modules."""
    hits: list[tuple[str, int, str]] = []
    for py_file in production_py_paths():
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        rel = str(py_file.relative_to(REPO_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for marker in FORBIDDEN_GLOBAL_MARKERS:
                        if marker in alias.name:
                            hits.append((rel, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for marker in FORBIDDEN_GLOBAL_MARKERS:
                    if marker in module:
                        hits.append((rel, node.lineno, module))
    return hits


def global_data_files() -> list[Path]:
    root = REPO_ROOT / "data" / "global"
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def parse_ls_tree_global(output: str) -> dict[str, str]:
    """Parse ``git ls-tree`` lines into {repo_path: git_blob_oid}."""
    entries: dict[str, str] = {}
    for line in output.splitlines():
        match = _LS_TREE_LINE.match(line.strip())
        if match:
            entries[match.group(2)] = match.group(1)
    return entries


def _run_cmd(cmd: list[str], *, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    rendered = " ".join(cmd)
    output = (proc.stdout + proc.stderr).rstrip()
    return rendered, output


def _run_shell(cmd: str, *, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, check=False)
    output = (proc.stdout + proc.stderr).rstrip()
    return cmd, output


def _shasum_hex_from_output(output: str) -> str:
    token = output.strip().split()
    return token[0] if token else ""


def ls_tree_global_at(ref: str, repo_root: Path | None = None) -> dict[str, str]:
    root = repo_root or REPO_ROOT
    _, output = _run_cmd(["git", "ls-tree", "-r", ref, "--", "data/global/"], cwd=root)
    return parse_ls_tree_global(output)


def git_show_shasum(ref: str, repo_path: str, repo_root: Path | None = None) -> tuple[str, str]:
    """SHA1 of committed blob content via ``git show ref:path | shasum``."""
    root = repo_root or REPO_ROOT
    cmd = f"git show {ref}:{repo_path} | shasum"
    return _run_shell(cmd, cwd=root)


def cat_file_shasum(blob_oid: str, repo_root: Path | None = None) -> tuple[str, str]:
    """SHA1 of git object content via ``git cat-file -p oid | shasum``."""
    root = repo_root or REPO_ROOT
    cmd = f"git cat-file -p {blob_oid} | shasum"
    return _run_shell(cmd, cwd=root)


def run_git_isolation_checks(repo_root: Path | None = None) -> list[tuple[str, str]]:
    """Subprocess git/shasum checks pinned to committed refs (not working-tree files).

    Returns (command, stdout) pairs suitable for verbatim echo into artifacts.
    """
    root = repo_root or REPO_ROOT
    sq3_parent_range = f"{SQ3_BASE_REF}..{SQ3_RANGE_END}"

    checks: list[tuple[str, str]] = []
    checks.append(
        (
            "NOTE: SQ3 deliverable scope = git diff with -- china_policy_track/ path filter. "
            "Full-range diff may include repo-hygiene files outside that filter.",
            "",
        )
    )
    for cmd in (
        ["git", "diff", "--name-only", sq3_parent_range],
        ["git", "diff", "--name-only", sq3_parent_range, "--", "china_policy_track/"],
        ["git", "diff", sq3_parent_range, "--", "04_Score_Calculation/"],
        ["git", "diff", sq3_parent_range, "--", "data/global/"],
        ["git", "ls-files", ".DS_Store"],
        ["git", "status", "--porcelain"],
        ["git", "ls-tree", "-r", SQ3_BASE_REF, "--", "data/global/"],
        ["git", "ls-tree", "-r", SQ3_RANGE_END, "--", "data/global/"],
    ):
        checks.append(_run_cmd(cmd, cwd=root))

    base_entries = ls_tree_global_at(SQ3_BASE_REF, root)
    head_entries = ls_tree_global_at(SQ3_RANGE_END, root)
    for repo_path in sorted(head_entries):
        checks.append(git_show_shasum(SQ3_BASE_REF, repo_path, root))
        checks.append(git_show_shasum(SQ3_RANGE_END, repo_path, root))
        checks.append(cat_file_shasum(head_entries[repo_path], root))

    return checks


def verify_global_blob_parity(repo_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Assert data/global blobs unchanged SQ3 base→HEAD; shasum matches ls-tree oids."""
    root = repo_root or REPO_ROOT
    base_entries = ls_tree_global_at(SQ3_BASE_REF, root)
    head_entries = ls_tree_global_at(SQ3_RANGE_END, root)
    if base_entries != head_entries:
        raise AssertionError(f"data/global ls-tree mismatch: base={base_entries} head={head_entries}")

    report: dict[str, dict[str, str]] = {}
    for repo_path, blob_oid in sorted(head_entries.items()):
        _, base_out = git_show_shasum(SQ3_BASE_REF, repo_path, root)
        _, head_out = git_show_shasum(SQ3_RANGE_END, repo_path, root)
        _, cat_out = cat_file_shasum(blob_oid, root)
        base_hex = _shasum_hex_from_output(base_out)
        head_hex = _shasum_hex_from_output(head_out)
        cat_hex = _shasum_hex_from_output(cat_out)
        if not (base_hex and base_hex == head_hex == cat_hex):
            raise AssertionError(
                f"shasum mismatch for {repo_path}: base={base_hex} head={head_hex} cat={cat_hex}"
            )
        report[repo_path] = {
            "blob_oid": blob_oid,
            "shasum": base_hex,
        }
    return report


def format_git_isolation_report(checks: list[tuple[str, str]]) -> str:
    lines = ["=== Verification plan step 4: Global isolation ==="]
    for cmd, output in checks:
        if cmd.startswith("NOTE:"):
            lines.append(cmd)
            continue
        lines.append(f"--- Command: {cmd} ---")
        lines.append(output if output else "(empty)")
    return "\n".join(lines) + "\n"


def assert_sq3_deliverable_scope(repo_root: Path | None = None) -> list[str]:
    """Return china_policy_track paths changed in SQ3 range; assert scope constraints."""
    root = repo_root or REPO_ROOT
    sq3_parent_range = f"{SQ3_BASE_REF}..{SQ3_RANGE_END}"
    _, china_out = _run_cmd(
        ["git", "diff", "--name-only", sq3_parent_range, "--", "china_policy_track/"],
        cwd=root,
    )
    china_paths = [p for p in china_out.splitlines() if p.strip()]
    if not china_paths:
        raise AssertionError("no china_policy_track paths in SQ3 deliverable scope")
    for path in china_paths:
        if not path.startswith("china_policy_track/"):
            raise AssertionError(f"non-package path in SQ3 deliverable scope: {path}")

    _, ls_ds = _run_cmd(["git", "ls-files", ".DS_Store"], cwd=root)
    if ls_ds.strip():
        raise AssertionError(f".DS_Store still tracked: {ls_ds!r}")
    return china_paths