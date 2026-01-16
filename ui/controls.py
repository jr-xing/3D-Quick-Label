"""Control panel with window/level and other settings."""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QComboBox, QCheckBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal

import config


class ControlsWidget(QWidget):
    """Control panel for display and annotation settings.

    Provides controls for:
    - Window/Level adjustment
    - Mask opacity
    - Label selection for annotation
    - Brush size
    - Toggle visibility options
    """

    # Signals
    window_level_changed = Signal(float, float)  # center, width
    mask_opacity_changed = Signal(int)
    label_changed = Signal(int, str)  # label_id, label_name
    brush_size_changed = Signal(int)
    show_reference_mask_changed = Signal(bool)
    show_annotations_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Window/Level Group
        wl_group = QGroupBox("Window/Level")
        wl_layout = QFormLayout(wl_group)

        self.window_center_slider = QSlider(Qt.Horizontal)
        self.window_center_slider.setRange(-1000, 4000)
        self.window_center_slider.setValue(config.DEFAULT_WINDOW_CENTER)
        self.window_center_slider.valueChanged.connect(self._on_window_level_changed)

        self.window_center_spin = QSpinBox()
        self.window_center_spin.setRange(-1000, 4000)
        self.window_center_spin.setValue(config.DEFAULT_WINDOW_CENTER)
        self.window_center_spin.valueChanged.connect(self.window_center_slider.setValue)
        self.window_center_slider.valueChanged.connect(self.window_center_spin.setValue)

        center_layout = QHBoxLayout()
        center_layout.addWidget(self.window_center_slider)
        center_layout.addWidget(self.window_center_spin)

        self.window_width_slider = QSlider(Qt.Horizontal)
        self.window_width_slider.setRange(1, 5000)
        self.window_width_slider.setValue(config.DEFAULT_WINDOW_WIDTH)
        self.window_width_slider.valueChanged.connect(self._on_window_level_changed)

        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(1, 5000)
        self.window_width_spin.setValue(config.DEFAULT_WINDOW_WIDTH)
        self.window_width_spin.valueChanged.connect(self.window_width_slider.setValue)
        self.window_width_slider.valueChanged.connect(self.window_width_spin.setValue)

        width_layout = QHBoxLayout()
        width_layout.addWidget(self.window_width_slider)
        width_layout.addWidget(self.window_width_spin)

        wl_layout.addRow("Center:", center_layout)
        wl_layout.addRow("Width:", width_layout)

        # Display Group
        display_group = QGroupBox("Display")
        display_layout = QFormLayout(display_group)

        self.mask_opacity_slider = QSlider(Qt.Horizontal)
        self.mask_opacity_slider.setRange(0, 255)
        self.mask_opacity_slider.setValue(config.DEFAULT_MASK_OPACITY)
        self.mask_opacity_slider.valueChanged.connect(self.mask_opacity_changed.emit)

        self.show_ref_mask_check = QCheckBox("Show Reference Mask")
        self.show_ref_mask_check.setChecked(True)
        self.show_ref_mask_check.toggled.connect(self.show_reference_mask_changed.emit)

        self.show_annotations_check = QCheckBox("Show Annotations")
        self.show_annotations_check.setChecked(True)
        self.show_annotations_check.toggled.connect(self.show_annotations_changed.emit)

        display_layout.addRow("Mask Opacity:", self.mask_opacity_slider)
        display_layout.addRow(self.show_ref_mask_check)
        display_layout.addRow(self.show_annotations_check)

        # Annotation Group
        annotation_group = QGroupBox("Annotation")
        annotation_layout = QFormLayout(annotation_group)

        self.label_combo = QComboBox()
        for label_id, label_name in config.LABEL_NAMES.items():
            color = config.LABEL_COLORS.get(label_id, (128, 128, 128))
            # Show reference mask value in dropdown if mapping exists
            ref_value = config.LABEL_TO_REFERENCE_VALUE.get(label_id, None)
            if ref_value is not None:
                display_text = f"{label_name} ({ref_value})"
            else:
                display_text = label_name
            self.label_combo.addItem(display_text, label_id)
        self.label_combo.currentIndexChanged.connect(self._on_label_changed)

        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setRange(config.MIN_BRUSH_SIZE, config.MAX_BRUSH_SIZE)
        self.brush_size_slider.setValue(config.DEFAULT_BRUSH_SIZE)
        self.brush_size_slider.valueChanged.connect(self.brush_size_changed.emit)

        self.brush_size_spin = QSpinBox()
        self.brush_size_spin.setRange(config.MIN_BRUSH_SIZE, config.MAX_BRUSH_SIZE)
        self.brush_size_spin.setValue(config.DEFAULT_BRUSH_SIZE)
        self.brush_size_spin.valueChanged.connect(self.brush_size_slider.setValue)
        self.brush_size_slider.valueChanged.connect(self.brush_size_spin.setValue)

        brush_layout = QHBoxLayout()
        brush_layout.addWidget(self.brush_size_slider)
        brush_layout.addWidget(self.brush_size_spin)

        annotation_layout.addRow("Label:", self.label_combo)
        annotation_layout.addRow("Brush Size:", brush_layout)

        # Add groups to main layout
        layout.addWidget(wl_group)
        layout.addWidget(display_group)
        layout.addWidget(annotation_group)
        layout.addStretch()

    def _on_window_level_changed(self):
        """Emit combined window/level change signal."""
        center = self.window_center_slider.value()
        width = self.window_width_slider.value()
        self.window_level_changed.emit(float(center), float(width))

    def _on_label_changed(self, index: int):
        """Emit label change signal."""
        label_id = self.label_combo.itemData(index)
        label_name = self.label_combo.itemText(index)
        self.label_changed.emit(label_id, label_name)

    def set_window_level(self, center: float, width: float):
        """Set window/level values without emitting signals."""
        self.window_center_slider.blockSignals(True)
        self.window_width_slider.blockSignals(True)
        self.window_center_spin.blockSignals(True)
        self.window_width_spin.blockSignals(True)

        self.window_center_slider.setValue(int(center))
        self.window_width_slider.setValue(int(width))
        self.window_center_spin.setValue(int(center))
        self.window_width_spin.setValue(int(width))

        self.window_center_slider.blockSignals(False)
        self.window_width_slider.blockSignals(False)
        self.window_center_spin.blockSignals(False)
        self.window_width_spin.blockSignals(False)

    def get_current_label(self) -> tuple:
        """Get current label (id, name, color)."""
        label_id = self.label_combo.currentData()
        label_name = self.label_combo.currentText()
        color = config.LABEL_COLORS.get(label_id, (128, 128, 128))
        return label_id, label_name, color

    def get_brush_size(self) -> int:
        """Get current brush size."""
        return self.brush_size_slider.value()

    def increase_brush_size(self):
        """Increase brush size by 1."""
        current = self.brush_size_slider.value()
        self.brush_size_slider.setValue(min(current + 1, config.MAX_BRUSH_SIZE))

    def decrease_brush_size(self):
        """Decrease brush size by 1."""
        current = self.brush_size_slider.value()
        self.brush_size_slider.setValue(max(current - 1, config.MIN_BRUSH_SIZE))
