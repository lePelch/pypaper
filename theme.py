from __future__ import annotations

import sys
from pathlib import Path


IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }
)


def list_themes(theme_root: Path) -> list[str]:
    """Return theme folder names under theme_root.

    A "theme" is a direct subdirectory of theme_root.
    """

    if not theme_root.exists():
        return []

    themes: list[str] = []
    for child in theme_root.iterdir():
        if not child.is_dir():
            continue

        name = child.name
        if name.startswith("."):
            continue

        # Common non-theme folders.
        if name in {"__pycache__", "Loaded"}:
            continue

        # Only keep folders that actually contain images.
        if not list_images(child):
            continue

        themes.append(name)

    return sorted(themes, key=str.casefold)


def list_images(theme_dir: Path) -> list[Path]:
    """Return image files (direct children) in a theme directory."""

    if not theme_dir.exists():
        return []

    images: list[Path] = []
    for child in theme_dir.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        images.append(child)

    return sorted(images, key=lambda p: p.name.casefold())


def _self_test(argv: list[str]) -> int:
    theme_root = Path(argv[1]) if len(argv) > 1 else Path("pypaper")

    themes = list_themes(theme_root)
    print(f"theme_root={theme_root.resolve()}")
    print(f"themes={themes}")

    for theme in themes:
        theme_dir = theme_root / theme
        images = list_images(theme_dir)
        assert images, f"Theme {theme_dir} has no images (should not happen)"
        missing = [p for p in images if not p.exists()]
        assert not missing, f"Missing files in {theme_dir}: {missing!r}"
        print(f"{theme}: {len(images)} images")

    # Soft expectations for this repo layout.
    if theme_root.name == "pypaper" and theme_root.exists():
        assert themes, "No themes found under ./pypaper (expected at least one)"

    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test(sys.argv))
