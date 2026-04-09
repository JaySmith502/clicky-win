"""System tray icon for ClickyWin.

Holds the current VoiceState, rebuilds its icon via icon_factory whenever
state changes, and exposes a toggle_panel_requested signal on left-click.
Right-click menu has a single "Quit" action.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from clicky.icon_factory import icon_for_state
from clicky.state import VoiceState


class TrayIcon(QSystemTrayIcon):
    """QSystemTrayIcon that reflects VoiceState via color-coded icons."""

    toggle_panel_requested = Signal()

    def __init__(self, initial_state: VoiceState = VoiceState.IDLE) -> None:
        super().__init__()
        self._state = initial_state
        self.setIcon(icon_for_state(self._state))
        self.setToolTip("ClickyWin")

        menu = QMenu()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)
        self._menu = menu
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def set_state(self, state: VoiceState) -> None:
        """Update the tray icon to reflect a new VoiceState."""
        if state == self._state:
            return
        self._state = state
        self.setIcon(icon_for_state(state))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel_requested.emit()

    def _on_quit(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
