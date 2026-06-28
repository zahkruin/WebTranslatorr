"""
Application version management.

The canonical source of truth is the VERSION file at the project root.
This module provides a single function to read it, avoiding circular imports
between server.py and the api modules.
"""

from pathlib import Path

_VERSION_PATH = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    """Return the application version from the VERSION file."""
    try:
        return _VERSION_PATH.read_text().strip()
    except (FileNotFoundError, OSError):
        return "0.0.0"
