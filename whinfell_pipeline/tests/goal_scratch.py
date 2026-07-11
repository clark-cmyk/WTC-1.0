"""Resolve goal-mode scratch dir for captured verification evidence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_DEFAULT = Path(tempfile.gettempdir()) / "grok-goal-verify" / "implementer"


def goal_scratch() -> Path:
    path = Path(os.environ.get("GROK_GOAL_SCRATCH", str(_DEFAULT)))
    path.mkdir(parents=True, exist_ok=True)
    return path