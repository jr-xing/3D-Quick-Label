"""Keypoint annotation tool."""

from typing import Optional, Tuple

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent, QCursor

from .base_tool import BaseTool
from core.annotation import Keypoint


class KeypointTool(BaseTool):
    """Tool for placing and removing keypoints.

    Left-click to add a keypoint.
    Right-click to remove the nearest keypoint.
    """

    def __init__(self):
        super().__init__("keypoint")
        self.current_label = "point"
        self.current_color = (255, 0, 0)

    def set_label(self, label: str, color: Tuple[int, int, int]):
        """Set the label and color for new keypoints."""
        self.current_label = label
        self.current_color = color

    def mouse_press(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse press - add or remove keypoint."""
        if event.button() == Qt.LeftButton:
            # Create keypoint at clicked position
            x, y, z = self.convert_2d_to_3d(scene_pos, plane, slice_index)
            kp = Keypoint(
                x=x, y=y, z=z,
                label=self.current_label,
                color=self.current_color
            )
            self.annotation_added.emit(kp)
            return True

        elif event.button() == Qt.RightButton:
            # Remove nearest keypoint
            x, y, z = self.convert_2d_to_3d(scene_pos, plane, slice_index)
            self.annotation_removed.emit({
                "type": "nearest_keypoint",
                "x": x, "y": y, "z": z
            })
            return True

        return False

    def mouse_move(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse move - no drag behavior for keypoints."""
        return False

    def mouse_release(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse release - no special behavior."""
        return False

    def get_cursor(self) -> QCursor:
        """Return crosshair cursor for precision placement."""
        return QCursor(Qt.CrossCursor)
