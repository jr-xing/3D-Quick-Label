# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

3D Quick Label is a Python GUI application for annotating 3D medical imaging data (NIfTI format). It provides multi-planar viewing (axial, sagittal, coronal) with multiple annotation modes: keypoint placement, brush painting, and segment (contour fill) tools.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

# Or load a specific folder
python main.py /path/to/medical/images
```

## Architecture

**Layered structure:**

- `core/` - Data layer: VolumeData (3D image wrapper via SimpleITK), Patient (container with lazy loading), Annotations (keypoints + masks with modification tracking), persistence (JSON + NPZ serialization)
- `ui/` - PySide6 Qt interface: MainWindow (coordinator), SliceView (2D slice renderer), PatientListWidget, ControlsWidget, ToolBar
- `tools/` - Annotation tools: SegmentTool (contour-based mask filling). Note: KeypointTool and BrushTool logic is handled directly in MainWindow due to metaclass conflicts with QObject+ABC
- `config.py` - Global configuration (colors, shortcuts, label definitions, file patterns)

**Key design patterns:**

- **Lazy loading**: Patient images only load on `patient.load()`, with explicit `patient.unload()` for memory management
- **Coordinate system**: All coordinates in (Z, Y, X) order (medical imaging convention)
- **Signal/slot**: Tools emit `annotation_added`, `annotation_modified`, `annotation_removed` signals for loose coupling

## Data Format

Annotations stored relative to patient image:
- `annotations/{patient_id}.json` - Metadata and keypoints
- `annotations/{patient_id}_masks.npz` - Binary mask arrays (NumPy compressed)

## Adding New Tools

1. Create class extending `BaseTool` in `tools/`
2. Implement: `mouse_press()`, `mouse_move()`, `mouse_release()`, `get_cursor()`
3. Emit appropriate signals
4. Register in `MainWindow._setup_tools()`

## Annotation Tools

**Tool Modes** (keyboard shortcuts 1-4):
1. **View** (1) - Pan with Ctrl+drag, zoom with Ctrl+scroll
2. **Keypoint** (2) - Left-click to add, right-click to remove points
3. **Brush** (3) - Left-click+drag to paint, right-click+drag to erase
4. **Segment** (4) - Draw contour and fill enclosed region as mask; right-click for erase mode

**Reference Mask Editing:**
- Reference masks (loaded from `*_label.nii.gz`) use different values than UI labels
- `config.LABEL_TO_REFERENCE_VALUE` maps UI label IDs (1-7) to NIfTI values (205, 420, 500, etc.)
- When user edits a label, the reference mask region is copied to user annotations and hidden from reference display

## Tech Stack

- Python 3.10+
- PySide6 (Qt GUI)
- SimpleITK (NIfTI I/O)
- NumPy, SciPy, scikit-image, OpenCV
