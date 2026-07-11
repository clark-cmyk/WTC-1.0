"""Sync Master Data Dictionary metadata to desk-facing artifacts for Transmission Control."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from whinfell_pipeline.data_dictionary import (
    DICTIONARY_VERSION,
    badge_default_payload,
    canonical_saved_view_names,
    get_project_structure,
    master_dictionary_info,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
META_JS = REPO_ROOT / "08_Deliverables" / "data_dictionary_meta.js"
META_JSON = REPO_ROOT / "08_Deliverables" / "data_dictionary_meta.json"
TC_HTML = REPO_ROOT / "08_Deliverables" / "Whinfell_Transmission_Control.html"

DD_BADGE_SYNC_START = "<!-- DD_BADGE_SYNC_START -->"
DD_BADGE_SYNC_END = "<!-- DD_BADGE_SYNC_END -->"


def build_meta_payload() -> dict:
    info = master_dictionary_info()
    ps = get_project_structure()
    return {
        "version": info["version"],
        "date": info["date"],
        "status": info["status"],
        "alignment": info["alignment"],
        "machine_version": DICTIONARY_VERSION,
        "repo_root": ps.get("repo_root", ""),
        "saved_views": canonical_saved_view_names(),
        "validated": True,
        "source": "whinfell_pipeline/data_dictionary.yaml",
    }


def build_badge_sync_script() -> str:
    payload = badge_default_payload()
    return (
        f"{DD_BADGE_SYNC_START}\n"
        f"<script>\n"
        f"window.DICTIONARY_BADGE_DEFAULT = {json.dumps(payload, indent=2)};\n"
        f"</script>\n"
        f"{DD_BADGE_SYNC_END}\n"
    )


def inject_tc_badge_sync(html_path: Path | None = None) -> Path:
    """Inject DICTIONARY_BADGE_DEFAULT from master_dictionary_info() into TC HTML."""
    path = html_path or TC_HTML
    text = path.read_text(encoding="utf-8")
    block = build_badge_sync_script()
    pattern = re.compile(
        re.escape(DD_BADGE_SYNC_START) + r"[\s\S]*?" + re.escape(DD_BADGE_SYNC_END) + r"\n?",
    )
    if pattern.search(text):
        # Lambda avoids re.sub interpreting JSON backslashes in the replacement.
        text = pattern.sub(lambda _m: block, text)
    else:
        anchor = '  <script src="https://cdn.tailwindcss.com"></script>\n'
        if anchor not in text:
            raise RuntimeError("TC HTML tailwind anchor not found for badge sync injection")
        text = text.replace(anchor, anchor + "\n" + block)
    path.write_text(text, encoding="utf-8")
    return path


def write_meta_files(payload: dict | None = None) -> Path:
    payload = payload or build_meta_payload()
    META_JSON.parent.mkdir(parents=True, exist_ok=True)
    META_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    js = f"window.DICTIONARY_META = {json.dumps(payload, indent=2)};\n"
    META_JS.write_text(js, encoding="utf-8")
    return META_JSON


def sync_all() -> tuple[Path, Path]:
    meta_path = write_meta_files()
    html_path = inject_tc_badge_sync()
    return meta_path, html_path


def main() -> int:
    meta_path, html_path = sync_all()
    print(f"synced {meta_path}")
    print(f"synced {html_path} (DD_BADGE_SYNC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())