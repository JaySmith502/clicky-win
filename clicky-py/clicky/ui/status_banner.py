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

from clicky.design_system import DS

_COLORS = {
    "error": DS.Colors.error_bg,
    "warning": DS.Colors.warning_bg,
    "info": DS.Colors.info_bg,
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
        self._label.setStyleSheet(f"color: {DS.Colors.text_white}; font-size: 13px;")
        layout.addWidget(self._label, stretch=1)

        self._action_btn = QPushButton()
        self._action_btn.setStyleSheet(
            f"color: {DS.Colors.text_white}; background: transparent; border: 1px solid {DS.Colors.text_white};"
            f" border-radius: {DS.CornerRadius.xs}px; padding: {DS.Spacing.xs}px 10px; font-size: {DS.Fonts.size_sm}px;"
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
            f"background-color: {bg}; border-radius: {DS.CornerRadius.small}px;"
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
