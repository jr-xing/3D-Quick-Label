# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

3D Quick Label is a Python GUI application for annotating 3D medical imaging data (NIfTI format). It provides multi-planar viewing (axial, sagittal, coronal) with dual annotation modes: keypoint placement and mask/brush drawing.

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
- `tools/` - Annotation tools extending BaseTool: KeypointTool (point annotations), BrushTool (mask painting)
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

## Tech Stack

- Python 3.10+
- PySide6 (Qt GUI)
- SimpleITK (NIfTI I/O)
- NumPy, SciPy, scikit-image, OpenCV
