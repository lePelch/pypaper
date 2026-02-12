from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6 import QtGui

from . import paths


HYPRCTL_TIMEOUT_S = 4.0


def default_loaded_dir() -> Path:
    root = paths.data_root()
    return paths.loaded_dir(root)


def loaded_path_for_slot(loaded_dir: Path, slot: int) -> Path:
    if slot <= 0:
        raise ValueError(f"Invalid slot: {slot}")
    return loaded_dir / f"monitor_{slot}.png"


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_png_atomic(*, src: Path, dest_png: Path) -> None:
    """Convert src to PNG and atomically replace dest_png."""

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(src)

    dest_png.parent.mkdir(parents=True, exist_ok=True)

    reader = QtGui.QImageReader(str(src))
    img = reader.read()
    if img.isNull():
        raise RuntimeError(f"Failed to read image {src}: {reader.errorString()}")

    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=dest_png.stem + ".",
            suffix=".tmp",
            dir=str(dest_png.parent),
        )
        os.close(fd)
        tmp_path = Path(tmp_name)

        writer = QtGui.QImageWriter(str(tmp_path), b"png")
        if not writer.write(img):
            raise RuntimeError(
                f"Failed to write PNG {dest_png}: {writer.errorString()}"
            )

        os.replace(tmp_path, dest_png)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _run_hyprctl(args: list[str]) -> None:
    try:
        proc = subprocess.run(
            ["hyprctl", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=HYPRCTL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"hyprctl timed out after {HYPRCTL_TIMEOUT_S}s") from e

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip() or "hyprctl failed"
        raise RuntimeError(msg)


def set_wallpaper_hyprpaper(*, monitor: str, path: Path) -> None:
    """Set hyprpaper wallpaper for a given monitor.

    Requires hyprpaper to be running and hyprctl to be available.
    """

    abs_path = path.expanduser().resolve()
    _run_hyprctl(["hyprpaper", "wallpaper", f"{monitor}, {abs_path}"])


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"version": 2, "mapping": {}, "monitors": {}}

    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": 2, "mapping": {}, "monitors": {}}
    if "monitors" not in data or not isinstance(data.get("monitors"), dict):
        data["monitors"] = {}
    if "mapping" not in data or not isinstance(data.get("mapping"), dict):
        data["mapping"] = {}
    if "version" not in data:
        data["version"] = 2
    return data


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def record_assignment(
    *,
    state_path: Path,
    monitor: str,
    theme: str,
    slot: int,
    source_path: Path,
    loaded_path: Path,
) -> None:
    state = load_state(state_path)
    monitors = state.setdefault("monitors", {})
    monitors[monitor] = {
        "theme": theme,
        "slot": slot,
        "source_path": str(source_path),
        "loaded_path": str(loaded_path),
    }
    save_state(state_path, state)


def get_mapping(state_path: Path) -> dict[str, int]:
    try:
        state = load_state(state_path)
    except Exception:
        return {}

    raw = state.get("mapping")
    if not isinstance(raw, dict):
        return {}

    out: dict[str, int] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k:
            continue
        if isinstance(v, int) and v > 0:
            out[k] = v
    return out


def set_mapping(state_path: Path, mapping: dict[str, int]) -> None:
    state = load_state(state_path)
    state["mapping"] = dict(mapping)
    save_state(state_path, state)


def apply_wallpaper(
    *,
    monitor: str,
    slot: int,
    theme: str,
    src: Path,
    loaded_dir: Path | None = None,
    state_path: Path | None = None,
) -> Path:
    loaded_dir = default_loaded_dir() if loaded_dir is None else loaded_dir
    state_path = (loaded_dir / "state.json") if state_path is None else state_path

    loaded_path = loaded_path_for_slot(loaded_dir, slot)
    write_png_atomic(src=src, dest_png=loaded_path)
    set_wallpaper_hyprpaper(monitor=monitor, path=loaded_path)
    record_assignment(
        state_path=state_path,
        monitor=monitor,
        theme=theme,
        slot=slot,
        source_path=src,
        loaded_path=loaded_path,
    )
    return loaded_path


def _self_test(argv: list[str]) -> int:
    # Safe, local tests (no hyprctl calls).
    with tempfile.TemporaryDirectory(prefix="pypaper_loaded_") as td:
        tmp_loaded = Path(td)
        tmp_state = tmp_loaded / "state.json"

        src_dir = tmp_loaded / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Make a deterministic source image.
        img = QtGui.QImage(64, 32, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor("#336699"))
        src = src_dir / "test.png"
        assert img.save(str(src)), "Failed to write test source PNG"

        dest = loaded_path_for_slot(tmp_loaded, 1)
        write_png_atomic(src=src, dest_png=dest)
        assert dest.exists(), "write_png_atomic did not create dest"
        assert dest.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "dest is not PNG"

        record_assignment(
            state_path=tmp_state,
            monitor="MON-1",
            theme="ThemeX",
            slot=1,
            source_path=src,
            loaded_path=dest,
        )
        state = load_state(tmp_state)
        assert state["monitors"]["MON-1"]["loaded_path"] == str(dest)

    print("image.py self-test OK")

    # Optional: apply a wallpaper using hyprctl.
    if len(argv) >= 5 and argv[1] == "--apply":
        mon = argv[2]
        th = argv[3]
        src = Path(argv[4])
        loaded_path = apply_wallpaper(monitor=mon, slot=1, theme=th, src=src)
        print(f"applied monitor={mon} loaded_path={loaded_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test(sys.argv))
