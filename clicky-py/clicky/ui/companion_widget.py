"""Cursor-following companion overlay widget."""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QCursor, QPainter, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from clicky.design_system import DS
from clicky.state import VoiceState
from clicky.ui.companion_position import compute_position, should_update
from clicky.ui.waveform_bars import compute_bar_heights

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

    # Waveform
    WAVEFORM_BAR_COUNT = 8
    WAVEFORM_WIDTH = 60       # total width of all bars
    WAVEFORM_MAX_HEIGHT = 24  # max bar height
    WAVEFORM_MIN_HEIGHT = 2   # min bar height (silent)
    WAVEFORM_GAP = 2          # gap between bars
    WAVEFORM_GAIN = 12.0      # amplify RMS (speech is ~0.01-0.05)

    # Animation durations
    EXPAND_DURATION_MS = 150
    CONTRACT_DURATION_MS = 300

    # Active triangle
    ACTIVE_TRIANGLE_SIZE = 18

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

        self._state = VoiceState.IDLE
        self._audio_level = 0.0
        self._output_level = 0.0  # system audio output level for responding waveform
        self._scale = 0.0       # 0.0 = idle, 1.0 = fully expanded (waveform visible)
        self._opacity = self.IDLE_OPACITY

        self._frozen = False  # freeze cursor tracking during RESPONDING

        # Animation for waveform expand/contract
        self._scale_anim = QPropertyAnimation(self, b"anim_scale")
        self._opacity_anim = QPropertyAnimation(self, b"anim_opacity")

        # Pulse animation for processing/responding states
        self._pulse_scale = 1.0
        self._pulse_color: str | None = None
        self._pulse_anim = QPropertyAnimation(self, b"anim_pulse")

        # Error flash timer
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(1000)  # 1 second red flash
        self._error_timer.timeout.connect(self._end_error_flash)
        self._error_flash = False

        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(self.TRACK_INTERVAL_MS)
        self._cursor_timer.timeout.connect(self._track_cursor)

    # ------------------------------------------------------------------
    # Qt properties for animation
    # ------------------------------------------------------------------

    def _get_anim_scale(self) -> float:
        return self._scale

    def _set_anim_scale(self, val: float) -> None:
        self._scale = val
        self.update()  # trigger repaint

    anim_scale = Property(float, _get_anim_scale, _set_anim_scale)

    def _get_anim_opacity(self) -> float:
        return self._opacity

    def _set_anim_opacity(self, val: float) -> None:
        self._opacity = val
        self.update()

    anim_opacity = Property(float, _get_anim_opacity, _set_anim_opacity)

    def _get_anim_pulse(self) -> float:
        return self._pulse_scale

    def _set_anim_pulse(self, val: float) -> None:
        self._pulse_scale = val
        self.update()

    anim_pulse = Property(float, _get_anim_pulse, _set_anim_pulse)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(self, state: VoiceState) -> None:
        if state == self._state:
            return
        self._state = state

        if state == VoiceState.LISTENING:
            self._frozen = False
            self._stop_pulse()
            self._animate_expand()
        elif state == VoiceState.PROCESSING:
            self._animate_to_pulse()
        elif state == VoiceState.RESPONDING:
            self._frozen = True  # freeze position during TTS
            self._start_pulse(DS.Colors.companion_responding)
        elif state == VoiceState.IDLE:
            self._frozen = False
            self._stop_pulse()
            self._animate_contract()

        self.update()

    def set_audio_level(self, level: float) -> None:
        self._audio_level = level
        if self._state == VoiceState.LISTENING:
            self.update()

    def set_output_level(self, level: float) -> None:
        self._output_level = level
        if self._state == VoiceState.RESPONDING:
            self.update()

    # ------------------------------------------------------------------
    # Animation helpers
    # ------------------------------------------------------------------

    def _animate_expand(self) -> None:
        """Expand waveform: scale 0->1, opacity to full."""
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.setDuration(self.EXPAND_DURATION_MS)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.start()

        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setDuration(self.EXPAND_DURATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._opacity_anim.start()

    def _animate_contract(self) -> None:
        """Contract waveform: scale 1->0, opacity to idle."""
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(0.0)
        self._scale_anim.setDuration(self.CONTRACT_DURATION_MS)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._scale_anim.start()

        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(self.IDLE_OPACITY)
        self._opacity_anim.setDuration(self.CONTRACT_DURATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._opacity_anim.start()

    # ------------------------------------------------------------------
    # Error flash
    # ------------------------------------------------------------------

    def flash_error(self, _msg: str = "") -> None:
        """Brief red flash on error, then return to current state."""
        self._error_flash = True
        self._error_timer.start()
        self.update()

    def _end_error_flash(self) -> None:
        self._error_flash = False
        self.update()

    # ------------------------------------------------------------------
    # Pulse animation helpers
    # ------------------------------------------------------------------

    def _animate_to_pulse(self) -> None:
        """Transition from waveform to pulsing dot (processing)."""
        # Contract waveform
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(0.3)  # small dot, not fully contracted
        self._scale_anim.setDuration(200)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.start()

        # Keep full opacity
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setDuration(200)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._opacity_anim.start()

        self._start_pulse(DS.Colors.companion_processing)

    def _start_pulse(self, color_hex: str) -> None:
        """Start looping pulse animation."""
        self._pulse_color = color_hex
        self._pulse_anim.stop()
        self._pulse_anim.setStartValue(0.8)
        self._pulse_anim.setEndValue(1.2)
        self._pulse_anim.setDuration(600)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # infinite loop
        self._pulse_anim.start()

    def _stop_pulse(self) -> None:
        """Stop pulse animation."""
        self._pulse_anim.stop()
        self._pulse_scale = 1.0
        self._pulse_color = None

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def show(self) -> None:
        super().show()
        # Initialize position immediately
        self._track_cursor(force=True)
        self._cursor_timer.start()

    def hide(self) -> None:
        self._cursor_timer.stop()
        super().hide()

    # ------------------------------------------------------------------
    # Cursor tracking
    # ------------------------------------------------------------------

    def _track_cursor(self, force: bool = False) -> None:
        pos = QCursor.pos()  # Global screen coordinates
        if self._frozen:
            return
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

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Determine color
        if self._error_flash:
            base_color = DS.Colors.companion_error
        elif self._pulse_color:
            base_color = self._pulse_color
        elif self._state == VoiceState.LISTENING:
            base_color = DS.Colors.companion_listening
        else:
            base_color = DS.Colors.companion_idle

        color = QColor(base_color)
        color.setAlphaF(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)

        cy = self.WIDGET_H / 2

        if self._state == VoiceState.PROCESSING and not self._error_flash:
            # Pulsing dot for processing
            radius = 8 * self._pulse_scale
            painter.setBrush(color)
            painter.drawEllipse(QPointF(radius + 2, cy), radius, radius)
        elif self._state == VoiceState.RESPONDING and not self._error_flash:
            # Breathing diamond waveform in green
            tri_size = self.ACTIVE_TRIANGLE_SIZE
            h = tri_size
            w = h * 0.866
            painter.setBrush(color)
            triangle = QPolygonF(
                [
                    QPointF(0, cy - h / 2),
                    QPointF(w, cy),
                    QPointF(0, cy + h / 2),
                ]
            )
            painter.drawPolygon(triangle)
            self._paint_breathing_waveform(painter, tri_offset=w + 4, cy=cy)
        else:
            # Triangle (idle or listening)
            size_delta = self.ACTIVE_TRIANGLE_SIZE - self.TRIANGLE_SIZE
            tri_size = self.TRIANGLE_SIZE + size_delta * self._scale

            painter.setBrush(color)
            h = tri_size
            w = h * 0.866
            triangle = QPolygonF(
                [
                    QPointF(0, cy - h / 2),
                    QPointF(w, cy),
                    QPointF(0, cy + h / 2),
                ]
            )
            painter.drawPolygon(triangle)

            # Waveform bars when listening
            if self._scale > 0.01 and self._state == VoiceState.LISTENING:
                self._paint_waveform(painter, tri_offset=w + 4, cy=cy)

        painter.end()

    def _paint_waveform(self, painter: QPainter, tri_offset: float, cy: float) -> None:
        """Paint 8-bar diamond waveform to the right of the triangle."""
        boosted = min(1.0, self._audio_level * self.WAVEFORM_GAIN)
        bar_heights = compute_bar_heights(
            boosted, self.WAVEFORM_MAX_HEIGHT, self.WAVEFORM_MIN_HEIGHT
        )

        total_bar_width = self.WAVEFORM_WIDTH - (self.WAVEFORM_GAP * (self.WAVEFORM_BAR_COUNT - 1))
        bar_w = total_bar_width / self.WAVEFORM_BAR_COUNT

        color = QColor(DS.Colors.companion_listening)
        color.setAlphaF(self._opacity * self._scale)  # fade with scale
        painter.setBrush(color)

        x = tri_offset
        for bar_h in bar_heights:
            h = bar_h * self._scale  # scale height with animation
            if h < self.WAVEFORM_MIN_HEIGHT:
                h = self.WAVEFORM_MIN_HEIGHT * self._scale
            y = cy - h / 2
            painter.drawRoundedRect(
                QRectF(x, y, bar_w, h), 2, 2
            )
            x += bar_w + self.WAVEFORM_GAP

    def _paint_breathing_waveform(self, painter: QPainter, tri_offset: float, cy: float) -> None:
        """Paint diamond waveform for RESPONDING state driven by system audio output."""
        # Use real output level if available, fall back to pulse breathing
        # Output level is already 0.0–1.0 peak from Windows audio meter (no gain needed)
        if self._output_level > 0.005:
            level = min(1.0, self._output_level)
        else:
            # Fallback: gentle breathing from pulse animation
            synthetic = (self._pulse_scale - 0.8) / 0.4
            level = max(0.3, min(1.0, synthetic))

        bar_heights = compute_bar_heights(
            level, self.WAVEFORM_MAX_HEIGHT, self.WAVEFORM_MIN_HEIGHT
        )

        total_bar_width = self.WAVEFORM_WIDTH - (self.WAVEFORM_GAP * (self.WAVEFORM_BAR_COUNT - 1))
        bar_w = total_bar_width / self.WAVEFORM_BAR_COUNT

        color = QColor(DS.Colors.companion_responding)
        color.setAlphaF(self._opacity)
        painter.setBrush(color)

        x = tri_offset
        for bar_h in bar_heights:
            y = cy - bar_h / 2
            painter.drawRoundedRect(
                QRectF(x, y, bar_w, bar_h), 2, 2
            )
            x += bar_w + self.WAVEFORM_GAP
