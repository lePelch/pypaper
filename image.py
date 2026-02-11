from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def default_loaded_dir() -> Path:
    return repo_root() / "Loaded"


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_into_loaded(*, src: Path, loaded_dir: Path, theme: str, monitor: str) -> Path:
    """Copy src into Loaded/<theme>/<monitor>/ and return destination path.

    Destination file name is content-addressed (sha1 + extension) to avoid
    collisions when two sources share a name.
    """

    if not src.exists() or not src.is_file():
        raise FileNotFoundError(src)

    digest = sha1_file(src)
    ext = src.suffix.lower()

    dest_dir = loaded_dir / theme / monitor
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{digest}{ext}"
    if not dest.exists():
        shutil.copy2(src, dest)

    return dest


def _run_hyprctl(args: list[str]) -> None:
    proc = subprocess.run(
        ["hyprctl", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip() or "hyprctl failed"
        raise RuntimeError(msg)


def set_wallpaper_hyprpaper(*, monitor: str, path: Path) -> None:
    """Set hyprpaper wallpaper for a given monitor.

    Requires hyprpaper to be running and hyprctl to be available.
    """

    abs_path = path.expanduser().resolve()
    _run_hyprctl(["hyprpaper", "preload", str(abs_path)])
    _run_hyprctl(["hyprpaper", "wallpaper", f"{monitor},{abs_path}"])


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"version": 1, "monitors": {}}

    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": 1, "monitors": {}}
    if "monitors" not in data or not isinstance(data.get("monitors"), dict):
        data["monitors"] = {}
    if "version" not in data:
        data["version"] = 1
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
    source_path: Path,
    loaded_path: Path,
) -> None:
    state = load_state(state_path)
    monitors = state.setdefault("monitors", {})
    monitors[monitor] = {
        "theme": theme,
        "source_path": str(source_path),
        "loaded_path": str(loaded_path),
    }
    save_state(state_path, state)


def apply_wallpaper(
    *,
    monitor: str,
    theme: str,
    src: Path,
    loaded_dir: Path | None = None,
    state_path: Path | None = None,
) -> Path:
    loaded_dir = default_loaded_dir() if loaded_dir is None else loaded_dir
    state_path = (loaded_dir / "state.json") if state_path is None else state_path

    loaded_path = copy_into_loaded(
        src=src,
        loaded_dir=loaded_dir,
        theme=theme,
        monitor=monitor,
    )
    set_wallpaper_hyprpaper(monitor=monitor, path=loaded_path)
    record_assignment(
        state_path=state_path,
        monitor=monitor,
        theme=theme,
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
        src = src_dir / "test.jpg"
        src.write_bytes(b"pypaper-test")

        dest = copy_into_loaded(
            src=src,
            loaded_dir=tmp_loaded,
            theme="ThemeX",
            monitor="MON-1",
        )
        assert dest.exists(), "copy_into_loaded did not create dest"
        assert dest.read_bytes() == src.read_bytes(), "copied file contents differ"
        assert dest.name.startswith(sha1_file(src)), (
            "dest filename should start with sha1"
        )

        record_assignment(
            state_path=tmp_state,
            monitor="MON-1",
            theme="ThemeX",
            source_path=src,
            loaded_path=dest,
        )
        state = load_state(tmp_state)
        assert state["monitors"]["MON-1"]["loaded_path"] == str(dest)

    print("image.py self-test OK")

    # Optional: apply a wallpaper using hyprctl.
    # Usage: python image.py --apply <MONITOR> <THEME> <IMAGE_PATH>
    if len(argv) >= 5 and argv[1] == "--apply":
        monitor = argv[2]
        theme = argv[3]
        src = Path(argv[4])
        loaded_path = apply_wallpaper(monitor=monitor, theme=theme, src=src)
        print(f"applied monitor={monitor} loaded_path={loaded_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test(sys.argv))
