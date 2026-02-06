# AGENTS.md (pypaper)

For agentic coding tools operating in this repo. Keep changes small, readable,
and aligned with existing conventions.

## Repo Facts
- Python: `>=3.14` (`pyproject.toml`, `.python-version`)
- Runner/manager: `uv` (`uv.lock` is authoritative)
- UI: PySide6 (Qt)
- Entrypoint today: `main.py`
- Placeholders: `image.py`, `monitor.py`, `theme.py` (currently empty)

## Cursor / Copilot Rules
No repo-specific rule files found:
- `.cursor/rules/` (missing)
- `.cursorrules` (missing)
- `.github/copilot-instructions.md` (missing)
If you add them later, update this section and follow them.

## Commands

### Setup
- Sync env: `uv sync`
- Verify interpreter: `uv run python --version`

### Dependency Changes (uv)
- Add a runtime dependency: `uv add <pkg>`
- Add a dev dependency: `uv add --dev <pkg>`
- Remove a dependency: `uv remove <pkg>`
- Update lockfile (when deps change): `uv lock`
- CI-style sync from lock (no changes): `uv sync --frozen`

Lockfile policy:
- Treat `uv.lock` as the source of truth.
- If you change `pyproject.toml` dependencies, update `uv.lock` too.

### Run ("Build")
No packaging build is configured (no `[build-system]`). Treat build as run:
- `uv run python main.py`
If/when a package exists, prefer: `uv run python -m pypaper`

### Lint / Format / Typecheck
Current state: none configured.
Recommended (add as dev deps if needed): `ruff`, `pyright` (or `mypy`).
Once installed:
- Lint: `uv run ruff check .`
- Fix (safe): `uv run ruff check . --fix`
- Format: `uv run ruff format .`
- Types: `uv run pyright`

### Tests (single test emphasis)
Current state: no `tests/` and no runner configured.
If you add `pytest`:
- All: `uv run pytest`
- File: `uv run pytest tests/test_something.py`
- Single test: `uv run pytest tests/test_something.py::TestClass::test_name`
- Substring: `uv run pytest -k "substring"`
If you use `unittest`:
- All: `uv run python -m unittest`
- Single test: `uv run python -m unittest tests.test_module.TestClass.test_name`
Qt tests: prefer pure-logic unit tests; consider `pytest-qt` only if needed.

Test conventions (if you add tests):
- Name files `tests/test_*.py` and tests `test_*`.
- Prefer deterministic tests: no sleeps, minimal timing assumptions.
- Keep UI tests small; exercise non-UI logic in normal unit tests.

## Code Style

### Imports
- Order: stdlib, third-party, local; blank line between groups
- Sort alphabetically within each group; avoid `from x import *`

```python
import random
import sys

from PySide6 import QtCore, QtWidgets
```

### Formatting
- 4 spaces; "Black-like" formatting even if Black is not installed
- Keep lines ~88-100 chars; readability wins
- Use trailing commas in multi-line calls/containers

```python
self.text = QtWidgets.QLabel(
    "Hello World",
    alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
)
```

### Naming
- Files/modules: `snake_case.py`; classes: `PascalCase`
- Functions/vars: `snake_case`; constants: `UPPER_SNAKE_CASE`
- Qt slots/handlers: explicit verbs (e.g., `on_apply_clicked`, `update_preview`)

### Types
- Add hints when they prevent mistakes or clarify behavior
- Prefer stdlib typing; use concrete Qt types in public signatures when helpful
- Avoid over-annotating obvious locals in tiny functions

### Error Handling
- Catch narrow exceptions; avoid blanket `except Exception`
- In slots/UI boundaries: never silently swallow errors
- For recoverable problems: show a message (e.g., `QMessageBox`) and log details
- For programmer errors: prefer assertions/letting exceptions surface in dev

### Logging
- Prefer `logging` over `print` for non-trivial output
- Keep logs concise; avoid per-event spam

### Qt / PySide6 Patterns
- No side effects at import time; start UI under `if __name__ == "__main__":`
- Keep constructors light; factor into `_build_ui()`, `_connect_signals()`, etc.
- Do not block the UI thread; use `QThread`/`QtConcurrent` for long work

Qt ergonomics:
- Prefer signals/slots over polling.
- Avoid global `QApplication` state where possible; keep it in the entrypoint.
- When doing background work, marshal results back to the UI thread.

### Filesystem / Paths
- Use `pathlib.Path`; don’t assume the current working directory
- Don’t commit local artifacts like `.venv/`, `__pycache__/`, build outputs

### Unicode
- Default to ASCII in identifiers/comments
- Unicode is OK in user-facing UI strings (already used in `main.py`)

## Project Structure (If You Expand It)
- Prefer `pypaper/` package + `pypaper/__main__.py` for `python -m pypaper`
- Add `tests/` (pytest) if/when tests exist
- When adding deps: update `pyproject.toml` and re-lock with `uv`

## Git / Workspace Hygiene
- Never revert unrelated local changes without being asked.
- Keep diffs focused; avoid drive-by reformatting.
- Don’t commit secrets or local artifacts (`.venv/`, credentials, large binaries).

## Suggested Defaults (When Unsure)
- Prefer the simplest implementation that matches existing patterns.
- Add small helper functions instead of clever inline logic.
- If you must introduce a tool (pytest/ruff/pyright), configure it in
  `pyproject.toml` and document the new commands here.
