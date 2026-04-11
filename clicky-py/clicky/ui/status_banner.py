"""Status banner widget for ClickyWin.

Displays contextual messages (info, warning, error) at the top of the
panel with colour-coded backgrounds and an optional action button.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

_COLORS = {
    "error": "#8B0000",
    "warning": "#8B6508",
    "info": "#1a3a5c",
}


class StatusBanner(QWidget):
    """Colour-coded banner for surfacing errors, warnings, and info."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: white; font-size: 13px;")
        layout.addWidget(self._label, stretch=1)

        self._action_btn = QPushButton()
        self._action_btn.setStyleSheet(
            "color: white; background: transparent; border: 1px solid white;"
            " border-radius: 4px; padding: 4px 10px; font-size: 12px;"
        )
        self._action_btn.hide()
        layout.addWidget(self._action_btn)

        self._on_action: Callable[[], object] | None = None
        self._action_btn.clicked.connect(self._handle_action)

        self.hide()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def show_error(
        self,
        text: str,
        action_label: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        self._show("error", text, action_label, on_action)

    def show_warning(
        self,
        text: str,
        action_label: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        self._show("warning", text, action_label, on_action)

    def show_info(self, text: str) -> None:
        self._show("info", text)

    @Slot()
    def clear(self) -> None:
        self.hide()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _show(
        self,
        mode: str,
        text: str,
        action_label: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        bg = _COLORS[mode]
        self.setStyleSheet(
            f"background-color: {bg}; border-radius: 8px;"
        )
        self._label.setText(text)

        if action_label and on_action:
            self._action_btn.setText(action_label)
            self._on_action = on_action
            self._action_btn.show()
        else:
            self._action_btn.hide()
            self._on_action = None

        self.show()

    def _handle_action(self) -> None:
        if self._on_action is not None:
            self._on_action()
