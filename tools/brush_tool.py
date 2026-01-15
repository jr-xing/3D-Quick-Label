"""Brush annotation tool for painting masks."""

from typing import List, Tuple, Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent, QCursor, QPixmap, QPainter, QColor
import numpy as np

from .base_tool import BaseTool


class BrushTool(BaseTool):
    """Tool for painting mask annotations.

    Drag to paint (or erase in erase mode).
    Brush strokes accumulate during drag and are applied on release.
    """

    def __init__(self):
        super().__init__("brush")
        self.brush_size = 10
        self.current_label_id = 1
        self.current_label_name = "Label 1"
        self.current_color = (0, 255, 0)
        self.erase_mode = False

        # Stroke accumulator
        self._stroke_points: List[Tuple[int, int]] = []
        self._stroke_plane: Optional[str] = None
        self._stroke_slice: Optional[int] = None
        self._is_drawing = False

    def set_brush_size(self, size: int):
        """Set the brush size in pixels."""
        self.brush_size = max(1, min(size, 100))

    def set_label(self, label_id: int, label_name: str, color: Tuple[int, int, int]):
        """Set the label for painted masks."""
        self.current_label_id = label_id
        self.current_label_name = label_name
        self.current_color = color

    def set_erase_mode(self, erase: bool):
        """Set erase mode."""
        self.erase_mode = erase

    def mouse_press(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse press - start brush stroke."""
        if event.button() == Qt.LeftButton:
            self._is_drawing = True
            self._stroke_points = [(int(scene_pos.x()), int(scene_pos.y()))]
            self._stroke_plane = plane
            self._stroke_slice = slice_index

            # Emit preview update
            self.annotation_modified.emit({
                "type": "stroke_preview",
                "points": self._stroke_points,
                "size": self.brush_size,
                "plane": plane
            })
            return True

        return False

    def mouse_move(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse move - continue brush stroke."""
        if self._is_drawing:
            # Only continue if on same plane
            if plane != self._stroke_plane:
                return False

            self._stroke_points.append((int(scene_pos.x()), int(scene_pos.y())))

            # Emit preview update
            self.annotation_modified.emit({
                "type": "stroke_preview",
                "points": self._stroke_points,
                "size": self.brush_size,
                "plane": plane
            })
            return True

        return False

    def mouse_release(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse release - complete brush stroke."""
        if self._is_drawing and event.button() == Qt.LeftButton:
            self._is_drawing = False

            # Emit completed stroke
            self.annotation_added.emit({
                "type": "brush_stroke",
                "plane": self._stroke_plane,
                "slice_index": self._stroke_slice,
                "points": self._stroke_points,
                "brush_size": self.brush_size,
                "label_id": self.current_label_id,
                "label_name": self.current_label_name,
                "color": self.current_color,
                "erase": self.erase_mode
            })

            self._stroke_points = []
            self._stroke_plane = None
            self._stroke_slice = None
            return True

        return False

    def get_cursor(self) -> QCursor:
        """Return circular cursor showing brush size."""
        # Create a circular cursor
        size = max(self.brush_size * 2 + 2, 8)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circle outline
        color = QColor(255, 0, 0) if self.erase_mode else QColor(0, 255, 0)
        painter.setPen(color)
        painter.drawEllipse(1, 1, size - 2, size - 2)

        # Draw crosshair
        center = size // 2
        painter.drawLine(center - 3, center, center + 3, center)
        painter.drawLine(center, center - 3, center, center + 3)

        painter.end()

        return QCursor(pixmap, size // 2, size // 2)

    @staticmethod
    def apply_stroke_to_mask(
        mask: np.ndarray, stroke_data: dict
    ) -> np.ndarray:
        """Apply brush stroke to a 3D mask array.

        Args:
            mask: 3D numpy array (z, y, x)
            stroke_data: Dictionary with stroke information

        Returns:
            Modified mask array
        """
        import cv2

        plane = stroke_data["plane"]
        slice_idx = stroke_data["slice_index"]
        points = stroke_data["points"]
        size = stroke_data["brush_size"]
        erase = stroke_data.get("erase", False)

        # Get 2D slice from 3D mask
        if plane == "axial":
            slice_2d = mask[slice_idx, :, :].copy()
        elif plane == "sagittal":
            slice_2d = mask[:, :, slice_idx].copy()
        else:  # coronal
            slice_2d = mask[:, slice_idx, :].copy()

        # Determine value to draw
        value = 0 if erase else 255

        # Draw lines connecting points
        for i in range(len(points) - 1):
            cv2.line(slice_2d, points[i], points[i + 1], value, size)

        # Handle single point
        if len(points) == 1:
            cv2.circle(slice_2d, points[0], size // 2, value, -1)

        # Write back to 3D mask
        if plane == "axial":
            mask[slice_idx, :, :] = slice_2d
        elif plane == "sagittal":
            mask[:, :, slice_idx] = slice_2d
        else:
            mask[:, slice_idx, :] = slice_2d

        return mask
