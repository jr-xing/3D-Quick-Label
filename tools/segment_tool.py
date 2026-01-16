"""Segment tool for contour-based mask creation."""

from typing import Tuple

from PySide6.QtGui import QPainterPath, QImage, QPainter, QColor, QBrush
from PySide6.QtCore import Qt
import numpy as np


class SegmentTool:
    """Static methods for segment/contour operations.

    Provides functionality to convert drawn contours (QPainterPath) into
    binary masks that can be applied to 3D volume annotations.
    """

    @staticmethod
    def path_to_mask(path: QPainterPath, width: int, height: int) -> np.ndarray:
        """Convert QPainterPath to binary mask array.

        Renders the closed path to a QImage and extracts the filled region
        as a binary mask.

        Args:
            path: The closed QPainterPath defining the region
            width: Image width (slice width)
            height: Image height (slice height)

        Returns:
            2D numpy array (uint8) with filled region as 255, background as 0
        """
        # Create QImage with alpha channel
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        # Draw filled path
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)  # Pixel-perfect edges
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.drawPath(path)
        painter.end()

        # Convert to numpy - extract alpha channel as mask
        ptr = image.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)).copy()
        # Alpha channel (index 3) indicates where we drew
        mask = (arr[:, :, 3] > 0).astype(np.uint8) * 255

        return mask

    @staticmethod
    def apply_segment_to_mask(
        mask_3d: np.ndarray,
        plane: str,
        slice_idx: int,
        path: QPainterPath,
        slice_shape: Tuple[int, int],
        erase: bool = False
    ) -> None:
        """Apply segment path to 3D mask array in-place.

        Args:
            mask_3d: 3D numpy array (z, y, x) to modify
            plane: The anatomical plane ('axial', 'sagittal', 'coronal')
            slice_idx: Index of the slice being modified
            path: The closed QPainterPath defining the segment region
            slice_shape: (height, width) of the 2D slice
            erase: If True, subtract from mask; if False, add to mask
        """
        height, width = slice_shape
        segment_mask = SegmentTool.path_to_mask(path, width, height)

        # Get 2D slice view from 3D mask (modifying in-place)
        if plane == "axial":
            slice_2d = mask_3d[slice_idx, :, :]
        elif plane == "sagittal":
            slice_2d = mask_3d[:, :, slice_idx]
        else:  # coronal
            slice_2d = mask_3d[:, slice_idx, :]

        # Apply operation
        if erase:
            slice_2d[segment_mask > 0] = 0
        else:
            slice_2d[segment_mask > 0] = 255
