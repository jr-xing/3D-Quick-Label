"""Annotation data structures for 3D medical imaging."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np

import config


@dataclass
class Keypoint:
    """Single 3D keypoint with label.

    Coordinates are stored in volume space (z, y, x) but can be
    created from any 2D plane view.
    """

    x: float
    y: float
    z: float
    label: str = ""
    color: Tuple[int, int, int] = (255, 0, 0)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "label": self.label,
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Keypoint":
        """Create from dictionary."""
        return cls(
            x=d["x"],
            y=d["y"],
            z=d["z"],
            label=d.get("label", ""),
            color=tuple(d.get("color", (255, 0, 0))),
        )

    def get_2d_position(self, plane: str, slice_index: int) -> Optional[Tuple[float, float]]:
        """Get 2D position if keypoint is visible on given slice.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Current slice index

        Returns:
            Tuple of (x, y) in 2D view coordinates, or None if not on this slice
        """
        tolerance = 0.5  # Half-voxel tolerance

        if plane == "axial":
            # Axial shows X-Y plane, Z is fixed
            if abs(self.z - slice_index) <= tolerance:
                return (self.x, self.y)
        elif plane == "sagittal":
            # Sagittal shows Y-Z plane, X is fixed
            if abs(self.x - slice_index) <= tolerance:
                return (self.y, self.z)
        elif plane == "coronal":
            # Coronal shows X-Z plane, Y is fixed
            if abs(self.y - slice_index) <= tolerance:
                return (self.x, self.z)
        return None

    def distance_to(self, other: "Keypoint") -> float:
        """Calculate 3D Euclidean distance to another keypoint."""
        return np.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


@dataclass
class LineSegment:
    """3D line segment defined by two endpoints.

    Both points are stored in volume space. Line segments
    are constrained to a single slice plane.
    """

    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    label: str = ""
    color: Tuple[int, int, int] = (255, 0, 0)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "x1": self.x1,
            "y1": self.y1,
            "z1": self.z1,
            "x2": self.x2,
            "y2": self.y2,
            "z2": self.z2,
            "label": self.label,
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LineSegment":
        """Create from dictionary."""
        return cls(
            x1=d["x1"],
            y1=d["y1"],
            z1=d["z1"],
            x2=d["x2"],
            y2=d["y2"],
            z2=d["z2"],
            label=d.get("label", ""),
            color=tuple(d.get("color", (255, 0, 0))),
        )

    def get_2d_positions(
        self, plane: str, slice_index: int
    ) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Get 2D positions if line segment is visible on given slice.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Current slice index

        Returns:
            Tuple of ((x1, y1), (x2, y2)) in 2D view coordinates, or None if not on this slice
        """
        tolerance = 0.5  # Half-voxel tolerance

        if plane == "axial":
            # Axial shows X-Y plane, Z is fixed
            if abs(self.z1 - slice_index) <= tolerance and abs(self.z2 - slice_index) <= tolerance:
                return ((self.x1, self.y1), (self.x2, self.y2))
        elif plane == "sagittal":
            # Sagittal shows Y-Z plane, X is fixed
            if abs(self.x1 - slice_index) <= tolerance and abs(self.x2 - slice_index) <= tolerance:
                return ((self.y1, self.z1), (self.y2, self.z2))
        elif plane == "coronal":
            # Coronal shows X-Z plane, Y is fixed
            if abs(self.y1 - slice_index) <= tolerance and abs(self.y2 - slice_index) <= tolerance:
                return ((self.x1, self.z1), (self.x2, self.z2))
        return None


