"""Save and load annotations."""

import json
from pathlib import Path
from typing import Dict, Optional
import numpy as np

from .annotation import Annotations, Keypoint, MaskAnnotation
from .patient import Patient


def save_patient_annotations(patient: Patient, output_dir: Path) -> None:
    """Save annotations for a single patient.

    Saves:
    - JSON file with metadata and keypoints
    - NPZ file with compressed mask arrays

    Args:
        patient: Patient with annotations to save
        output_dir: Directory to save annotations to
    """
    if patient.annotations is None:
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ann = patient.annotations

    # Prepare JSON data
    json_data = {
        "patient_id": ann.patient_id,
        "image_path": patient.image_path,
        "mask_path": patient.mask_path,
        "keypoints": [kp.to_dict() for kp in ann.keypoints],
        "masks": {},
    }

    # Save masks as compressed numpy
    if ann.masks:
        masks_file = output_dir / f"{ann.patient_id}_masks.npz"
        mask_arrays = {}
        for label_id, mask_ann in ann.masks.items():
            if mask_ann.has_data():
                mask_arrays[f"label_{label_id}"] = mask_ann.mask
                json_data["masks"][str(label_id)] = {
                    "label_name": mask_ann.label_name,
                    "color": list(mask_ann.color),
                }
        if mask_arrays:
            np.savez_compressed(str(masks_file), **mask_arrays)

    # Save JSON
    json_file = output_dir / f"{ann.patient_id}.json"
    with open(json_file, "w") as f:
        json.dump(json_data, f, indent=2)

    ann.mark_saved()


def load_patient_annotations(
    patient_id: str, annotations_dir: Path, volume_shape: tuple
) -> Optional[Annotations]:
    """Load annotations for a patient if they exist.

    Args:
        patient_id: ID of the patient
        annotations_dir: Directory containing annotation files
        volume_shape: Shape of the volume (z, y, x) for mask creation

    Returns:
        Annotations instance if found, None otherwise
    """
    annotations_dir = Path(annotations_dir)
    json_file = annotations_dir / f"{patient_id}.json"

    if not json_file.exists():
        return None

    with open(json_file) as f:
        data = json.load(f)

    ann = Annotations(patient_id=patient_id)

    # Load keypoints
    ann.keypoints = [Keypoint.from_dict(kp) for kp in data.get("keypoints", [])]

    # Load masks
    masks_file = annotations_dir / f"{patient_id}_masks.npz"
    if masks_file.exists():
        mask_data = np.load(str(masks_file))
        for label_id_str, mask_info in data.get("masks", {}).items():
            label_id = int(label_id_str)
            mask_key = f"label_{label_id}"
            if mask_key in mask_data:
                mask_array = mask_data[mask_key]
                # Verify shape matches
                if mask_array.shape == volume_shape:
                    ann.masks[label_id] = MaskAnnotation(
                        label_id=label_id,
                        label_name=mask_info["label_name"],
                        mask=mask_array,
                        color=tuple(mask_info["color"]),
                    )

    ann.modified = False
    return ann


def save_all_patients(patients: Dict[str, Patient], output_dir: Path) -> int:
    """Save all patients with unsaved changes.

    Args:
        patients: Dictionary of patient_id -> Patient
        output_dir: Directory to save annotations to

    Returns:
        Number of patients saved
    """
    saved = 0
    for patient in patients.values():
        if patient.has_unsaved_changes:
            save_patient_annotations(patient, output_dir)
            saved += 1
    return saved


def try_load_existing_annotations(patient: Patient) -> bool:
    """Try to load existing annotations for a patient.

    Looks for annotation files in the annotations directory
    relative to the image path.

    Args:
        patient: Patient to load annotations for

    Returns:
        True if annotations were loaded
    """
    from config import ANNOTATIONS_DIR

    image_dir = Path(patient.image_path).parent
    annotations_dir = image_dir / ANNOTATIONS_DIR

    # Need volume shape, so ensure patient is loaded
    if not patient.is_loaded:
        patient.load()

    volume_shape = patient.image.shape

    ann = load_patient_annotations(patient.patient_id, annotations_dir, volume_shape)
    if ann is not None:
        patient.annotations = ann
        return True

    return False
