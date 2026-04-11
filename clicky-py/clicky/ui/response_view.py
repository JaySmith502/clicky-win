"""Response view widget for ClickyWin.

Displays Claude's streaming response text in a scrollable, read-only
QTextEdit. Supports delta-based streaming via ``append_delta`` and
full replacement via ``set_full``. Auto-scrolls to bottom on new content.

See ``clicky.clients`` for the AI response lifecycle.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from clicky.design_system import DS


class ResponseView(QWidget):
    """Scrollable display for Claude's streaming response text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 160)

        self._edit = QTextEdit(self)
        self._edit.setReadOnly(True)
        self._edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._edit.setStyleSheet(f"color: {DS.Colors.text_white}; background: transparent;")
        self._edit.setFrameShape(QTextEdit.Shape.NoFrame)
        self._edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

    @Slot()
    def clear(self) -> None:
        """Clear all response text."""
        self._edit.clear()

    @Slot(str)
    def append_delta(self, text: str) -> None:
        """Append a streaming delta chunk and scroll to bottom."""
        cursor = self._edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._edit.setTextCursor(cursor)
        self._edit.ensureCursorVisible()

    @Slot(str)
    def set_full(self, text: str) -> None:
        """Replace the entire response with *text* and scroll to bottom."""
        self._edit.setPlainText(text)
        self._edit.moveCursor(self._edit.textCursor().MoveOperation.End)
        self._edit.ensureCursorVisible()
