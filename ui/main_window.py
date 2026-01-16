"""Main application window."""

from pathlib import Path
from typing import Dict, Optional, List, Tuple

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QStatusBar, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QKeySequence, QShortcut, QCursor, QPainterPath

import config
from core.patient import Patient
from core.annotation import Keypoint, Annotations
from .slice_view import SliceView
from .controls import ControlsWidget
from .patient_list import PatientListWidget
from .toolbar import ToolBar


class MainWindow(QMainWindow):
    """Main application window coordinating all views and tools.

    Manages:
    - Multi-planar slice views (axial, sagittal, coronal)
    - Patient list and switching
    - Annotation tools
    - Save/load operations
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Quick Label")
        self.setMinimumSize(1200, 800)

        # Data management
        self._patients: Dict[str, Patient] = {}
        self._current_patient: Optional[Patient] = None
        self._current_tool = "view"

        # Brush stroke accumulator
        self._brush_stroke_points: List[Tuple[int, int]] = []
        self._brush_stroke_plane: Optional[str] = None
        self._brush_stroke_slice: Optional[int] = None
        self._is_drawing = False
        self._temp_erase_mode = False

        # Segment tool state
        self._segment_path: Optional[QPainterPath] = None
        self._segment_plane: Optional[str] = None
        self._segment_slice: Optional[int] = None
        self._segment_is_erasing = False

        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self):
        """Create the main layout."""
        # Toolbar
        self.toolbar = ToolBar()
        self.addToolBar(self.toolbar)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Left panel - Patient list
        self.patient_list = PatientListWidget()
        self.patient_list.setMaximumWidth(200)

        # Right panel - Views in 2x2 grid
        view_container = QWidget()
        view_layout = QGridLayout(view_container)
        view_layout.setSpacing(5)

        self.axial_view = SliceView("axial")
        self.sagittal_view = SliceView("sagittal")
        self.coronal_view = SliceView("coronal")
        self.controls = ControlsWidget()

        view_layout.addWidget(self.axial_view, 0, 0)
        view_layout.addWidget(self.sagittal_view, 0, 1)
        view_layout.addWidget(self.coronal_view, 1, 0)
        view_layout.addWidget(self.controls, 1, 1)

        # Splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.patient_list)
        splitter.addWidget(view_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Load a folder to begin")

        # Store views in list for easy iteration
        self._views = [self.axial_view, self.sagittal_view, self.coronal_view]

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Tool modes
        QShortcut(QKeySequence("1"), self, lambda: self.toolbar.set_tool("view"))
        QShortcut(QKeySequence("2"), self, lambda: self.toolbar.set_tool("keypoint"))
        QShortcut(QKeySequence("3"), self, lambda: self.toolbar.set_tool("brush"))
        QShortcut(QKeySequence("4"), self, lambda: self.toolbar.set_tool("segment"))

        # Save
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._save_all)

        # Brush size
        QShortcut(QKeySequence("+"), self, self.controls.increase_brush_size)
        QShortcut(QKeySequence("="), self, self.controls.increase_brush_size)
        QShortcut(QKeySequence("-"), self, self.controls.decrease_brush_size)

        # Erase toggle
        QShortcut(QKeySequence("E"), self, self._toggle_erase_mode)

    def _connect_signals(self):
        """Connect signals between components."""
        # Toolbar signals
        self.toolbar.tool_changed.connect(self._on_tool_changed)
        self.toolbar.save_requested.connect(self._save_current)
        self.toolbar.save_all_requested.connect(self._save_all)
        self.toolbar.load_requested.connect(self.patient_list._on_load_folder)

        # Patient list signals
        self.patient_list.patient_selected.connect(self._on_patient_selected)
        self.patient_list.folder_loaded.connect(self._on_folder_loaded)

        # Control signals
        self.controls.window_level_changed.connect(self._on_window_level_changed)
        self.controls.mask_opacity_changed.connect(self._on_mask_opacity_changed)
        self.controls.brush_size_changed.connect(self._on_brush_size_changed)
        self.controls.show_reference_mask_changed.connect(self._on_show_ref_mask_changed)
        self.controls.show_annotations_changed.connect(self._on_show_annotations_changed)

        # View signals
        for view in self._views:
            view.mouse_pressed.connect(self._on_view_mouse_pressed)
            view.mouse_moved.connect(self._on_view_mouse_moved)
            view.mouse_released.connect(self._on_view_mouse_released)

    def _on_tool_changed(self, tool_name: str):
        """Handle tool change."""
        self._current_tool = tool_name

        # Update cursor for views
        if tool_name == "view":
            cursor = Qt.OpenHandCursor
        elif tool_name == "keypoint":
            cursor = Qt.CrossCursor
        elif tool_name == "brush":
            cursor = Qt.CrossCursor
        elif tool_name == "segment":
            cursor = Qt.CrossCursor
        else:
            cursor = Qt.ArrowCursor

        for view in self._views:
            view.view.setCursor(QCursor(cursor))

    def _on_patient_selected(self, patient_id: str):
        """Handle patient selection from list."""
        patient = self.patient_list.get_patient(patient_id)
        if patient:
            self._load_patient(patient)

    def _on_folder_loaded(self, patients: list):
        """Handle folder load completion."""
        if patients:
            # Load the first patient
            self._load_patient(patients[0])
            self.patient_list.select_patient(patients[0].patient_id)

    def _load_patient(self, patient: Patient):
        """Load and display a patient."""
        # Check for unsaved changes
        if self._current_patient and self._current_patient.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Patient {self._current_patient.patient_id} has unsaved changes. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Load patient data
        self.status_bar.showMessage(f"Loading {patient.patient_id}...")
        QApplication.processEvents()

        patient.load()
        self._current_patient = patient

        # Update all views
        for view in self._views:
            view.set_volume(patient.image)
            view.set_reference_mask(patient.reference_mask)
            view.set_annotations(patient.annotations)

        # Update window/level from data range
        vmin, vmax = patient.image.get_value_range()
        center = (vmin + vmax) / 2
        width = vmax - vmin
        self.controls.set_window_level(center, width)

        self.status_bar.showMessage(f"Loaded: {patient.patient_id}")
        self.patient_list.refresh_display()

    def _on_window_level_changed(self, center: float, width: float):
        """Handle window/level change."""
        for view in self._views:
            view.set_window_level(center, width)
            view.update_display()

    def _on_mask_opacity_changed(self, opacity: int):
        """Handle mask opacity change."""
        for view in self._views:
            view.set_mask_opacity(opacity)
            view.update_display()

    def _on_brush_size_changed(self, size: int):
        """Handle brush size change."""
        # Update cursor if in brush mode
        if self._current_tool == "brush":
            # Could update cursor size here
            pass

    def _on_show_ref_mask_changed(self, show: bool):
        """Handle reference mask visibility toggle."""
        for view in self._views:
            view.show_reference_mask = show
            view.update_display()

    def _on_show_annotations_changed(self, show: bool):
        """Handle annotations visibility toggle."""
        for view in self._views:
            view.show_annotations = show
            view.update_display()

    def _toggle_erase_mode(self):
        """Toggle erase mode for brush tool."""
        if self._current_tool == "brush":
            current = self.toolbar.is_erase_mode()
            self.toolbar.set_erase_mode(not current)

    # Mouse event handlers
    def _on_view_mouse_pressed(self, plane: str, slice_idx: int, scene_pos: QPointF, event):
        """Handle mouse press on a view."""
        if self._current_patient is None:
            return

        if event.button() == Qt.LeftButton:
            if self._current_tool == "keypoint":
                self._add_keypoint(plane, slice_idx, scene_pos)
            elif self._current_tool == "brush":
                self._temp_erase_mode = False
                self._start_brush_stroke(plane, slice_idx, scene_pos)
            elif self._current_tool == "segment":
                self._segment_is_erasing = False
                self._start_segment(plane, slice_idx, scene_pos)
        elif event.button() == Qt.RightButton:
            if self._current_tool == "keypoint":
                self._remove_keypoint(plane, slice_idx, scene_pos)
            elif self._current_tool == "brush":
                self._temp_erase_mode = True
                self._start_brush_stroke(plane, slice_idx, scene_pos)
            elif self._current_tool == "segment":
                self._segment_is_erasing = True
                self._start_segment(plane, slice_idx, scene_pos)

    def _on_view_mouse_moved(self, plane: str, slice_idx: int, scene_pos: QPointF, event):
        """Handle mouse move on a view."""
        if self._current_patient is None:
            return

        if self._is_drawing and self._current_tool == "brush":
            self._continue_brush_stroke(plane, slice_idx, scene_pos)
        elif self._is_drawing and self._current_tool == "segment":
            self._continue_segment(plane, slice_idx, scene_pos)

    def _on_view_mouse_released(self, plane: str, slice_idx: int, scene_pos: QPointF, event):
        """Handle mouse release on a view."""
        if self._current_patient is None:
            return

        if event.button() in (Qt.LeftButton, Qt.RightButton):
            if self._is_drawing and self._current_tool == "brush":
                self._end_brush_stroke(plane, slice_idx)
                self._temp_erase_mode = False
            elif self._is_drawing and self._current_tool == "segment":
                self._end_segment(plane, slice_idx)

    def _add_keypoint(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Add a keypoint at the clicked position."""
        x2d, y2d = scene_pos.x(), scene_pos.y()

        # Convert 2D to 3D coordinates based on plane
        if plane == "axial":
            x, y, z = x2d, y2d, float(slice_idx)
        elif plane == "sagittal":
            x, y, z = float(slice_idx), x2d, y2d
        else:  # coronal
            x, y, z = x2d, float(slice_idx), y2d

        label_id, label_name, color = self.controls.get_current_label()
        kp = Keypoint(x=x, y=y, z=z, label=label_name, color=color)

        self._current_patient.annotations.add_keypoint(kp)
        self._update_all_views()
        self.patient_list.refresh_display()

        self.status_bar.showMessage(f"Added keypoint at ({x:.1f}, {y:.1f}, {z:.1f})")

    def _remove_keypoint(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Remove nearest keypoint to clicked position."""
        x2d, y2d = scene_pos.x(), scene_pos.y()

        # Convert 2D to 3D coordinates
        if plane == "axial":
            x, y, z = x2d, y2d, float(slice_idx)
        elif plane == "sagittal":
            x, y, z = float(slice_idx), x2d, y2d
        else:
            x, y, z = x2d, float(slice_idx), y2d

        if self._current_patient.annotations.remove_nearest_keypoint(x, y, z):
            self._update_all_views()
            self.patient_list.refresh_display()
            self.status_bar.showMessage("Removed keypoint")

    def _start_brush_stroke(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Start a new brush stroke."""
        self._is_drawing = True
        self._brush_stroke_points = [(int(scene_pos.x()), int(scene_pos.y()))]
        self._brush_stroke_plane = plane
        self._brush_stroke_slice = slice_idx

        # Show preview
        view = self._get_view_for_plane(plane)
        view.set_brush_preview(self._brush_stroke_points, self.controls.get_brush_size())

    def _continue_brush_stroke(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Continue the current brush stroke."""
        if plane != self._brush_stroke_plane:
            return

        self._brush_stroke_points.append((int(scene_pos.x()), int(scene_pos.y())))

        # Update preview
        view = self._get_view_for_plane(plane)
        view.set_brush_preview(self._brush_stroke_points, self.controls.get_brush_size())

    def _end_brush_stroke(self, plane: str, slice_idx: int):
        """End the brush stroke and apply to mask."""
        import cv2
        import numpy as np

        if not self._brush_stroke_points:
            self._is_drawing = False
            return

        # Get current label info
        label_id, label_name, color = self.controls.get_current_label()
        erase = self._temp_erase_mode or self.toolbar.is_erase_mode()

        # Get or create mask (initialize from reference mask if available)
        volume_shape = self._current_patient.image.shape
        initial_mask = None
        if self._current_patient.reference_mask is not None:
            initial_mask = self._current_patient.reference_mask.array
        mask_ann = self._current_patient.annotations.get_or_create_mask(
            label_id, label_name, volume_shape, color, initial_mask
        )

        # Get 2D slice
        slice_2d = mask_ann.get_2d_slice(self._brush_stroke_plane, self._brush_stroke_slice).copy()

        # Draw stroke on slice
        brush_size = self.controls.get_brush_size()
        value = 0 if erase else 255

        for i in range(len(self._brush_stroke_points) - 1):
            pt1 = self._brush_stroke_points[i]
            pt2 = self._brush_stroke_points[i + 1]
            cv2.line(slice_2d, pt1, pt2, value, brush_size)

        # Handle single point
        if len(self._brush_stroke_points) == 1:
            pt = self._brush_stroke_points[0]
            cv2.circle(slice_2d, pt, brush_size // 2, value, -1)

        # Update mask
        mask_ann.set_2d_slice(self._brush_stroke_plane, self._brush_stroke_slice, slice_2d)
        self._current_patient.annotations.modified = True

        # Clear preview and update display
        self._is_drawing = False
        self._brush_stroke_points = []

        view = self._get_view_for_plane(self._brush_stroke_plane)
        view.clear_brush_preview()
        self._update_all_views()
        self.patient_list.refresh_display()

        action = "Erased" if erase else "Painted"
        self.status_bar.showMessage(f"{action} mask for {label_name}")

    def _start_segment(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Start a new segment contour."""
        self._is_drawing = True
        self._segment_path = QPainterPath()
        self._segment_path.moveTo(scene_pos)
        self._segment_plane = plane
        self._segment_slice = slice_idx

        view = self._get_view_for_plane(plane)
        view.set_segment_preview(self._segment_path, self._segment_is_erasing)

    def _continue_segment(self, plane: str, slice_idx: int, scene_pos: QPointF):
        """Continue the current segment contour."""
        if plane != self._segment_plane:
            return

        self._segment_path.lineTo(scene_pos)

        view = self._get_view_for_plane(plane)
        view.set_segment_preview(self._segment_path, self._segment_is_erasing)

    def _end_segment(self, plane: str, slice_idx: int):
        """End the segment contour and apply to mask."""
        # Always reset drawing state first
        self._is_drawing = False

        if self._segment_path is None:
            return

        try:
            from tools.segment_tool import SegmentTool

            # Close the path
            self._segment_path.closeSubpath()

            # Get current label info
            label_id, label_name, color = self.controls.get_current_label()

            # Get or create mask (initialize from reference mask if available)
            volume_shape = self._current_patient.image.shape
            initial_mask = None
            if self._current_patient.reference_mask is not None:
                initial_mask = self._current_patient.reference_mask.array
            mask_ann = self._current_patient.annotations.get_or_create_mask(
                label_id, label_name, volume_shape, color, initial_mask
            )

            # Get slice shape
            slice_shape = self._current_patient.image.get_slice_shape(self._segment_plane)

            # Apply segment to mask
            SegmentTool.apply_segment_to_mask(
                mask_ann.mask,
                self._segment_plane,
                self._segment_slice,
                self._segment_path,
                slice_shape,
                self._segment_is_erasing
            )
            self._current_patient.annotations.modified = True

            action = "Erased" if self._segment_is_erasing else "Filled"
            self.status_bar.showMessage(f"{action} segment for {label_name}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Segment error: {e}")

        finally:
            # Always clear preview and reset state
            if self._segment_plane:
                view = self._get_view_for_plane(self._segment_plane)
                view.clear_segment_preview()
            self._update_all_views()
            self.patient_list.refresh_display()

            # Reset state
            self._segment_path = None
            self._segment_plane = None
            self._segment_slice = None
            self._segment_is_erasing = False

    def _get_view_for_plane(self, plane: str) -> SliceView:
        """Get the view widget for a given plane."""
        if plane == "axial":
            return self.axial_view
        elif plane == "sagittal":
            return self.sagittal_view
        else:
            return self.coronal_view

    def _update_all_views(self):
        """Update display on all views."""
        for view in self._views:
            view.update_display()

    def _save_current(self):
        """Save current patient's annotations."""
        if self._current_patient is None:
            self.status_bar.showMessage("No patient to save")
            return

        from core.persistence import save_patient_annotations

        output_dir = Path(self._current_patient.image_path).parent / config.ANNOTATIONS_DIR
        save_patient_annotations(self._current_patient, output_dir)

        self.patient_list.refresh_display()
        self.status_bar.showMessage(f"Saved annotations for {self._current_patient.patient_id}")

    def _save_all(self):
        """Save all modified patients."""
        from core.persistence import save_all_patients

        modified = self.patient_list.get_modified_patients()
        if not modified:
            self.status_bar.showMessage("No unsaved changes")
            return

        # Use directory of first patient
        first_patient = modified[0]
        output_dir = Path(first_patient.image_path).parent / config.ANNOTATIONS_DIR

        count = save_all_patients(self.patient_list.get_all_patients(), output_dir)

        self.patient_list.refresh_display()
        self.status_bar.showMessage(f"Saved annotations for {count} patient(s)")

    def closeEvent(self, event):
        """Handle window close with unsaved changes check."""
        modified = self.patient_list.get_modified_patients()
        if modified:
            patient_ids = ", ".join(p.patient_id for p in modified[:5])
            if len(modified) > 5:
                patient_ids += f"... and {len(modified) - 5} more"

            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"The following patients have unsaved changes:\n{patient_ids}\n\nSave before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self._save_all()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
