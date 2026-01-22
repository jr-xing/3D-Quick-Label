#!/usr/bin/env python
"""Cardiac View Planning - Standard cardiac view planning from 3D volumes.

A tool for creating standard cardiac imaging views (2-chamber, 4-chamber,
short-axis) from 3D medical volumes using interactive line segment annotations.

Usage:
    python cardiac_planning.py [data_folder]

Workflow:
    1. Load a patient folder containing NIfTI files
    2. Draw a line segment on the Axial view (through the heart)
       -> This generates the pseudo 2-chamber (p2ch) view
    3. Draw a line segment on the p2ch view
       -> This generates the pseudo 4-chamber (p4ch) view
    4. Draw a line segment on the p4ch view (along the long axis)
       -> This generates the Short Axis (SAX) view
    5. Use the SAX slider to scroll through short-axis slices

Controls:
    - Left-click + drag: Draw line segment
    - Right-click: Remove line segment
    - Mouse wheel: Scroll slices (top row) or SAX position (bottom right)
    - Ctrl + Mouse wheel: Zoom
    - Ctrl + drag: Pan view
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.cardiac_view_window import CardiacViewWindow


def main():
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Cardiac View Planning")
    app.setApplicationVersion("1.0.0")

    # Create main window
    window = CardiacViewWindow()
    window.show()

    # If a folder was provided as argument, load it
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
        if folder.exists() and folder.is_dir():
            window.load_folder(str(folder))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
