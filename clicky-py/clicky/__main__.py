"""ClickyWin entry point: `python -m clicky`."""

from __future__ import annotations

import sys

from clicky.app import bootstrap


def main() -> int:
    result = bootstrap()
    if result.was_first_run:
        print(f"[clicky] first run: created config at {result.config_path}")
    if result.config_error is not None:
        print(f"[clicky] config error: {result.config_error}", file=sys.stderr)
    else:
        assert result.config is not None
        print(f"[clicky] config loaded: worker_url={result.config.worker_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
