"""Cardiac view planning window with oblique slice visualization."""

from typing import Optional, Dict, List, Tuple, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSlider,
    QLabel, QSplitter, QListWidget, QListWidgetItem, QMessageBox,
    QFileDialog, QMenuBar, QSizePolicy, QComboBox
)
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QColor, QPen, QBrush,
    QPainterPath, QWheelEvent, QMouseEvent, QAction
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF

from pathlib import Path

from core.oblique_slice import (
    ObliquePlane, extract_oblique_slice,
    create_p2ch_plane_from_axial_line,
    create_p4ch_plane_from_p2ch_line,
    create_sax_plane_from_p4ch_line
)
from core.volume import VolumeData
from core.patient import Patient
from core.annotation import Annotations, LineSegment
from core.persistence import save_patient_annotations, load_patient_annotations
from ui.slice_view import SliceView
import config


def scan_patient_folder(folder_path: str) -> List[Patient]:
    """Scan folder for NIfTI files and create Patient objects.

    Args:
        folder_path: Path to folder containing NIfTI files

    Returns:
        List of Patient objects
    """
    folder = Path(folder_path)
    patients = []

    # Find image files (exclude label files)
    image_files = []
    for pattern in [config.NIFTI_PATTERN]:
        for f in folder.glob(pattern):
            if not f.name.endswith(config.LABEL_SUFFIX):
                image_files.append(f)

    for image_path in sorted(image_files):
        patient = Patient.from_image_path(str(image_path))
        patients.append(patient)

    return patients

if TYPE_CHECKING:
    pass


