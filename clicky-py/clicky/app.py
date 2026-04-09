"""ClickyWin QApplication bootstrap.

Resolves the config file path via platformdirs, ensures the file exists
(creating from config.example.toml on first run), loads it, and holds
the resulting Config for downstream components to read.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir, user_log_dir
from PySide6.QtWidgets import QApplication

from clicky.config import Config, ConfigError

APP_NAME = "ClickyWin"
APP_AUTHOR = "ClickyWin"


@dataclass
class BootstrapResult:
    app: QApplication
    config: Config | None
    config_error: ConfigError | None
    was_first_run: bool
    config_path: Path
    log_dir: Path


def _example_config_path() -> Path:
    # config.example.toml sits next to the clicky package directory
    # (i.e. inside clicky-py/, alongside clicky/).
    return Path(__file__).resolve().parent.parent / "config.example.toml"


def bootstrap(argv: list[str] | None = None) -> BootstrapResult:
    argv = argv if argv is not None else sys.argv
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_AUTHOR)
    app.setQuitOnLastWindowClosed(False)  # tray app — closing panel must not quit

    # Pass appauthor=False so platformdirs does NOT nest a redundant
    # second "ClickyWin" folder inside the first (which happens when
    # appname == appauthor on Windows). We want %APPDATA%\ClickyWin\config.toml,
    # not %APPDATA%\ClickyWin\ClickyWin\config.toml.
    config_dir = Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))
    config_path = config_dir / "config.toml"
    log_dir = Path(user_log_dir(APP_NAME, appauthor=False))

    was_first_run = Config.ensure_exists(config_path, _example_config_path())

    try:
        config = Config.from_path(config_path)
        config_error = None
    except ConfigError as exc:
        config = None
        config_error = exc

    return BootstrapResult(
        app=app,
        config=config,
        config_error=config_error,
        was_first_run=was_first_run,
        config_path=config_path,
        log_dir=log_dir,
    )
