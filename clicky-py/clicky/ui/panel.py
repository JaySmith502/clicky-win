"""Frameless dark panel for ClickyWin.

Hosts all panel sub-views (waveform, transcript, response, banner, etc).
Positioned near the system tray icon via show_near_tray(). Dismisses on
Escape or click-outside-panel.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

_BG_COLOR = "#1a1a1a"
_TEXT_COLOR = "#e0e0e0"
_CORNER_RADIUS = 16
_MIN_WIDTH = 420
_MIN_HEIGHT = 360
_TRAY_MARGIN = 8  # px between tray icon and panel edge


class Panel(QWidget):
    """Frameless translucent dark panel anchored near the system tray."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self._placeholder = QLabel("ClickyWin \u2014 Hold Ctrl+Alt to talk")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {_TEXT_COLOR}; font-size: 14px;"
        )
        layout.addStretch(1)
        layout.addWidget(self._placeholder)
        layout.addStretch(1)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002 - Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(
            float(rect.x()),
            float(rect.y()),
            float(rect.width()),
            float(rect.height()),
            float(_CORNER_RADIUS),
            float(_CORNER_RADIUS),
        )
        painter.fillPath(path, QColor(_BG_COLOR))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self.isVisible():
            return super().eventFilter(watched, event)
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            # event.globalPosition() returns QPointF in recent Qt.
            global_pos = event.globalPosition().toPoint()
            if not self.frameGeometry().contains(global_pos):
                self.hide()
        elif event_type == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            # Tool windows on Windows don't always receive keyboard focus,
            # so keyPressEvent never fires. Catch Escape at the app-event
            # level instead — this runs regardless of which widget has focus.
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(watched, event)

    def show_near_tray(self, tray_icon: QSystemTrayIcon) -> None:
        """Show the panel positioned near the given tray icon.

        Falls back to cursor-screen center when the tray geometry is empty
        (common on Windows before the icon has fully registered). Always
        clamps to the containing screen's available geometry.
        """
        target_point = self._compute_target_position(tray_icon)

        screen = QGuiApplication.screenAt(target_point)
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        panel_w = self.width() or _MIN_WIDTH
        panel_h = self.height() or _MIN_HEIGHT

        x = max(avail.left(), min(target_point.x(), avail.right() - panel_w))
        y = max(avail.top(), min(target_point.y(), avail.bottom() - panel_h))

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _compute_target_position(self, tray_icon: QSystemTrayIcon) -> QPoint:
        tray_geo: QRect = tray_icon.geometry()
        panel_w = self.width() or _MIN_WIDTH
        panel_h = self.height() or _MIN_HEIGHT

        if tray_geo.isEmpty() or tray_geo.width() == 0:
            # Fallback: center on the screen the cursor is currently on.
            cursor_pos = QCursor.pos()
            screen = (
                QGuiApplication.screenAt(cursor_pos)
                or QGuiApplication.primaryScreen()
            )
            avail = screen.availableGeometry()
            return QPoint(
                avail.center().x() - panel_w // 2,
                avail.center().y() - panel_h // 2,
            )

        # Align the panel's bottom-right just above the tray icon's top-right.
        # If the tray is near the top of its screen, fall back to below.
        screen = (
            QGuiApplication.screenAt(tray_geo.center())
            or QGuiApplication.primaryScreen()
        )
        avail = screen.availableGeometry()

        if tray_geo.top() - panel_h - _TRAY_MARGIN >= avail.top():
            x = tray_geo.right() - panel_w
            y = tray_geo.top() - panel_h - _TRAY_MARGIN
        else:
            x = tray_geo.right() - panel_w
            y = tray_geo.bottom() + _TRAY_MARGIN
        return QPoint(x, y)
