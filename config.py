"""Configuration constants for 3D Quick Label."""

from typing import Dict, Tuple

# Default window/level values for different modalities
DEFAULT_WINDOW_CENTER = 400
DEFAULT_WINDOW_WIDTH = 1500

# Label colors (RGB)
LABEL_COLORS: Dict[int, Tuple[int, int, int]] = {
    1: (255, 0, 0),      # Red
    2: (0, 255, 0),      # Green
    3: (0, 0, 255),      # Blue
    4: (255, 255, 0),    # Yellow
    5: (255, 0, 255),    # Magenta
    6: (0, 255, 255),    # Cyan
    7: (255, 128, 0),    # Orange
    8: (128, 0, 255),    # Purple
}

# Label names
LABEL_NAMES: Dict[int, str] = {
    1: "Label 1",
    2: "Label 2",
    3: "Label 3",
    4: "Label 4",
    5: "Label 5",
    6: "Label 6",
    7: "Label 7",
    8: "Label 8",
}

# Reference mask color mapping (for loaded NIfTI labels)
REFERENCE_MASK_COLORS: Dict[int, Tuple[int, int, int]] = {
    205: (255, 0, 0),     # Red
    420: (0, 255, 0),     # Green
    500: (0, 0, 255),     # Blue
    550: (255, 255, 0),   # Yellow
    600: (255, 0, 255),   # Magenta
    820: (0, 255, 255),   # Cyan
    850: (255, 128, 0),   # Orange
}

# Keypoint settings
KEYPOINT_RADIUS = 5
KEYPOINT_DEFAULT_COLOR = (255, 0, 0)

# Brush settings
DEFAULT_BRUSH_SIZE = 10
MIN_BRUSH_SIZE = 1
MAX_BRUSH_SIZE = 50

# Mask overlay opacity (0-255)
DEFAULT_MASK_OPACITY = 128

# File patterns
NIFTI_PATTERN = "*.nii.gz"
IMAGE_SUFFIX = "_image.nii.gz"
LABEL_SUFFIX = "_label.nii.gz"

# Annotations directory name
ANNOTATIONS_DIR = "annotations"

# Keyboard shortcuts
SHORTCUTS = {
    "view_mode": "1",
    "keypoint_mode": "2",
    "brush_mode": "3",
    "save": "Ctrl+S",
    "save_all": "Ctrl+Shift+S",
    "load_folder": "Ctrl+O",
    "increase_brush": "+",
    "decrease_brush": "-",
    "toggle_mask": "M",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
}
