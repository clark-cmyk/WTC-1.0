"""Re-stage quarantined files that have canonical names + pass transform."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from whinfell_pipeline.batch_collect import infer_canonical_name, is_canonical_name, strip_browser_duplicate_suffix
from whinfell_pipeline.csv_download import stage_file


@dataclass
class QuarantineRetryResult:
    scanned: int = 0
    staged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def retry_quarantine_canonical(
    staged_root: Path,
    *,
    operator: str = "desk",
    overwrite: bool = True,
    max_files: int = 200,
) -> QuarantineRetryResult:
    """Attempt to stage quarantine CSVs that already match canonical filename contract."""
    result = QuarantineRetryResult()
    quarantine = staged_root / "quarantine"
    if not quarantine.is_dir():
        result.errors.append(f"quarantine dir missing: {quarantine}")
        return result

    candidates: list[Path] = []
    for day_dir in sorted(quarantine.glob("*/")):
        for path in sorted(day_dir.glob("*.csv")):
            # Strip quarantine prefix: 112239__rates_... → rates_...
            name = path.name
            if "__" in name:
                base = name.split("__", 1)[1]
            else:
                base = name
            if is_canonical_name(base):
                candidates.append(path)
    candidates = candidates[:max_files]

    for path in candidates:
        result.scanned += 1
        name = path.name.split("__", 1)[-1] if "__" in path.name else path.name
        # stage_file keys off filename — copy to temp name in parent for staging
        import shutil
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp(prefix="wtm_quarantine_retry_"))
        try:
            src = tmp_dir / name
            shutil.copy2(path, src)
            fr = stage_file(src, staged_root, operator=operator, overwrite=overwrite)
            if fr.status == "staged":
                result.staged += 1
            else:
                result.skipped += 1
                if fr.errors:
                    result.errors.append(f"{name}: {'; '.join(fr.errors)}")
        except Exception as exc:
            result.skipped += 1
            result.errors.append(f"{path.name}: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


def _quarantine_base_name(path: Path) -> str:
    name = path.name
    if "__" in name:
        name = name.split("__", 1)[1]
    return strip_browser_duplicate_suffix(name)


def retry_quarantine_normalize(
    staged_root: Path,
    *,
    operator: str = "desk",
    overwrite: bool = True,
    max_files: int = 200,
) -> QuarantineRetryResult:
    """Normalize quarantined vendor filenames, then attempt stage."""
    result = QuarantineRetryResult()
    quarantine = staged_root / "quarantine"
    if not quarantine.is_dir():
        result.errors.append(f"quarantine dir missing: {quarantine}")
        return result

    candidates: list[tuple[Path, str]] = []
    for day_dir in sorted(quarantine.glob("*/")):
        for path in sorted(day_dir.glob("*.csv")):
            base = _quarantine_base_name(path)
            if is_canonical_name(base):
                candidates.append((path, base))
                continue
            dest_name = infer_canonical_name(base, path)
            if dest_name:
                candidates.append((path, dest_name))
    candidates = candidates[:max_files]

    import shutil
    import tempfile

    for path, stage_name in candidates:
        result.scanned += 1
        tmp_dir = Path(tempfile.mkdtemp(prefix="wtm_quarantine_norm_"))
        try:
            src = tmp_dir / stage_name
            shutil.copy2(path, src)
            fr = stage_file(src, staged_root, operator=operator, overwrite=overwrite)
            if fr.status == "staged":
                result.staged += 1
            else:
                result.skipped += 1
                if fr.errors:
                    result.errors.append(f"{stage_name}: {'; '.join(fr.errors)}")
        except Exception as exc:
            result.skipped += 1
            result.errors.append(f"{path.name}: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return result