@dataclass
class MaskAnnotation:
    """3D binary mask annotation with label.

    The mask is a 3D numpy array matching the volume shape,
    where non-zero values indicate annotated regions.
    """

    label_id: int
    label_name: str
    mask: np.ndarray  # 3D array matching volume shape (z, y, x)
    color: Tuple[int, int, int] = (0, 255, 0)

    def to_dict(self) -> dict:
        """Convert metadata to dictionary (mask saved separately)."""
        return {
            "label_id": self.label_id,
            "label_name": self.label_name,
            "color": list(self.color),
        }

    def get_2d_slice(self, plane: str, slice_index: int) -> np.ndarray:
        """Get 2D mask slice for given plane.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Slice index

        Returns:
            2D numpy array (binary mask)
        """
        if plane == "axial":
            return self.mask[slice_index, :, :]
        elif plane == "sagittal":
            return self.mask[:, :, slice_index]
        elif plane == "coronal":
            return self.mask[:, slice_index, :]
        else:
            raise ValueError(f"Unknown plane: {plane}")

    def set_2d_slice(self, plane: str, slice_index: int, slice_data: np.ndarray) -> None:
        """Set 2D mask slice for given plane.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Slice index
            slice_data: 2D numpy array to set
        """
        if plane == "axial":
            self.mask[slice_index, :, :] = slice_data
        elif plane == "sagittal":
            self.mask[:, :, slice_index] = slice_data
        elif plane == "coronal":
            self.mask[:, slice_index, :] = slice_data
        else:
            raise ValueError(f"Unknown plane: {plane}")

    def has_data(self) -> bool:
        """Check if mask contains any annotations."""
        return np.any(self.mask > 0)


