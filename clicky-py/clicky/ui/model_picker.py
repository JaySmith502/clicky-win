"""Model picker dropdown for ClickyWin."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

_MODELS = [
    ("Sonnet 4.6", "claude-sonnet-4-6"),
    ("Opus 4.6", "claude-opus-4-6"),
]


class ModelPicker(QWidget):
    model_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Model:", self)
        label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(label)

        self._combo = QComboBox(self)
        for display_name, model_id in _MODELS:
            self._combo.addItem(display_name, model_id)
        self._combo.setStyleSheet(
            "QComboBox { color: #e0e0e0; background: #2a2a2a; border: 1px solid #444; border-radius: 4px; padding: 2px 8px; font-size: 12px; }"
        )
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self._combo)
        layout.addStretch(1)

    def set_model(self, model_id: str) -> None:
        """Set the selected model without firing the signal."""
        idx = self._combo.findData(model_id)
        if idx >= 0:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(idx)
            self._combo.blockSignals(False)

    def _on_index_changed(self, index: int) -> None:
        model_id = self._combo.itemData(index)
        if model_id:
            self.model_changed.emit(model_id)
