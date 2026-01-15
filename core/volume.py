"""Volume data handling with SimpleITK."""

from dataclasses import dataclass, field
from typing import Optional, Tuple
import SimpleITK as sitk
import numpy as np


@dataclass
class VolumeData:
    """Lightweight wrapper for 3D medical volume data.

    Handles NIfTI file loading via SimpleITK and provides slice extraction
    for different anatomical planes.

    Note: SimpleITK returns arrays in (z, y, x) order which matches
    the standard medical imaging convention.
    """

    filepath: str
    _image: Optional[sitk.Image] = field(default=None, repr=False)
    _array: Optional[np.ndarray] = field(default=None, repr=False)

    # Cached metadata
    shape: Tuple[int, int, int] = field(default=(0, 0, 0))
    spacing: Tuple[float, float, float] = field(default=(1.0, 1.0, 1.0))
    origin: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0))
    direction: Tuple[float, ...] = field(default=())

    def load(self) -> None:
        """Load NIfTI file using SimpleITK."""
        self._image = sitk.ReadImage(self.filepath)
        # SimpleITK GetArrayFromImage returns (z, y, x) ordering
        self._array = sitk.GetArrayFromImage(self._image)
        self.shape = self._array.shape
        # SimpleITK spacing is (x, y, z), convert to (z, y, x) to match array
        sitk_spacing = self._image.GetSpacing()
        self.spacing = (sitk_spacing[2], sitk_spacing[1], sitk_spacing[0])
        sitk_origin = self._image.GetOrigin()
        self.origin = (sitk_origin[2], sitk_origin[1], sitk_origin[0])
        self.direction = self._image.GetDirection()

    @property
    def array(self) -> np.ndarray:
        """Return numpy array in (z, y, x) ordering."""
        if self._array is None:
            self.load()
        return self._array

    @property
    def is_loaded(self) -> bool:
        """Check if volume data is loaded."""
        return self._array is not None

    def unload(self) -> None:
        """Free memory by clearing cached data."""
        self._array = None
        self._image = None

    def get_axial_slice(self, z: int) -> np.ndarray:
        """Get axial slice (XY plane at given Z index).

        Args:
            z: Z-axis index (0 to shape[0]-1)

        Returns:
            2D numpy array of shape (height, width) = (Y, X)
        """
        z = max(0, min(z, self.shape[0] - 1))
        return self.array[z, :, :]

    def get_sagittal_slice(self, x: int) -> np.ndarray:
        """Get sagittal slice (YZ plane at given X index).

        Args:
            x: X-axis index (0 to shape[2]-1)

        Returns:
            2D numpy array of shape (height, width) = (Z, Y)
        """
        x = max(0, min(x, self.shape[2] - 1))
        return self.array[:, :, x]

    def get_coronal_slice(self, y: int) -> np.ndarray:
        """Get coronal slice (XZ plane at given Y index).

        Args:
            y: Y-axis index (0 to shape[1]-1)

        Returns:
            2D numpy array of shape (height, width) = (Z, X)
        """
        y = max(0, min(y, self.shape[1] - 1))
        return self.array[:, y, :]

    def get_slice(self, plane: str, index: int) -> np.ndarray:
        """Get slice for specified plane.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'
            index: Slice index

        Returns:
            2D numpy array
        """
        if plane == "axial":
            return self.get_axial_slice(index)
        elif plane == "sagittal":
            return self.get_sagittal_slice(index)
        elif plane == "coronal":
            return self.get_coronal_slice(index)
        else:
            raise ValueError(f"Unknown plane: {plane}")

    def get_max_index(self, plane: str) -> int:
        """Get maximum valid index for given plane.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'

        Returns:
            Maximum valid slice index
        """
        if plane == "axial":
            return self.shape[0] - 1
        elif plane == "sagittal":
            return self.shape[2] - 1
        elif plane == "coronal":
            return self.shape[1] - 1
        else:
            raise ValueError(f"Unknown plane: {plane}")

    def get_value_range(self) -> Tuple[float, float]:
        """Get min/max values for windowing.

        Returns:
            Tuple of (min_value, max_value)
        """
        return float(self.array.min()), float(self.array.max())

    def get_slice_shape(self, plane: str) -> Tuple[int, int]:
        """Get shape of slices for given plane.

        Args:
            plane: One of 'axial', 'sagittal', 'coronal'

        Returns:
            Tuple of (height, width)
        """
        if plane == "axial":
            return (self.shape[1], self.shape[2])  # (Y, X)
        elif plane == "sagittal":
            return (self.shape[0], self.shape[1])  # (Z, Y)
        elif plane == "coronal":
            return (self.shape[0], self.shape[2])  # (Z, X)
        else:
            raise ValueError(f"Unknown plane: {plane}")