@dataclass
class Annotations:
    """Container for all annotations for a single patient.

    Manages keypoints, line segments, and multiple mask labels, tracking
    modification state for save prompts.
    """

    patient_id: str
    keypoints: List[Keypoint] = field(default_factory=list)
    line_segments: List[LineSegment] = field(default_factory=list)
    masks: Dict[int, MaskAnnotation] = field(default_factory=dict)
    modified: bool = False

    def add_keypoint(self, kp: Keypoint) -> None:
        """Add a new keypoint."""
        self.keypoints.append(kp)
        self.modified = True

    def remove_keypoint(self, index: int) -> None:
        """Remove keypoint by index."""
        if 0 <= index < len(self.keypoints):
            self.keypoints.pop(index)
            self.modified = True

    def remove_nearest_keypoint(
        self, x: float, y: float, z: float, max_distance: float = 10.0
    ) -> bool:
        """Remove the keypoint nearest to given 3D position.

        Args:
            x, y, z: Target position
            max_distance: Maximum distance to consider

        Returns:
            True if a keypoint was removed
        """
        if not self.keypoints:
            return False

        target = Keypoint(x=x, y=y, z=z)
        distances = [(i, kp.distance_to(target)) for i, kp in enumerate(self.keypoints)]
        distances.sort(key=lambda x: x[1])

        if distances[0][1] <= max_distance:
            self.remove_keypoint(distances[0][0])
            return True
        return False

    def add_line_segment(self, ls: LineSegment) -> None:
        """Add a new line segment."""
        self.line_segments.append(ls)
        self.modified = True

    def remove_line_segment(self, index: int) -> None:
        """Remove line segment by index."""
        if 0 <= index < len(self.line_segments):
            self.line_segments.pop(index)
            self.modified = True

    def remove_nearest_line_segment(
        self, x: float, y: float, z: float, max_distance: float = 15.0
    ) -> bool:
        """Remove the line segment nearest to given 3D position.

        Uses perpendicular distance to line segment.

        Args:
            x, y, z: Target position
            max_distance: Maximum distance to consider

        Returns:
            True if a line segment was removed
        """
        if not self.line_segments:
            return False

        def point_to_segment_distance(px, py, pz, ls):
            """Calculate distance from point to line segment."""
            # Vector from p1 to p2
            dx = ls.x2 - ls.x1
            dy = ls.y2 - ls.y1
            dz = ls.z2 - ls.z1

            # Vector from p1 to point
            fx = px - ls.x1
            fy = py - ls.y1
            fz = pz - ls.z1

            segment_len_sq = dx * dx + dy * dy + dz * dz
            if segment_len_sq == 0:
                # Degenerate segment (single point)
                return np.sqrt(fx * fx + fy * fy + fz * fz)

            # Parameter t for closest point on infinite line
            t = (fx * dx + fy * dy + fz * dz) / segment_len_sq
            t = max(0, min(1, t))  # Clamp to segment

            # Closest point on segment
            cx = ls.x1 + t * dx
            cy = ls.y1 + t * dy
            cz = ls.z1 + t * dz

            # Distance
            return np.sqrt((px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2)

        distances = [
            (i, point_to_segment_distance(x, y, z, ls))
            for i, ls in enumerate(self.line_segments)
        ]
        distances.sort(key=lambda x: x[1])

        if distances[0][1] <= max_distance:
            self.remove_line_segment(distances[0][0])
            return True
        return False

    def get_line_segments_on_slice(
        self, plane: str, slice_index: int
    ) -> List[Tuple[int, LineSegment, Tuple[Tuple[float, float], Tuple[float, float]]]]:
        """Get all line segments visible on given slice.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Current slice index

        Returns:
            List of (index, line_segment, ((x1_2d, y1_2d), (x2_2d, y2_2d))) tuples
        """
        result = []
        for i, ls in enumerate(self.line_segments):
            pos_2d = ls.get_2d_positions(plane, slice_index)
            if pos_2d is not None:
                result.append((i, ls, pos_2d))
        return result

    def get_or_create_mask(
        self, label_id: int, label_name: str, volume_shape: Tuple[int, int, int],
        color: Tuple[int, int, int] = (0, 255, 0),
        reference_mask: Optional[np.ndarray] = None
    ) -> MaskAnnotation:
        """Get existing mask or create new one.

        Args:
            label_id: Unique label ID
            label_name: Human-readable label name
            volume_shape: Shape of the volume (z, y, x)
            color: RGB color for visualization
            reference_mask: Optional reference mask array with label values.
                           Voxels matching the mapped reference value will be extracted.

        Returns:
            MaskAnnotation instance
        """
        if label_id not in self.masks:
            if reference_mask is not None:
                # Map UI label_id to reference mask value
                ref_value = config.LABEL_TO_REFERENCE_VALUE.get(label_id, label_id)
                print(f"  [get_or_create_mask] label_id={label_id} -> ref_value={ref_value}")
                # Extract only the specific label from reference mask
                mask_data = (reference_mask == ref_value).astype(np.uint8) * 255
                print(f"  [get_or_create_mask] extracted {np.sum(mask_data > 0)} voxels")
            else:
                mask_data = np.zeros(volume_shape, dtype=np.uint8)
            self.masks[label_id] = MaskAnnotation(
                label_id=label_id,
                label_name=label_name,
                mask=mask_data,
                color=color,
            )
            self.modified = True
        return self.masks[label_id]

    def update_mask(self, label_id: int, mask: MaskAnnotation) -> None:
        """Update or add a mask annotation."""
        self.masks[label_id] = mask
        self.modified = True

    def clear_mask(self, label_id: int) -> None:
        """Remove a mask annotation."""
        if label_id in self.masks:
            del self.masks[label_id]
            self.modified = True

    def get_keypoints_on_slice(
        self, plane: str, slice_index: int
    ) -> List[Tuple[int, Keypoint, Tuple[float, float]]]:
        """Get all keypoints visible on given slice.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            slice_index: Current slice index

        Returns:
            List of (index, keypoint, 2d_position) tuples
        """
        result = []
        for i, kp in enumerate(self.keypoints):
            pos_2d = kp.get_2d_position(plane, slice_index)
            if pos_2d is not None:
                result.append((i, kp, pos_2d))
        return result

    def mark_saved(self) -> None:
        """Mark annotations as saved (not modified)."""
        self.modified = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (masks saved separately)."""
        return {
            "patient_id": self.patient_id,
            "keypoints": [kp.to_dict() for kp in self.keypoints],
            "line_segments": [ls.to_dict() for ls in self.line_segments],
            "masks": {str(k): v.to_dict() for k, v in self.masks.items()},
        }

    @classmethod
    def from_dict(
        cls, d: dict, mask_arrays: Optional[Dict[str, np.ndarray]] = None
    ) -> "Annotations":
        """Create from dictionary.

        Args:
            d: Metadata dictionary
            mask_arrays: Dictionary of mask arrays keyed by 'label_{id}'

        Returns:
            Annotations instance
        """
        ann = cls(patient_id=d["patient_id"])
        ann.keypoints = [Keypoint.from_dict(kp) for kp in d.get("keypoints", [])]
        ann.line_segments = [LineSegment.from_dict(ls) for ls in d.get("line_segments", [])]

        for label_id_str, mask_info in d.get("masks", {}).items():
            label_id = int(label_id_str)
            mask_key = f"label_{label_id}"
            if mask_arrays and mask_key in mask_arrays:
                ann.masks[label_id] = MaskAnnotation(
                    label_id=label_id,
                    label_name=mask_info["label_name"],
                    mask=mask_arrays[mask_key],
                    color=tuple(mask_info["color"]),
                )

        ann.modified = False
        return ann
