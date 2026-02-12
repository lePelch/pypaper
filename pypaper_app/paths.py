from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    # Runtime data (themes, Loaded wallpapers, state.json).
    # Override with PYPAPER_DATA_ROOT.
    env = os.environ.get("PYPAPER_DATA_ROOT")
    if env:
        return Path(env).expanduser()

    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "pypaper"


def theme_root(root: Path) -> Path:
    env = os.environ.get("PYPAPER_THEME_ROOT")
    if env:
        return Path(env).expanduser()
    return root / "themes"


def loaded_dir(root: Path) -> Path:
    return root / "Loaded"


def state_path(root: Path) -> Path:
    return loaded_dir(root) / "state.json"
