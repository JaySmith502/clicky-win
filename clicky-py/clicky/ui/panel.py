"""Frameless dark panel for ClickyWin.

Hosts all panel sub-views (waveform, transcript, response, banner, etc).
Positioned near the system tray icon via show_near_tray(). Dismissal is
handled by a global pynput mouse listener (click-outside → hide), since
Qt focus semantics for frameless Tool windows on Windows 11 are
unreliable. Escape-to-dismiss is provided by HotkeyMonitor via a signal
wired up in ``clicky.app``.
"""

from __future__ import annotations

from pynput import mouse
from PySide6.QtCore import QPoint, QRect, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QHideEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QLabel,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from clicky.design_system import DS
from clicky.state import VoiceState
from clicky.ui.model_picker import ModelPicker
from clicky.ui.permissions_indicator import PermissionsIndicator
from clicky.ui.response_view import ResponseView
from clicky.ui.status_banner import StatusBanner
from clicky.ui.transcript_view import TranscriptView
from clicky.ui.waveform_view import WaveformView

_BG_COLOR = DS.Colors.panel_bg
_TEXT_COLOR = DS.Colors.text_primary
_CORNER_RADIUS = DS.CornerRadius.large
_MIN_WIDTH = 420
_MIN_HEIGHT = 360
_TRAY_MARGIN = 8  # px between tray icon and panel edge


class Panel(QWidget):
    """Frameless translucent dark panel anchored near the system tray."""

    # Emitted from the pynput mouse listener background thread with the
    # click's global screen coordinates. Connected with QueuedConnection
    # so the slot runs on the main Qt thread.
    _external_mouse_press = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        # Tool hides the panel from the taskbar. We deliberately avoid
        # relying on Qt focus events for dismissal — click-outside is
        # handled by a pynput global mouse hook.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)

        self._mouse_listener: mouse.Listener | None = None
        self._external_mouse_press.connect(
            self._on_external_mouse_press,
            Qt.ConnectionType.QueuedConnection,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Public: app.py wires CompanionManager error/success signals here.
        self.banner = StatusBanner(self)
        layout.addWidget(self.banner)

        self._waveform = WaveformView(self)
        self._waveform.hide()

        # Public: app.py wires TranscriptionClient signals to these slots.
        self.transcript = TranscriptView(self)
        self.transcript.hide()

        # Public: app.py wires CompanionManager response signals here.
        self.response = ResponseView(self)
        self.response.hide()

        self._placeholder = QLabel("ClickyWin \u2014 Hold Ctrl+Alt to talk")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {_TEXT_COLOR}; font-size: 14px;"
        )
        layout.addWidget(self._waveform)
        layout.addWidget(self.transcript)
        layout.addWidget(self.response)
        layout.addStretch(1)
        layout.addWidget(self._placeholder)
        layout.addStretch(1)

        # Public: app.py sets initial model and connects model_changed.
        self.model_picker = ModelPicker(self)
        layout.addWidget(self.model_picker)

        # Public: app.py wires mic.error to set_mic_status(False).
        self.permissions = PermissionsIndicator(self)
        layout.addWidget(self.permissions)

    # ------------------------------------------------------------------
    # state / audio wiring
    # ------------------------------------------------------------------
    def set_state(self, state: VoiceState) -> None:
        """Update panel sub-views to reflect the given voice state.

        LISTENING:  waveform + transcript visible, response hidden.
        PROCESSING: waveform hidden, transcript visible, response hidden.
        RESPONDING: waveform hidden, transcript + response visible.
        IDLE:       everything hidden, transcript + response cleared.
        """
        if state is VoiceState.LISTENING:
            self._waveform.show()
            self._waveform.start()
            self.transcript.show()
            self.response.hide()
        elif state is VoiceState.PROCESSING:
            self._waveform.stop()
            self._waveform.hide()
            self.transcript.show()
            self.response.hide()
        elif state is VoiceState.RESPONDING:
            self._waveform.stop()
            self._waveform.hide()
            self.transcript.show()
            self.response.show()
        else:
            self._waveform.stop()
            self._waveform.hide()
            self.transcript.hide()
            self.transcript.clear()
            self.response.hide()
            self.response.clear()

    def set_audio_level(self, level: float) -> None:
        """Forward a mic RMS level (in [0, 1]) to the waveform."""
        self._waveform.push_level(level)

    # ------------------------------------------------------------------
    # PanelVisibilityController protocol (used by CompanionManager)
    # ------------------------------------------------------------------
    def hide_for_capture(self) -> None:
        self.setWindowOpacity(0.0)

    def restore_after_capture(self) -> None:
        self.setWindowOpacity(1.0)

    # ------------------------------------------------------------------
    # Qt event overrides
    # ------------------------------------------------------------------
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

    def showEvent(self, event: QShowEvent) -> None:  # noqa: ARG002
        self.raise_()
        self.activateWindow()
        self._start_mouse_listener()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: ARG002
        self._stop_mouse_listener()

    # ------------------------------------------------------------------
    # Global mouse listener (for click-outside dismissal)
    # ------------------------------------------------------------------
    def _start_mouse_listener(self) -> None:
        if self._mouse_listener is not None:
            return

        def on_click(
            x: float, y: float, button: mouse.Button, pressed: bool
        ) -> None:  # noqa: ARG001 - pynput signature
            if not pressed:
                return
            # Hop to main thread via queued signal.
            self._external_mouse_press.emit(int(x), int(y))

        self._mouse_listener = mouse.Listener(on_click=on_click)
        self._mouse_listener.start()

    def _stop_mouse_listener(self) -> None:
        listener = self._mouse_listener
        self._mouse_listener = None
        if listener is not None:
            listener.stop()

    @Slot(int, int)
    def _on_external_mouse_press(self, x: int, y: int) -> None:
        if not self.isVisible():
            return
        if not self.frameGeometry().contains(QPoint(x, y)):
            self.hide()

    # ------------------------------------------------------------------
    # positioning
    # ------------------------------------------------------------------
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