class ObliqueSliceView(QWidget):
    """Viewer for oblique (non-axis-aligned) slices.

    Similar to SliceView but handles arbitrary plane orientations
    defined by ObliquePlane objects.
    """

    # Signals
    mouse_pressed = Signal(str, QPointF, object)  # view_name, scene_pos, event
    mouse_moved = Signal(str, QPointF, object)
    mouse_released = Signal(str, QPointF, object)
    rotation_changed = Signal(str, float)  # view_name, rotation_degrees
    rotation_mode_changed = Signal(str, str)  # view_name, mode ('long_axis' or 'perp_p2ch')

    def __init__(self, view_name: str, title: str, scrollable: bool = False,
                 rotatable: bool = False, parent=None):
        """Initialize oblique slice view.

        Args:
            view_name: Identifier for this view (e.g., 'p2ch', 'p4ch', 'sax')
            title: Display title for the view
            scrollable: If True, show slider for scrolling through parallel planes
            rotatable: If True, show slider for rotating the plane around long axis
        """
        super().__init__(parent)
        self.view_name = view_name
        self.title_text = title
        self.scrollable = scrollable
        self.rotatable = rotatable

        # Data
        self._volume: Optional[VolumeData] = None
        self._plane: Optional[ObliquePlane] = None
        self._scroll_offset: float = 0.0
        self._scroll_range: Tuple[float, float] = (-100, 100)

        # Windowing
        self.window_center = config.DEFAULT_WINDOW_CENTER
        self.window_width = config.DEFAULT_WINDOW_WIDTH

        # Line segment for this view
        self._line_segment: Optional[LineSegment] = None

        # Line segment preview
        self._lineseg_preview_start: Optional[Tuple[float, float]] = None
        self._lineseg_preview_end: Optional[Tuple[float, float]] = None

        # Panning state
        self._is_panning = False
        self._pan_start = None

        self._setup_ui()

    def _setup_ui(self):
        """Create UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold;")

        # Graphics view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Install event filter
        self.view.viewport().installEventFilter(self)

        # Image and overlay items
        self.image_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)

        self.annotation_overlay_item = QGraphicsPixmapItem()
        self.annotation_overlay_item.setZValue(2)
        self.scene.addItem(self.annotation_overlay_item)

        # Placeholder label (shown when no plane is set)
        self.placeholder_label = QLabel("Draw line on previous view")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; font-style: italic;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.placeholder_label)

        # Slider for scrollable views (SAX)
        if self.scrollable:
            slider_layout = QHBoxLayout()
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setMinimum(-100)
            self.slider.setMaximum(100)
            self.slider.setValue(0)
            self.slider.valueChanged.connect(self._on_slider_changed)

            self.slice_label = QLabel("0")
            self.slice_label.setMinimumWidth(40)

            slider_layout.addWidget(self.slider)
            slider_layout.addWidget(self.slice_label)
            layout.addLayout(slider_layout)
        else:
            self.slider = None
            self.slice_label = None

        # Rotation controls for rotatable views (p4ch)
        if self.rotatable:
            # Mode selector
            mode_layout = QHBoxLayout()
            mode_label = QLabel("Mode:")
            self.rotation_mode_combo = QComboBox()
            self.rotation_mode_combo.addItem("Rotate around long axis", "long_axis")
            self.rotation_mode_combo.addItem("Perpendicular to p2ch", "perp_p2ch")
            self.rotation_mode_combo.setCurrentIndex(0)  # Default: rotate around long axis
            self.rotation_mode_combo.currentIndexChanged.connect(self._on_rotation_mode_changed)

            mode_layout.addWidget(mode_label)
            mode_layout.addWidget(self.rotation_mode_combo, stretch=1)
            layout.addLayout(mode_layout)

            # Rotation slider
            rotation_layout = QHBoxLayout()
            rotation_label = QLabel("Rotation:")
            self.rotation_slider = QSlider(Qt.Horizontal)
            self.rotation_slider.setMinimum(-180)
            self.rotation_slider.setMaximum(180)
            self.rotation_slider.setValue(0)
            self.rotation_slider.valueChanged.connect(self._on_rotation_changed)

            self.rotation_value_label = QLabel("0°")
            self.rotation_value_label.setMinimumWidth(40)

            rotation_layout.addWidget(rotation_label)
            rotation_layout.addWidget(self.rotation_slider)
            rotation_layout.addWidget(self.rotation_value_label)
            layout.addLayout(rotation_layout)
        else:
            self.rotation_slider = None
            self.rotation_value_label = None
            self.rotation_mode_combo = None

        # Initially show placeholder
        self.view.hide()
        self.placeholder_label.show()

    def eventFilter(self, obj, event):
        """Handle mouse events."""
        if obj == self.view.viewport():
            if event.type() == event.Type.MouseButtonPress:
                self._handle_mouse_press(event)
                return True
            elif event.type() == event.Type.MouseMove:
                self._handle_mouse_move(event)
                return True
            elif event.type() == event.Type.MouseButtonRelease:
                self._handle_mouse_release(event)
                return True
            elif event.type() == event.Type.Wheel:
                self._handle_wheel(event)
                return True
        return super().eventFilter(obj, event)

    def _handle_mouse_press(self, event: QMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.LeftButton and event.modifiers() == Qt.ControlModifier:
            self._is_panning = True
            self._pan_start = event.pos()
            self.view.setCursor(Qt.ClosedHandCursor)
            return

        scene_pos = self.view.mapToScene(event.pos())
        if self._is_in_image_bounds(scene_pos):
            self.mouse_pressed.emit(self.view_name, scene_pos, event)

    def _handle_mouse_move(self, event: QMouseEvent):
        """Handle mouse move."""
        if self._is_panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.view.horizontalScrollBar().setValue(
                self.view.horizontalScrollBar().value() - delta.x()
            )
            self.view.verticalScrollBar().setValue(
                self.view.verticalScrollBar().value() - delta.y()
            )
            return

        scene_pos = self.view.mapToScene(event.pos())
        self.mouse_moved.emit(self.view_name, scene_pos, event)

    def _handle_mouse_release(self, event: QMouseEvent):
        """Handle mouse release."""
        if self._is_panning and event.button() == Qt.LeftButton:
            self._is_panning = False
            self.view.setCursor(Qt.ArrowCursor)
            return

        scene_pos = self.view.mapToScene(event.pos())
        self.mouse_released.emit(self.view_name, scene_pos, event)

    def _handle_wheel(self, event: QWheelEvent):
        """Handle wheel for zooming or scrolling."""
        if event.modifiers() == Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.view.scale(factor, factor)
        elif self.scrollable and self.slider:
            delta = 5 if event.angleDelta().y() > 0 else -5
            self.slider.setValue(self.slider.value() + delta)

    def _is_in_image_bounds(self, scene_pos: QPointF) -> bool:
        """Check if position is within image bounds."""
        pixmap = self.image_item.pixmap()
        if pixmap.isNull():
            return False
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        return rect.contains(scene_pos)

    def _on_slider_changed(self, value: int):
        """Handle scroll slider change."""
        self._scroll_offset = float(value)
        if self.slice_label:
            self.slice_label.setText(str(value))
        self.update_display()

    def _on_rotation_changed(self, value: int):
        """Handle rotation slider change."""
        if self.rotation_value_label:
            self.rotation_value_label.setText(f"{value}°")
        # Emit signal so parent can regenerate the plane
        self.rotation_changed.emit(self.view_name, float(value))

    def get_rotation(self) -> float:
        """Get current rotation angle in degrees."""
        if self.rotation_slider:
            return float(self.rotation_slider.value())
        return 0.0

    def set_rotation(self, degrees: float):
        """Set rotation angle without emitting signal."""
        if self.rotation_slider:
            self.rotation_slider.blockSignals(True)
            self.rotation_slider.setValue(int(degrees))
            self.rotation_slider.blockSignals(False)
            if self.rotation_value_label:
                self.rotation_value_label.setText(f"{int(degrees)}°")

    def _on_rotation_mode_changed(self, index: int):
        """Handle rotation mode combo box change."""
        if self.rotation_mode_combo:
            mode = self.rotation_mode_combo.currentData()
            self.rotation_mode_changed.emit(self.view_name, mode)

    def get_rotation_mode(self) -> str:
        """Get current rotation mode ('long_axis' or 'perp_p2ch')."""
        if self.rotation_mode_combo:
            return self.rotation_mode_combo.currentData()
        return "long_axis"

    def set_rotation_mode(self, mode: str):
        """Set rotation mode without emitting signal."""
        if self.rotation_mode_combo:
            self.rotation_mode_combo.blockSignals(True)
            index = self.rotation_mode_combo.findData(mode)
            if index >= 0:
                self.rotation_mode_combo.setCurrentIndex(index)
            self.rotation_mode_combo.blockSignals(False)

    def set_plane(self, volume: VolumeData, plane: ObliquePlane,
                  scroll_range: Tuple[float, float] = (-100, 100)):
        """Set the oblique plane and volume to display.

        Args:
            volume: VolumeData to slice
            plane: ObliquePlane defining the slice
            scroll_range: (min, max) scroll offset range
        """
        self._volume = volume
        self._plane = plane
        self._scroll_range = scroll_range
        self._scroll_offset = 0.0

        # Set up slider if scrollable
        if self.scrollable and self.slider:
            self.slider.setMinimum(int(scroll_range[0]))
            self.slider.setMaximum(int(scroll_range[1]))
            self.slider.setValue(0)

        # Auto-set window/level from volume
        vmin, vmax = volume.get_value_range()
        self.window_center = (vmin + vmax) / 2
        self.window_width = vmax - vmin

        # Show view, hide placeholder
        self.view.show()
        self.placeholder_label.hide()

        self.update_display()
        self.fit_view()

    def clear_plane(self):
        """Clear the displayed plane."""
        self._plane = None
        self._line_segment = None
        self.image_item.setPixmap(QPixmap())
        self.annotation_overlay_item.setPixmap(QPixmap())
        self.view.hide()
        self.placeholder_label.show()

    def set_line_segment(self, ls: Optional[LineSegment]):
        """Set the line segment for this view."""
        self._line_segment = ls
        self._update_annotation_overlay()

    def set_lineseg_preview(self, start: Tuple[float, float], end: Tuple[float, float]):
        """Set line segment preview during drawing."""
        self._lineseg_preview_start = start
        self._lineseg_preview_end = end
        self._update_annotation_overlay()

    def clear_lineseg_preview(self):
        """Clear line segment preview."""
        self._lineseg_preview_start = None
        self._lineseg_preview_end = None
        self._update_annotation_overlay()

    def update_display(self):
        """Update the displayed slice."""
        if self._volume is None or self._plane is None:
            return

        # Extract oblique slice
        slice_data = extract_oblique_slice(
            self._volume.array, self._plane, self._scroll_offset
        )

        # Apply windowing
        vmin = self.window_center - self.window_width / 2
        vmax = self.window_center + self.window_width / 2
        display = np.clip(slice_data.astype(np.float32), vmin, vmax)
        display = ((display - vmin) / (vmax - vmin + 1e-8) * 255).astype(np.uint8)

        # Convert to QImage
        h, w = display.shape
        display = np.ascontiguousarray(display)
        qimage = QImage(display.data, w, h, w, QImage.Format_Grayscale8)
        self.image_item.setPixmap(QPixmap.fromImage(qimage.copy()))

        self._update_annotation_overlay()

    def _update_annotation_overlay(self):
        """Update annotation overlay (line segments)."""
        if self._plane is None:
            self.annotation_overlay_item.setPixmap(QPixmap())
            return

        w, h = self._plane.width, self._plane.height
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw stored line segment
        if self._line_segment is not None:
            ls = self._line_segment
            # Project 3D endpoints to 2D
            pos1 = self._plane.map_3d_to_2d(ls.x1, ls.y1, ls.z1, tolerance=50)
            pos2 = self._plane.map_3d_to_2d(ls.x2, ls.y2, ls.z2, tolerance=50)

            if pos1 is not None and pos2 is not None:
                color = QColor(*ls.color)
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawLine(QPointF(pos1[0], pos1[1]), QPointF(pos2[0], pos2[1]))

                # Endpoints
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QPointF(pos1[0], pos1[1]), 3, 3)
                painter.drawEllipse(QPointF(pos2[0], pos2[1]), 3, 3)

        # Draw preview
        if self._lineseg_preview_start and self._lineseg_preview_end:
            color = QColor(255, 0, 0, 200)
            pen = QPen(color, 2, Qt.DashLine)
            painter.setPen(pen)
            x1, y1 = self._lineseg_preview_start
            x2, y2 = self._lineseg_preview_end
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x1, y1), 4, 4)

        painter.end()
        self.annotation_overlay_item.setPixmap(pixmap)

    def fit_view(self):
        """Fit image to view."""
        if not self.image_item.pixmap().isNull():
            self.view.fitInView(self.image_item, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        """Handle resize."""
        super().resizeEvent(event)
        self.fit_view()

    def map_2d_to_3d(self, x2d: float, y2d: float) -> Optional[Tuple[float, float, float]]:
        """Convert 2D view coordinates to 3D volume coordinates."""
        if self._plane is None:
            return None
        return self._plane.map_2d_to_3d(x2d, y2d, self._scroll_offset)

    def get_plane(self) -> Optional[ObliquePlane]:
        """Get the current oblique plane."""
        return self._plane


class CardiacViewWindow(QMainWindow):
    """Main window for cardiac view planning with 2x3 view grid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cardiac View Planning")
        self.resize(1400, 900)

        # Patient data
        self._patients: List[Patient] = []
        self._current_patient: Optional[Patient] = None
        self._annotations: Optional[Annotations] = None

        # Views dictionary
        self._top_views: Dict[str, SliceView] = {}
        self._bottom_views: Dict[str, ObliqueSliceView] = {}

        # Line segments for cardiac views (one per relevant view)
        # Keys: 'axial' -> for p2ch, 'p2ch' -> for p4ch, 'p4ch' -> for sax
        self._cardiac_line_segments: Dict[str, Optional[LineSegment]] = {
            'axial': None,
            'p2ch': None,
            'p4ch': None
        }

        # Oblique planes
        self._oblique_planes: Dict[str, Optional[ObliquePlane]] = {
            'p2ch': None,
            'p4ch': None,
            'sax': None
        }

        # Line segment drawing state
        self._lineseg_first_point: Optional[Tuple[float, float, float]] = None
        self._lineseg_source_view: Optional[str] = None

        self._setup_ui()
        self._setup_menu()

    def _setup_ui(self):
        """Set up the main UI."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # Left: Patient list
        self.patient_list = QListWidget()
        self.patient_list.setMaximumWidth(200)
        self.patient_list.itemClicked.connect(self._on_patient_selected)

        # Right: View grid
        view_container = QWidget()
        grid_layout = QGridLayout(view_container)
        grid_layout.setSpacing(4)

        # Top row: Standard orthogonal views
        for col, (plane, title) in enumerate([
            ('axial', 'Axial (XY)'),
            ('sagittal', 'Sagittal (YZ)'),
            ('coronal', 'Coronal (XZ)')
        ]):
            view = SliceView(plane)
            view.mouse_pressed.connect(self._on_top_view_mouse_pressed)
            view.mouse_moved.connect(self._on_top_view_mouse_moved)
            view.mouse_released.connect(self._on_top_view_mouse_released)
            self._top_views[plane] = view
            grid_layout.addWidget(view, 0, col)

        # Bottom row: Oblique views
        # p2ch: no slider
        # p4ch: rotation slider (rotatable=True)
        # sax: scroll slider (scrollable=True)
        for col, (name, title, scrollable, rotatable) in enumerate([
            ('p2ch', 'Pseudo 2-Chamber', False, False),
            ('p4ch', 'Pseudo 4-Chamber', False, True),
            ('sax', 'Short Axis', True, False)
        ]):
            view = ObliqueSliceView(name, title, scrollable=scrollable, rotatable=rotatable)
            view.mouse_pressed.connect(self._on_oblique_view_mouse_pressed)
            view.mouse_moved.connect(self._on_oblique_view_mouse_moved)
            view.mouse_released.connect(self._on_oblique_view_mouse_released)
            if rotatable:
                view.rotation_changed.connect(self._on_p4ch_rotation_changed)
                view.rotation_mode_changed.connect(self._on_p4ch_rotation_mode_changed)
            self._bottom_views[name] = view
            grid_layout.addWidget(view, 1, col)

        # Splitter for patient list and views
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.patient_list)
        splitter.addWidget(view_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _setup_menu(self):
        """Set up menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open Folder...", self)
        open_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_action)

        save_action = QAction("Save Annotations", self)
        save_action.triggered.connect(self._on_save_annotations)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def load_folder(self, folder_path: str):
        """Load patients from folder."""
        self._patients = scan_patient_folder(folder_path)
        self.patient_list.clear()
        for patient in self._patients:
            item = QListWidgetItem(patient.patient_id)
            self.patient_list.addItem(item)

        if self._patients:
            self.patient_list.setCurrentRow(0)
            self._load_patient(self._patients[0])

    def _on_open_folder(self):
        """Handle open folder action."""
        folder = QFileDialog.getExistingDirectory(self, "Select Patient Folder")
        if folder:
            self.load_folder(folder)

    def _on_save_annotations(self):
        """Save current annotations."""
        if self._current_patient and self._annotations:
            # Update annotations with cardiac line segments
            self._sync_line_segments_to_annotations()

            import os
            ann_dir = os.path.join(os.path.dirname(self._current_patient.image_path), "annotations")
            os.makedirs(ann_dir, exist_ok=True)
            save_patient_annotations(self._current_patient, ann_dir)
            QMessageBox.information(self, "Saved", "Annotations saved successfully.")

    def _on_patient_selected(self, item: QListWidgetItem):
        """Handle patient selection."""
        idx = self.patient_list.row(item)
        if 0 <= idx < len(self._patients):
            self._load_patient(self._patients[idx])

    def _load_patient(self, patient: Patient):
        """Load a patient's data."""
        # Unload previous
        if self._current_patient:
            self._current_patient.unload()

        self._current_patient = patient
        patient.load()

        # Load annotations
        import os
        ann_dir = os.path.join(os.path.dirname(patient.image_path), "annotations")
        if os.path.exists(ann_dir):
            self._annotations = load_patient_annotations(
                patient.patient_id, ann_dir, patient.image.shape
            )
        else:
            self._annotations = Annotations(patient_id=patient.patient_id)

        # Set volume to top views
        for plane, view in self._top_views.items():
            view.set_volume(patient.image)
            view.set_annotations(self._annotations)

        # Clear bottom views
        for view in self._bottom_views.values():
            view.clear_plane()

        # Reset cardiac line segments
        self._cardiac_line_segments = {'axial': None, 'p2ch': None, 'p4ch': None}
        self._oblique_planes = {'p2ch': None, 'p4ch': None, 'sax': None}

        # Check for existing line segments and try to restore views
        self._restore_cardiac_views_from_annotations()

    def _restore_cardiac_views_from_annotations(self):
        """Try to restore cardiac views from existing annotations."""
        if not self._annotations or not self._annotations.line_segments:
            return

        # Look for line segments that might be cardiac planning lines
        # For now, use first line segment on axial plane for p2ch
        for ls in self._annotations.line_segments:
            # Check if it's on axial plane (z1 == z2)
            if abs(ls.z1 - ls.z2) < 0.5 and self._cardiac_line_segments['axial'] is None:
                self._cardiac_line_segments['axial'] = ls
                self._generate_p2ch_view()
                break

    def _sync_line_segments_to_annotations(self):
        """Sync cardiac line segments to annotations object."""
        if not self._annotations:
            return

        # For now, we add the cardiac line segments to annotations
        # In a more complete implementation, we might want to track them separately
        for key, ls in self._cardiac_line_segments.items():
            if ls is not None:
                # Check if already in annotations
                found = False
                for existing in self._annotations.line_segments:
                    if (abs(existing.x1 - ls.x1) < 0.1 and
                        abs(existing.y1 - ls.y1) < 0.1 and
                        abs(existing.z1 - ls.z1) < 0.1):
                        found = True
                        break
                if not found:
                    self._annotations.add_line_segment(ls)

    # --- Top View Mouse Handlers ---

    def _on_top_view_mouse_pressed(self, plane: str, slice_idx: int,
                                    scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse press on top (orthogonal) views."""
        if event.button() == Qt.LeftButton:
            # Start line segment
            x2d, y2d = scene_pos.x(), scene_pos.y()
            x3d, y3d, z3d = self._convert_2d_to_3d(plane, slice_idx, x2d, y2d)
            self._lineseg_first_point = (x3d, y3d, z3d)
            self._lineseg_source_view = plane

        elif event.button() == Qt.RightButton:
            # Remove line segment if clicked near one
            if plane == 'axial' and self._cardiac_line_segments['axial']:
                # Also remove from annotations
                old_ls = self._cardiac_line_segments['axial']
                if old_ls and self._annotations:
                    for i, existing in enumerate(self._annotations.line_segments):
                        if existing is old_ls:
                            self._annotations.remove_line_segment(i)
                            break
                self._cardiac_line_segments['axial'] = None
                self._clear_dependent_views('axial')
                self._top_views[plane].update_display()

    def _on_top_view_mouse_moved(self, plane: str, slice_idx: int,
                                  scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse move on top views."""
        if self._lineseg_first_point and self._lineseg_source_view == plane:
            # Show preview
            view = self._top_views[plane]
            start_2d = self._convert_3d_to_2d(plane, slice_idx, *self._lineseg_first_point)
            if start_2d:
                view.set_lineseg_preview(start_2d, (scene_pos.x(), scene_pos.y()))

    def _on_top_view_mouse_released(self, plane: str, slice_idx: int,
                                     scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse release on top views."""
        if event.button() != Qt.LeftButton:
            return

        view = self._top_views[plane]
        view.clear_lineseg_preview()

        if self._lineseg_first_point and self._lineseg_source_view == plane:
            x2d, y2d = scene_pos.x(), scene_pos.y()
            x3d, y3d, z3d = self._convert_2d_to_3d(plane, slice_idx, x2d, y2d)

            # Create line segment
            x1, y1, z1 = self._lineseg_first_point
            ls = LineSegment(
                x1=x1, y1=y1, z1=z1,
                x2=x3d, y2=y3d, z2=z3d,
                label=f"{plane}_cardiac",
                color=(255, 100, 100)
            )

            # Only use axial for generating p2ch
            if plane == 'axial':
                # Remove old line segment from annotations if exists
                old_ls = self._cardiac_line_segments['axial']
                if old_ls and self._annotations:
                    # Find index of old line segment
                    for i, existing in enumerate(self._annotations.line_segments):
                        if existing is old_ls:
                            self._annotations.remove_line_segment(i)
                            break

                # Store new line segment
                self._cardiac_line_segments['axial'] = ls

                # Add to annotations so it's displayed by SliceView
                if self._annotations:
                    self._annotations.add_line_segment(ls)

                # Clear dependent views before regenerating
                self._clear_dependent_views('axial')
                self._generate_p2ch_view()

            self._lineseg_first_point = None
            self._lineseg_source_view = None
            view.update_display()

    # --- Oblique View Mouse Handlers ---

    def _on_oblique_view_mouse_pressed(self, view_name: str,
                                        scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse press on oblique views."""
        if event.button() == Qt.LeftButton:
            view = self._bottom_views[view_name]
            pos_3d = view.map_2d_to_3d(scene_pos.x(), scene_pos.y())
            if pos_3d:
                self._lineseg_first_point = pos_3d
                self._lineseg_source_view = view_name

        elif event.button() == Qt.RightButton:
            # Remove line segment
            if view_name == 'p2ch' and self._cardiac_line_segments['p2ch']:
                self._cardiac_line_segments['p2ch'] = None
                self._clear_dependent_views('p2ch')
                self._bottom_views[view_name].set_line_segment(None)
            elif view_name == 'p4ch' and self._cardiac_line_segments['p4ch']:
                self._cardiac_line_segments['p4ch'] = None
                self._clear_dependent_views('p4ch')
                self._bottom_views[view_name].set_line_segment(None)

    def _on_oblique_view_mouse_moved(self, view_name: str,
                                      scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse move on oblique views."""
        if self._lineseg_first_point and self._lineseg_source_view == view_name:
            view = self._bottom_views[view_name]
            plane = view.get_plane()
            if plane:
                start_2d = plane.map_3d_to_2d(*self._lineseg_first_point)
                if start_2d:
                    view.set_lineseg_preview(start_2d, (scene_pos.x(), scene_pos.y()))

    def _on_oblique_view_mouse_released(self, view_name: str,
                                         scene_pos: QPointF, event: QMouseEvent):
        """Handle mouse release on oblique views."""
        if event.button() != Qt.LeftButton:
            return

        view = self._bottom_views[view_name]
        view.clear_lineseg_preview()

        if self._lineseg_first_point and self._lineseg_source_view == view_name:
            pos_3d = view.map_2d_to_3d(scene_pos.x(), scene_pos.y())
            if pos_3d:
                x1, y1, z1 = self._lineseg_first_point
                x2, y2, z2 = pos_3d

                ls = LineSegment(
                    x1=x1, y1=y1, z1=z1,
                    x2=x2, y2=y2, z2=z2,
                    label=f"{view_name}_cardiac",
                    color=(100, 255, 100)
                )

                if view_name == 'p2ch':
                    self._cardiac_line_segments['p2ch'] = ls
                    view.set_line_segment(ls)
                    self._generate_p4ch_view()
                elif view_name == 'p4ch':
                    self._cardiac_line_segments['p4ch'] = ls
                    view.set_line_segment(ls)
                    self._generate_sax_view()

            self._lineseg_first_point = None
            self._lineseg_source_view = None

    # --- View Generation ---

    def _generate_p2ch_view(self):
        """Generate pseudo-2ch view from axial line segment."""
        ls = self._cardiac_line_segments['axial']
        if not ls or not self._current_patient:
            return

        volume = self._current_patient.image
        plane = create_p2ch_plane_from_axial_line(
            ls.x1, ls.y1, ls.x2, ls.y2,
            ls.z1,  # axial slice Z
            volume.shape
        )

        self._oblique_planes['p2ch'] = plane
        self._bottom_views['p2ch'].set_plane(volume, plane)

    def _generate_p4ch_view(self, rotation_degrees: float = None, rotation_mode: str = None):
        """Generate pseudo-4ch view from p2ch line segment.

        Args:
            rotation_degrees: Rotation angle around long axis. If None, uses current slider value.
            rotation_mode: Either 'long_axis' or 'perp_p2ch'. If None, uses current combo box value.
        """
        ls = self._cardiac_line_segments['p2ch']
        p2ch_plane = self._oblique_planes['p2ch']
        if not ls or not p2ch_plane or not self._current_patient:
            return

        volume = self._current_patient.image

        # Get rotation from slider if not provided
        if rotation_degrees is None:
            rotation_degrees = self._bottom_views['p4ch'].get_rotation()

        # Get rotation mode from combo box if not provided
        if rotation_mode is None:
            rotation_mode = self._bottom_views['p4ch'].get_rotation_mode()

        # Get 2D coordinates on p2ch plane
        # Point 1 = valve, Point 2 = apex
        pos1 = p2ch_plane.map_3d_to_2d(ls.x1, ls.y1, ls.z1)
        pos2 = p2ch_plane.map_3d_to_2d(ls.x2, ls.y2, ls.z2)
        if not pos1 or not pos2:
            return

        plane = create_p4ch_plane_from_p2ch_line(
            pos1[0], pos1[1], pos2[0], pos2[1],
            p2ch_plane, volume.shape,
            rotation_degrees=rotation_degrees,
            rotation_mode=rotation_mode
        )

        self._oblique_planes['p4ch'] = plane
        self._bottom_views['p4ch'].set_plane(volume, plane)

    def _on_p4ch_rotation_changed(self, view_name: str, rotation_degrees: float):
        """Handle p4ch rotation slider change."""
        # Regenerate p4ch with new rotation
        self._generate_p4ch_view(rotation_degrees)

    def _on_p4ch_rotation_mode_changed(self, view_name: str, rotation_mode: str):
        """Handle p4ch rotation mode change."""
        # Regenerate p4ch with new mode
        self._generate_p4ch_view(rotation_mode=rotation_mode)

    def _generate_sax_view(self):
        """Generate short-axis view from p4ch line segment."""
        ls = self._cardiac_line_segments['p4ch']
        p4ch_plane = self._oblique_planes['p4ch']
        if not ls or not p4ch_plane or not self._current_patient:
            return

        volume = self._current_patient.image

        # Get 2D coordinates on p4ch plane
        pos1 = p4ch_plane.map_3d_to_2d(ls.x1, ls.y1, ls.z1)
        pos2 = p4ch_plane.map_3d_to_2d(ls.x2, ls.y2, ls.z2)
        if not pos1 or not pos2:
            return

        plane = create_sax_plane_from_p4ch_line(
            pos1[0], pos1[1], pos2[0], pos2[1],
            p4ch_plane, volume.shape
        )

        self._oblique_planes['sax'] = plane

        # Calculate scroll range based on volume size
        max_dim = max(volume.shape)
        scroll_range = (-max_dim // 2, max_dim // 2)

        self._bottom_views['sax'].set_plane(volume, plane, scroll_range)

    def _clear_dependent_views(self, source: str):
        """Clear views that depend on the given source."""
        if source == 'axial':
            self._bottom_views['p2ch'].clear_plane()
            self._oblique_planes['p2ch'] = None
            self._cardiac_line_segments['p2ch'] = None
            self._clear_dependent_views('p2ch')
        elif source == 'p2ch':
            self._bottom_views['p4ch'].clear_plane()
            self._oblique_planes['p4ch'] = None
            self._cardiac_line_segments['p4ch'] = None
            self._clear_dependent_views('p4ch')
        elif source == 'p4ch':
            self._bottom_views['sax'].clear_plane()
            self._oblique_planes['sax'] = None

    # --- Coordinate Conversion ---

    def _convert_2d_to_3d(self, plane: str, slice_idx: int,
                          x2d: float, y2d: float) -> Tuple[float, float, float]:
        """Convert 2D view coordinates to 3D volume coordinates."""
        if plane == "axial":
            return (x2d, y2d, float(slice_idx))
        elif plane == "sagittal":
            return (float(slice_idx), x2d, y2d)
        else:  # coronal
            return (x2d, float(slice_idx), y2d)

    def _convert_3d_to_2d(self, plane: str, slice_idx: int,
                          x: float, y: float, z: float) -> Optional[Tuple[float, float]]:
        """Convert 3D coordinates to 2D view coordinates."""
        tolerance = 0.5
        if plane == "axial":
            if abs(z - slice_idx) <= tolerance:
                return (x, y)
        elif plane == "sagittal":
            if abs(x - slice_idx) <= tolerance:
                return (y, z)
        else:  # coronal
            if abs(y - slice_idx) <= tolerance:
                return (x, z)
        return None
