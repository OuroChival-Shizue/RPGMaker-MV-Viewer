"""Path and runtime constants for RPGMV Viewer."""

from __future__ import annotations

from pathlib import Path

PORT = 8642

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
REGISTRY_PATH = PROJECT_ROOT / "games_registry.json"

