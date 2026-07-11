"""Whinfell brand theme definition."""

from __future__ import annotations

from pathlib import Path

from .base import BrandTheme

WHINFELL = BrandTheme(
    name="whinfell",
    primary="#1E2761",
    secondary="#36454F",
    accent="#2E86AB",
    highlight="#F4A261",
    text_dark="#212121",
    text_muted="#5E5E5E",
    background="#FFFFFF",
    font_title="Calibri",
    font_body="Calibri Light",
    logo_path=Path("templates/shared/whinfell_logo.png"),
    slide_width_inches=11.0,
    slide_height_inches=8.5,
)