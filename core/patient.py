"""Patient data container."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .volume import VolumeData
from .annotation import Annotations


@dataclass
class Patient:
    """Represents a single patient with image, mask, and annotations.

    Supports lazy loading to manage memory when working with
    multiple patients.
    """

    patient_id: str
    image_path: str
    mask_path: Optional[str] = None

    # Lazily loaded data
    image: Optional[VolumeData] = field(default=None, repr=False)
    reference_mask: Optional[VolumeData] = field(default=None, repr=False)
    annotations: Optional[Annotations] = field(default=None, repr=False)

    _loaded: bool = field(default=False, repr=False)

    def load(self) -> None:
        """Load image and optional reference mask."""
        if self._loaded:
            return

        self.image = VolumeData(self.image_path)
        self.image.load()

        if self.mask_path and Path(self.mask_path).exists():
            self.reference_mask = VolumeData(self.mask_path)
            self.reference_mask.load()

        # Initialize empty annotations if not already loaded from file
        if self.annotations is None:
            self.annotations = Annotations(patient_id=self.patient_id)

        self._loaded = True

    def unload(self) -> None:
        """Free memory but keep annotations.

        Annotations are preserved so they aren't lost when switching
        between patients.
        """
        if self.image:
            self.image.unload()
            self.image = None
        if self.reference_mask:
            self.reference_mask.unload()
            self.reference_mask = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if volume data is loaded."""
        return self._loaded

    @property
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved annotation changes."""
        return self.annotations is not None and self.annotations.modified

    @property
    def volume_shape(self) -> tuple:
        """Get volume shape, loading if necessary."""
        if self.image is None:
            self.load()
        return self.image.shape

    def get_display_name(self) -> str:
        """Get display name for patient list."""
        name = self.patient_id
        if self.has_unsaved_changes:
            name += " *"
        return name

    @classmethod
    def from_image_path(cls, image_path: str) -> "Patient":
        """Create Patient from image file path.

        Automatically determines patient ID and looks for corresponding
        mask file using naming convention.

        Args:
            image_path: Path to image NIfTI file

        Returns:
            Patient instance
        """
        from config import IMAGE_SUFFIX, LABEL_SUFFIX

        path = Path(image_path)
        filename = path.name

        # Extract patient ID from filename
        if filename.endswith(IMAGE_SUFFIX):
            patient_id = filename[:-len(IMAGE_SUFFIX)]
            # Look for corresponding mask
            mask_path = path.parent / f"{patient_id}{LABEL_SUFFIX}"
            mask_path = str(mask_path) if mask_path.exists() else None
        else:
            # Generic NIfTI file
            patient_id = path.stem
            if patient_id.endswith(".nii"):
                patient_id = patient_id[:-4]
            mask_path = None

        return cls(
            patient_id=patient_id,
            image_path=str(path),
            mask_path=mask_path,
        )
