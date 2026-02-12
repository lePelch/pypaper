from __future__ import annotations

import sys

from .ui import main as _main


def main() -> int:
    return _main(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
