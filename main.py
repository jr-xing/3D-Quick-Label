#!/usr/bin/env python
"""3D Quick Label - Lightweight 3D medical data annotation tool.

A simple multi-planar viewer with annotation capabilities for NIfTI files.
Supports keypoint and mask annotations with persistent storage.

Usage:
    python main.py [data_folder]

Controls:
    - Mouse wheel: Scroll through slices
    - Ctrl + Mouse wheel: Zoom
    - 1: View mode (pan/zoom)
    - 2: Keypoint mode (left-click to add, right-click to remove)
    - 3: Brush mode (drag to paint)
    - E: Toggle erase mode (in brush mode)
    - +/-: Increase/decrease brush size
    - Ctrl+S: Save current patient
    - Ctrl+Shift+S: Save all patients
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("3D Quick Label")
    app.setApplicationVersion("1.0.0")

    # Create main window
    window = MainWindow()
    window.show()

    # If a folder was provided as argument, load it
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
        if folder.exists() and folder.is_dir():
            window.patient_list.load_folder(str(folder))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
