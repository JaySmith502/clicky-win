"""Cursor-following companion overlay widget."""

from __future__ import annotations

import logging

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from clicky.ui.companion_position import compute_position, should_update

logger = logging.getLogger(__name__)


class CompanionWidget(QWidget):
    """Small cursor-following overlay. Shows a blue triangle when idle."""

    # Dimensions -- enough for triangle + future waveform expansion
    WIDGET_W = 120
    WIDGET_H = 50

    # Idle triangle
    TRIANGLE_SIZE = 14  # px height of equilateral triangle
    IDLE_OPACITY = 0.6
    IDLE_COLOR = QColor("#4a9eff")

    # Cursor tracking
    TRACK_INTERVAL_MS = 33  # ~30fps
    OFFSET = 20
    EDGE_MARGIN = 80

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(self.WIDGET_W, self.WIDGET_H)

        self._prev_x = 0
        self._prev_y = 0

        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(self.TRACK_INTERVAL_MS)
        self._cursor_timer.timeout.connect(self._track_cursor)

    def show(self) -> None:
        super().show()
        # Initialize position immediately
        self._track_cursor(force=True)
        self._cursor_timer.start()

    def hide(self) -> None:
        self._cursor_timer.stop()
        super().hide()

    def _track_cursor(self, force: bool = False) -> None:
        pos = QCursor.pos()  # Global screen coordinates
        cx, cy = pos.x(), pos.y()

        if not force and not should_update(self._prev_x, self._prev_y, cx, cy):
            return

        screen = QApplication.screenAt(pos)
        if screen is None:
            return

        geo = screen.geometry()
        screen_rect = (geo.x(), geo.y(), geo.width(), geo.height())

        placement = compute_position(
            cx,
            cy,
            screen_rect,
            companion_size=(self.WIDGET_W, self.WIDGET_H),
            offset=self.OFFSET,
            edge_margin=self.EDGE_MARGIN,
        )

        self.move(placement.x, placement.y)
        self._prev_x = cx
        self._prev_y = cy

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self.IDLE_COLOR)
        color.setAlphaF(self.IDLE_OPACITY)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        # Draw equilateral triangle pointing right, vertically centered
        h = self.TRIANGLE_SIZE
        w = h * 0.866  # equilateral: width = height * sqrt(3)/2
        cy = self.WIDGET_H / 2

        triangle = QPolygonF(
            [
                QPointF(0, cy - h / 2),  # top-left
                QPointF(w, cy),  # right point
                QPointF(0, cy + h / 2),  # bottom-left
            ]
        )

        painter.drawPolygon(triangle)
        painter.end()
