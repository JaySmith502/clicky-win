"""Mic permissions indicator for ClickyWin panel."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from clicky.design_system import DS


class PermissionsIndicator(QWidget):
    """Colored dot + label showing mic status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._dot = QLabel("\u25cf", self)
        self._dot.setFixedWidth(16)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._dot)

        self._label = QLabel("mic ok", self)
        self._label.setStyleSheet(f"color: {DS.Colors.text_secondary}; font-size: {DS.Fonts.size_sm}px;")
        layout.addWidget(self._label)

        self._fix_btn = QPushButton("Open Settings", self)
        self._fix_btn.setStyleSheet(
            f"color: {DS.Colors.text_white}; background: {DS.Colors.surface}; "
            f"border: 1px solid {DS.Colors.border}; border-radius: {DS.CornerRadius.xs}px; "
            f"padding: 2px 8px; font-size: {DS.Fonts.size_sm}px;"
        )
        self._fix_btn.clicked.connect(self._open_mic_settings)
        self._fix_btn.hide()
        layout.addWidget(self._fix_btn)
        layout.addStretch(1)

        self.set_mic_status(True)  # default ok

    @Slot(bool)
    def set_mic_status(self, ok: bool) -> None:
        if ok:
            self._dot.setStyleSheet(f"color: {DS.Colors.accent_green}; font-size: 12px;")
            self._label.setText("mic ok")
            self._fix_btn.hide()
        else:
            self._dot.setStyleSheet(f"color: {DS.Colors.error_red}; font-size: 12px;")
            self._label.setText("mic blocked")
            self._fix_btn.show()

    def _open_mic_settings(self) -> None:
        os.startfile("ms-settings:privacy-microphone")
