"""Base class for annotation tools."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from PySide6.QtCore import QObject, Signal, QPointF
from PySide6.QtGui import QMouseEvent, QCursor


class BaseTool(QObject, ABC):
    """Abstract base class for annotation tools.

    Provides interface for mouse event handling and cursor management.
    Subclasses implement specific annotation behaviors.
    """

    # Signals
    annotation_added = Signal(object)  # New annotation
    annotation_modified = Signal(object)  # Modified annotation
    annotation_removed = Signal(int)  # Index to remove
    cursor_changed = Signal(object)  # QCursor

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.active = False

    @abstractmethod
    def mouse_press(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse press event.

        Args:
            event: The mouse event
            scene_pos: Position in scene coordinates
            plane: Current viewing plane
            slice_index: Current slice index

        Returns:
            True if event was consumed
        """
        pass

    @abstractmethod
    def mouse_move(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse move event.

        Args:
            event: The mouse event
            scene_pos: Position in scene coordinates
            plane: Current viewing plane
            slice_index: Current slice index

        Returns:
            True if event was consumed
        """
        pass

    @abstractmethod
    def mouse_release(
        self, event: QMouseEvent, scene_pos: QPointF,
        plane: str, slice_index: int
    ) -> bool:
        """Handle mouse release event.

        Args:
            event: The mouse event
            scene_pos: Position in scene coordinates
            plane: Current viewing plane
            slice_index: Current slice index

        Returns:
            True if event was consumed
        """
        pass

    def key_press(self, event) -> bool:
        """Handle key press event.

        Args:
            event: The key event

        Returns:
            True if event was consumed
        """
        return False

    @abstractmethod
    def get_cursor(self) -> QCursor:
        """Get appropriate cursor for this tool.

        Returns:
            QCursor instance
        """
        pass

    def activate(self):
        """Called when tool is activated."""
        self.active = True

    def deactivate(self):
        """Called when tool is deactivated."""
        self.active = False

    @staticmethod
    def convert_2d_to_3d(
        scene_pos: QPointF, plane: str, slice_index: int
    ) -> Tuple[float, float, float]:
        """Convert 2D scene position to 3D volume coordinates.

        Args:
            scene_pos: Position in 2D scene coordinates
            plane: Current viewing plane
            slice_index: Current slice index

        Returns:
            Tuple of (x, y, z) in volume coordinates
        """
        x2d, y2d = scene_pos.x(), scene_pos.y()

        if plane == "axial":
            # Axial shows X-Y plane, Z is fixed
            return (x2d, y2d, float(slice_index))
        elif plane == "sagittal":
            # Sagittal shows Y-Z plane, X is fixed
            return (float(slice_index), x2d, y2d)
        else:  # coronal
            # Coronal shows X-Z plane, Y is fixed
            return (x2d, float(slice_index), y2d)
