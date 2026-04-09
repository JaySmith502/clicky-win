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
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from clicky.config import Config, ConfigError
from clicky.hotkey import HotkeyMonitor
from clicky.state import VoiceState
from clicky.ui.panel import Panel
from clicky.ui.tray_icon import TrayIcon

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


def run() -> int:
    """Start the ClickyWin tray app and run the Qt event loop.

    Wires together the tray icon, floating panel, and global hotkey
    monitor. Blocks until the user quits via the tray menu.
    """
    result = bootstrap()

    if result.was_first_run:
        print(
            f"[clicky] first run: created config at {result.config_path}",
            file=sys.stderr,
        )

    if result.config_error is not None:
        # Phase 1: log to stderr and proceed. Phase 2+ will surface this
        # as a banner inside the panel.
        print(
            f"[clicky] config error: {result.config_error}",
            file=sys.stderr,
        )

    tray_icon = TrayIcon(initial_state=VoiceState.IDLE)
    panel = Panel()

    def _toggle_panel() -> None:
        if panel.isVisible():
            panel.hide()
        else:
            panel.show_near_tray(tray_icon)

    tray_icon.toggle_panel_requested.connect(_toggle_panel)

    hotkey_binding = result.config.hotkey if result.config is not None else "ctrl+alt"
    hotkey_monitor = HotkeyMonitor(binding=hotkey_binding)

    def _on_hotkey_pressed() -> None:
        print("[clicky] hotkey pressed", file=sys.stderr)
        panel.show_near_tray(tray_icon)

    def _on_hotkey_released() -> None:
        print("[clicky] hotkey released", file=sys.stderr)

    def _on_hotkey_cancelled() -> None:
        print("[clicky] hotkey cancelled", file=sys.stderr)

    def _on_escape_pressed() -> None:
        # Only hide if the panel is visible — otherwise the Escape key
        # has nothing to act on.
        if panel.isVisible():
            panel.hide()

    hotkey_monitor.pressed.connect(_on_hotkey_pressed)
    hotkey_monitor.released.connect(_on_hotkey_released)
    hotkey_monitor.cancelled.connect(_on_hotkey_cancelled)
    hotkey_monitor.escape_pressed.connect(_on_escape_pressed)

    hotkey_monitor.start()
    tray_icon.show()

    # Ensure the pynput listener thread is stopped before the app exits,
    # otherwise Python may hang on interpreter shutdown waiting for it
    # (pynput's helper thread is not always daemonic on Windows).
    result.app.aboutToQuit.connect(hotkey_monitor.stop)

    if result.was_first_run:
        # Delay the first-run auto-show so the tray icon has time to be
        # laid out — otherwise tray_icon.geometry() returns an empty rect
        # on Windows and the panel falls back to screen-centering.
        QTimer.singleShot(100, lambda: panel.show_near_tray(tray_icon))

    return result.app.exec()
