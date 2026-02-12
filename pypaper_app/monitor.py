from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Sequence


HYPRCTL_MONITORS_TIMEOUT_S = 2.0


def _run_hyprctl_json(args: Sequence[str]) -> object:
    try:
        proc = subprocess.run(
            ["hyprctl", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=HYPRCTL_MONITORS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"hyprctl timed out after {HYPRCTL_MONITORS_TIMEOUT_S}s"
        ) from e

    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.strip() or proc.stdout.strip() or "hyprctl failed"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from hyprctl: {e}") from e


def get_monitors(
    *, prefer_hyprctl: bool = True, allow_qt_fallback: bool = True
) -> list[str]:
    """Return a list of monitor names.

    Prefer Hyprland (hyprctl) when available. Falls back to Qt screen names.
    """

    if prefer_hyprctl and shutil.which("hyprctl"):
        for args in (("monitors", "-j"), ("-j", "monitors")):
            try:
                data = _run_hyprctl_json(args)
            except RuntimeError:
                continue

            if isinstance(data, list):
                names: list[str] = []
                seen: set[str] = set()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    if name in seen:
                        continue
                    seen.add(name)
                    names.append(name)
                if names:
                    return names

    if not allow_qt_fallback:
        return []

    # Fallback: Qt screen list.
    try:
        from PySide6 import QtGui
    except Exception:
        return []

    app = QtGui.QGuiApplication.instance()
    if app is None:
        QtGui.QGuiApplication([])

    names: list[str] = []
    for i, screen in enumerate(QtGui.QGuiApplication.screens(), start=1):
        name = screen.name() or f"Screen {i}"
        names.append(name)
    return names


def _self_test() -> int:
    names = get_monitors()
    print(f"monitors={names!r}")

    # Soft expectation: on Hyprland this should be non-empty.
    if shutil.which("hyprctl"):
        assert names, "Expected at least one monitor from hyprctl/Qt"

    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
