"""Annotation data structures for 3D medical imaging."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np


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

    Manages keypoints and multiple mask labels, tracking
    modification state for save prompts.
    """

    patient_id: str
    keypoints: List[Keypoint] = field(default_factory=list)
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

    def get_or_create_mask(
        self, label_id: int, label_name: str, volume_shape: Tuple[int, int, int],
        color: Tuple[int, int, int] = (0, 255, 0)
    ) -> MaskAnnotation:
        """Get existing mask or create new one.

        Args:
            label_id: Unique label ID
            label_name: Human-readable label name
            volume_shape: Shape of the volume (z, y, x)
            color: RGB color for visualization

        Returns:
            MaskAnnotation instance
        """
        if label_id not in self.masks:
            self.masks[label_id] = MaskAnnotation(
                label_id=label_id,
                label_name=label_name,
                mask=np.zeros(volume_shape, dtype=np.uint8),
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
