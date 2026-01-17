"""Single plane slice viewer with annotation overlay."""

from typing import Optional, List, Tuple, TYPE_CHECKING
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSlider, QLabel, QGraphicsEllipseItem,
    QGraphicsPathItem, QSizePolicy
)
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QColor, QPen, QBrush,
    QPainterPath, QWheelEvent, QMouseEvent
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF

if TYPE_CHECKING:
    from core.volume import VolumeData
    from core.annotation import Annotations, Keypoint

import config


class SliceView(QWidget):
    """Single plane viewer with slice slider and annotation overlay.

    Displays one anatomical plane (axial, sagittal, or coronal) of a 3D
    volume with annotations overlaid. Supports windowing, zooming, and
    interaction with annotation tools.
    """

    # Signals
    slice_changed = Signal(str, int)  # plane, index
    mouse_pressed = Signal(str, int, QPointF, object)  # plane, slice_idx, scene_pos, event
    mouse_moved = Signal(str, int, QPointF, object)  # plane, slice_idx, scene_pos, event
    mouse_released = Signal(str, int, QPointF, object)  # plane, slice_idx, scene_pos, event

    def __init__(self, plane: str, parent=None):
        """Initialize slice view.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
        """
        super().__init__(parent)
        self.plane = plane
        self.current_slice = 0
        self.max_slice = 0

        # Windowing parameters
        self.window_center = config.DEFAULT_WINDOW_CENTER
        self.window_width = config.DEFAULT_WINDOW_WIDTH

        # Display data cache
        self._volume: Optional["VolumeData"] = None
        self._reference_mask: Optional["VolumeData"] = None
        self._annotations: Optional["Annotations"] = None

        # Overlay settings
        self.mask_opacity = config.DEFAULT_MASK_OPACITY
        self.show_reference_mask = True
        self.show_annotations = True

        # Brush preview
        self._brush_preview_points: List[Tuple[int, int]] = []
        self._brush_preview_size = config.DEFAULT_BRUSH_SIZE

        # Panning state
        self._is_panning = False
        self._pan_start = None

        # Segment preview
        self._segment_preview_path: Optional[QPainterPath] = None
        self._segment_preview_is_erasing = False
        self._segment_preview_color: Tuple[int, int, int] = (0, 255, 0)  # Default green

        # Line segment preview
        self._lineseg_preview_start: Optional[Tuple[float, float]] = None
        self._lineseg_preview_end: Optional[Tuple[float, float]] = None
        self._lineseg_preview_color: Tuple[int, int, int] = (255, 0, 0)

        self._setup_ui()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Title label
        plane_names = {"axial": "Axial (XY)", "sagittal": "Sagittal (YZ)", "coronal": "Coronal (XZ)"}
        self.title_label = QLabel(plane_names.get(self.plane, self.plane.upper()))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold;")

        # Graphics view for image display
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

        # Install event filter for mouse events
        self.view.viewport().installEventFilter(self)

        # Image and overlay items
        self.image_item = QGraphicsPixmapItem()
        self.scene.addItem(self.image_item)

        self.mask_overlay_item = QGraphicsPixmapItem()
        self.mask_overlay_item.setZValue(1)
        self.scene.addItem(self.mask_overlay_item)

        self.annotation_overlay_item = QGraphicsPixmapItem()
        self.annotation_overlay_item.setZValue(2)
        self.scene.addItem(self.annotation_overlay_item)

        # Slice slider
        slider_layout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.slice_label = QLabel("0 / 0")
        self.slice_label.setMinimumWidth(60)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.slice_label)

        layout.addWidget(self.title_label)
        layout.addWidget(self.view, stretch=1)
        layout.addLayout(slider_layout)

    def eventFilter(self, obj, event):
        """Handle mouse events on the viewport."""
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
        """Handle mouse press event."""
        # Check for Ctrl+click panning
        if event.button() == Qt.LeftButton and event.modifiers() == Qt.ControlModifier:
            self._is_panning = True
            self._pan_start = event.pos()
            self.view.setCursor(Qt.ClosedHandCursor)
            return

        scene_pos = self.view.mapToScene(event.pos())
        # Check if click is within image bounds
        if self._is_in_image_bounds(scene_pos):
            self.mouse_pressed.emit(self.plane, self.current_slice, scene_pos, event)

    def _handle_mouse_move(self, event: QMouseEvent):
        """Handle mouse move event."""
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
        self.mouse_moved.emit(self.plane, self.current_slice, scene_pos, event)

    def _handle_mouse_release(self, event: QMouseEvent):
        """Handle mouse release event."""
        if self._is_panning and event.button() == Qt.LeftButton:
            self._is_panning = False
            self.view.setCursor(Qt.ArrowCursor)
            return

        scene_pos = self.view.mapToScene(event.pos())
        self.mouse_released.emit(self.plane, self.current_slice, scene_pos, event)

    def _handle_wheel(self, event: QWheelEvent):
        """Handle wheel event for zooming."""
        if event.modifiers() == Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.view.scale(factor, factor)
        else:
            # Scroll slices with wheel
            delta = 1 if event.angleDelta().y() > 0 else -1
            new_slice = self.current_slice + delta
            if 0 <= new_slice <= self.max_slice:
                self.slider.setValue(new_slice)

    def _is_in_image_bounds(self, scene_pos: QPointF) -> bool:
        """Check if position is within image bounds."""
        pixmap = self.image_item.pixmap()
        if pixmap.isNull():
            return False
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        return rect.contains(scene_pos)

    def _on_slider_changed(self, value: int):
        """Handle slice slider change."""
        self.current_slice = value
        self.slice_label.setText(f"{value} / {self.max_slice}")
        self.update_display()
        self.slice_changed.emit(self.plane, value)

    def set_volume(self, volume: "VolumeData", slice_index: Optional[int] = None):
        """Set volume data and update display.

        Args:
            volume: VolumeData instance
            slice_index: Optional initial slice index
        """
        self._volume = volume

        # Set slider range based on plane
        self.max_slice = volume.get_max_index(self.plane)
        self.slider.setMaximum(self.max_slice)

        if slice_index is not None:
            self.slider.setValue(slice_index)
        else:
            self.slider.setValue(self.max_slice // 2)

        # Auto-adjust window/level based on data range
        vmin, vmax = volume.get_value_range()
        self.window_center = (vmin + vmax) / 2
        self.window_width = vmax - vmin

        self.update_display()
        self.fit_view()

    def set_reference_mask(self, mask: Optional["VolumeData"]):
        """Set reference mask for overlay display."""
        self._reference_mask = mask
        self.update_display()

    def set_annotations(self, annotations: Optional["Annotations"]):
        """Set annotations for overlay display."""
        self._annotations = annotations
        self.update_display()

    def set_window_level(self, center: float, width: float):
        """Set window/level parameters."""
        self.window_center = center
        self.window_width = width
        self.update_display()

    def set_mask_opacity(self, opacity: int):
        """Set mask overlay opacity (0-255)."""
        self.mask_opacity = opacity
        self.update_display()

    def update_display(self):
        """Update the displayed image and overlays."""
        if self._volume is None:
            return

        # Get and display slice
        slice_data = self._volume.get_slice(self.plane, self.current_slice)
        self._display_image(slice_data)

        # Update mask overlay
        self._update_mask_overlay()

        # Update annotation overlay
        self._update_annotation_overlay()

    def _display_image(self, slice_data: np.ndarray):
        """Display slice with window/level applied."""
        # Apply windowing
        vmin = self.window_center - self.window_width / 2
        vmax = self.window_center + self.window_width / 2

        display = np.clip(slice_data.astype(np.float32), vmin, vmax)
        display = ((display - vmin) / (vmax - vmin + 1e-8) * 255).astype(np.uint8)

        # Convert to QImage
        h, w = display.shape
        # Ensure contiguous array for QImage
        display = np.ascontiguousarray(display)
        qimage = QImage(display.data, w, h, w, QImage.Format_Grayscale8)

        self.image_item.setPixmap(QPixmap.fromImage(qimage.copy()))

    def _update_mask_overlay(self, debug=False):
        """Update the mask overlay (reference mask + user annotations)."""
        if self._volume is None:
            self.mask_overlay_item.setPixmap(QPixmap())
            return

        slice_shape = self._volume.get_slice_shape(self.plane)
        h, w = slice_shape

        # Create RGBA overlay
        overlay = np.zeros((h, w, 4), dtype=np.uint8)

        # Get set of reference mask values that have user annotations (these override reference mask)
        # We need to convert UI label IDs to reference mask values
        user_edited_ref_values = set()
        if self._annotations is not None:
            for label_id in self._annotations.masks.keys():
                ref_value = config.LABEL_TO_REFERENCE_VALUE.get(label_id, label_id)
                user_edited_ref_values.add(ref_value)

        # DEBUG
        if debug or (self._annotations is not None and len(self._annotations.masks) > 0):
            print(f"\n=== DEBUG _update_mask_overlay ({self.plane}, slice={self.current_slice}) ===")
            print(f"user_edited_label_ids={set(self._annotations.masks.keys()) if self._annotations else set()}")
            print(f"user_edited_ref_values={user_edited_ref_values}")

        # Draw reference mask if available and enabled
        # Skip labels that have user annotations (user edits take precedence)
        if self.show_reference_mask and self._reference_mask is not None:
            ref_slice = self._reference_mask.get_slice(self.plane, self.current_slice)
            for ref_value, color in config.REFERENCE_MASK_COLORS.items():
                # Skip this label if user has edited it
                if ref_value in user_edited_ref_values:
                    if debug or len(user_edited_ref_values) > 0:
                        print(f"  SKIPPING reference value {ref_value} (user has edited)")
                    continue
                mask = ref_slice == ref_value
                if np.any(mask):
                    overlay[mask, 0] = color[0]
                    overlay[mask, 1] = color[1]
                    overlay[mask, 2] = color[2]
                    overlay[mask, 3] = self.mask_opacity

        # Draw user annotation masks if available
        if self.show_annotations and self._annotations is not None:
            for label_id, mask_ann in self._annotations.masks.items():
                mask_slice = mask_ann.get_2d_slice(self.plane, self.current_slice)
                mask_bool = mask_slice > 0
                num_pixels = np.sum(mask_bool)
                print(f"  Drawing user annotation label_id={label_id}: {num_pixels} pixels on this slice")
                if np.any(mask_bool):
                    overlay[mask_bool, 0] = mask_ann.color[0]
                    overlay[mask_bool, 1] = mask_ann.color[1]
                    overlay[mask_bool, 2] = mask_ann.color[2]
                    overlay[mask_bool, 3] = self.mask_opacity

        if self._annotations is not None and len(self._annotations.masks) > 0:
            print(f"=== END DEBUG ===\n")

        # Convert to QImage
        overlay = np.ascontiguousarray(overlay)
        qimage = QImage(overlay.data, w, h, w * 4, QImage.Format_RGBA8888)
        self.mask_overlay_item.setPixmap(QPixmap.fromImage(qimage.copy()))

    def _update_annotation_overlay(self):
        """Update the annotation overlay (keypoints, brush preview)."""
        if self._volume is None:
            self.annotation_overlay_item.setPixmap(QPixmap())
            return

        slice_shape = self._volume.get_slice_shape(self.plane)
        h, w = slice_shape

        # Create transparent pixmap
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw keypoints
        if self.show_annotations and self._annotations is not None:
            keypoints_on_slice = self._annotations.get_keypoints_on_slice(
                self.plane, self.current_slice
            )
            for idx, kp, (x2d, y2d) in keypoints_on_slice:
                color = QColor(*kp.color)
                painter.setPen(QPen(color, 2))
                painter.setBrush(QBrush(color))
                r = config.KEYPOINT_RADIUS
                painter.drawEllipse(QPointF(x2d, y2d), r, r)

                # Draw label if present
                if kp.label:
                    painter.setPen(QPen(Qt.white, 1))
                    painter.drawText(int(x2d + r + 2), int(y2d), kp.label)

        # Draw line segments
        if self.show_annotations and self._annotations is not None:
            lineseg_on_slice = self._annotations.get_line_segments_on_slice(
                self.plane, self.current_slice
            )
            for idx, ls, ((x1, y1), (x2, y2)) in lineseg_on_slice:
                color = QColor(*ls.color)
                pen = QPen(color, config.LINESEG_LINE_WIDTH)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

                # Draw endpoint markers
                painter.setBrush(QBrush(color))
                r = 3  # Small radius for endpoints
                painter.drawEllipse(QPointF(x1, y1), r, r)
                painter.drawEllipse(QPointF(x2, y2), r, r)

                # Draw label at midpoint if present
                if ls.label:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    painter.setPen(QPen(Qt.white, 1))
                    painter.drawText(int(mid_x + 5), int(mid_y), ls.label)

        # Draw brush preview
        if self._brush_preview_points:
            pen = QPen(QColor(255, 255, 0, 200), self._brush_preview_size,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            if len(self._brush_preview_points) > 1:
                path = QPainterPath()
                path.moveTo(QPointF(*self._brush_preview_points[0]))
                for pt in self._brush_preview_points[1:]:
                    path.lineTo(QPointF(*pt))
                painter.drawPath(path)
            elif len(self._brush_preview_points) == 1:
                pt = self._brush_preview_points[0]
                painter.drawPoint(QPointF(*pt))

        # Draw segment preview
        if self._segment_preview_path is not None:
            # Use label color for preview, but tint red if erasing
            if self._segment_preview_is_erasing:
                # Red tint for erasing
                color = QColor(255, 0, 0, 200)
            else:
                # Use the actual label color
                r, g, b = self._segment_preview_color
                color = QColor(r, g, b, 200)
            pen = QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawPath(self._segment_preview_path)

            # Semi-transparent fill preview
            fill_color = QColor(color)
            fill_color.setAlpha(50)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            closed_path = QPainterPath(self._segment_preview_path)
            closed_path.closeSubpath()
            painter.drawPath(closed_path)

        # Draw line segment preview
        if self._lineseg_preview_start is not None and self._lineseg_preview_end is not None:
            r, g, b = self._lineseg_preview_color
            color = QColor(r, g, b, 200)
            pen = QPen(color, config.LINESEG_LINE_WIDTH, Qt.DashLine)
            painter.setPen(pen)
            x1, y1 = self._lineseg_preview_start
            x2, y2 = self._lineseg_preview_end
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # Draw start point marker
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x1, y1), 4, 4)

        painter.end()
        self.annotation_overlay_item.setPixmap(pixmap)

    def set_brush_preview(self, points: List[Tuple[int, int]], size: int):
        """Set brush stroke preview for display."""
        self._brush_preview_points = points
        self._brush_preview_size = size
        self._update_annotation_overlay()

    def clear_brush_preview(self):
        """Clear brush stroke preview."""
        self._brush_preview_points = []
        self._update_annotation_overlay()

    def set_segment_preview(self, path: QPainterPath, is_erasing: bool = False, color: Tuple[int, int, int] = None):
        """Set segment contour preview for display.

        Args:
            path: The QPainterPath defining the contour
            is_erasing: If True, shows erase preview (red tint)
            color: RGB tuple for the label color. If None, uses default green.
        """
        self._segment_preview_path = path
        self._segment_preview_is_erasing = is_erasing
        if color is not None:
            self._segment_preview_color = color
        self._update_annotation_overlay()

    def clear_segment_preview(self):
        """Clear segment contour preview."""
        self._segment_preview_path = None
        self._update_annotation_overlay()

    def set_lineseg_preview(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        color: Tuple[int, int, int] = (255, 0, 0)
    ):
        """Set line segment preview for display.

        Args:
            start: (x, y) start point in scene coordinates
            end: (x, y) end point (cursor position)
            color: RGB tuple for the label color
        """
        self._lineseg_preview_start = start
        self._lineseg_preview_end = end
        self._lineseg_preview_color = color
        self._update_annotation_overlay()

    def clear_lineseg_preview(self):
        """Clear line segment preview."""
        self._lineseg_preview_start = None
        self._lineseg_preview_end = None
        self._update_annotation_overlay()

    def fit_view(self):
        """Fit the image to the view."""
        if not self.image_item.pixmap().isNull():
            self.view.fitInView(self.image_item, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        """Handle resize to maintain fit."""
        super().resizeEvent(event)
        self.fit_view()

    def get_slice_index(self) -> int:
        """Get current slice index."""
        return self.current_slice

    def set_slice_index(self, index: int):
        """Set slice index."""
        if 0 <= index <= self.max_slice:
            self.slider.setValue(index)
