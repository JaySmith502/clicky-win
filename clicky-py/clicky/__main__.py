"""ClickyWin entry point: `python -m clicky`."""

from __future__ import annotations

from clicky.app import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
