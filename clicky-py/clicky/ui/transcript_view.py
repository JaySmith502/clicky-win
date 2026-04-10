"""Transcript view widget for ClickyWin.

Displays two lines of transcript text from the AssemblyAI stream:
an interim (in-flight) line in gray italic, and a final line in
white regular weight. Uses a single QLabel with rich text so both
lines render in one widget without layout jitter.

See ``clicky.clients.transcription_client`` for the websocket lifecycle.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_INTERIM_COLOR = "#888888"
_FINAL_COLOR = "#ffffff"
_EMPTY_PLACEHOLDER = "&nbsp;"


class TranscriptView(QWidget):
    """Two-line transcript display: interim (gray italic) + final (white)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 72)

        self._interim: str = ""
        self._final: str = ""

        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._render()

    @Slot(str)
    def set_interim(self, text: str) -> None:
        self._interim = text
        self._render()

    @Slot(str)
    def set_final(self, text: str) -> None:
        # Once a final arrives, the interim for that utterance is
        # done — clear it so we don't show stale in-flight text.
        self._final = text
        self._interim = ""
        self._render()

    @Slot()
    def clear(self) -> None:
        self._interim = ""
        self._final = ""
        self._render()

    def _render(self) -> None:
        interim_body = html.escape(self._interim) if self._interim else _EMPTY_PLACEHOLDER
        final_body = html.escape(self._final) if self._final else _EMPTY_PLACEHOLDER
        markup = (
            f'<span style="color:{_INTERIM_COLOR}; font-style:italic;">{interim_body}</span><br>'
            f'<span style="color:{_FINAL_COLOR};">{final_body}</span>'
        )
        self._label.setText(markup)
