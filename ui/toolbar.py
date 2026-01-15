"""Toolbar for tool mode selection and common actions."""

from PySide6.QtWidgets import (
    QToolBar, QWidget, QPushButton, QButtonGroup, QHBoxLayout,
    QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon


class ToolBar(QToolBar):
    """Main toolbar with tool selection and action buttons.

    Provides:
    - Tool mode selection (View, Keypoint, Brush)
    - Save/Save All buttons
    - Current mode indicator
    """

    # Signals
    tool_changed = Signal(str)  # tool name
    save_requested = Signal()
    save_all_requested = Signal()
    load_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self._current_tool = "view"
        self._setup_ui()

    def _setup_ui(self):
        """Create the toolbar UI."""
        # File operations
        self.load_button = QPushButton("Load Folder")
        self.load_button.clicked.connect(self.load_requested.emit)
        self.addWidget(self.load_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_requested.emit)
        self.addWidget(self.save_button)

        self.save_all_button = QPushButton("Save All")
        self.save_all_button.clicked.connect(self.save_all_requested.emit)
        self.addWidget(self.save_all_button)

        self.addSeparator()

        # Tool mode label
        mode_label = QLabel("Mode:")
        self.addWidget(mode_label)

        # Tool mode buttons
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.setExclusive(True)

        self.view_button = QPushButton("View")
        self.view_button.setCheckable(True)
        self.view_button.setChecked(True)
        self.view_button.setToolTip("View mode - Pan and zoom (1)")
        self.tool_button_group.addButton(self.view_button)

        self.keypoint_button = QPushButton("Keypoint")
        self.keypoint_button.setCheckable(True)
        self.keypoint_button.setToolTip("Keypoint mode - Click to add points (2)")
        self.tool_button_group.addButton(self.keypoint_button)

        self.brush_button = QPushButton("Brush")
        self.brush_button.setCheckable(True)
        self.brush_button.setToolTip("Brush mode - Paint masks (3)")
        self.tool_button_group.addButton(self.brush_button)

        self.addWidget(self.view_button)
        self.addWidget(self.keypoint_button)
        self.addWidget(self.brush_button)

        # Connect button group
        self.tool_button_group.buttonClicked.connect(self._on_tool_button_clicked)

        self.addSeparator()

        # Erase mode toggle (only visible in brush mode)
        self.erase_button = QPushButton("Erase")
        self.erase_button.setCheckable(True)
        self.erase_button.setToolTip("Toggle erase mode for brush (E)")
        self.erase_button.setVisible(False)
        self.addWidget(self.erase_button)

        # Spacer to push status to right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.addWidget(spacer)

        # Current tool indicator
        self.tool_indicator = QLabel("Mode: View")
        self.tool_indicator.setStyleSheet("font-weight: bold; padding: 0 10px;")
        self.addWidget(self.tool_indicator)

    def _on_tool_button_clicked(self, button):
        """Handle tool button click."""
        if button == self.view_button:
            self._set_tool("view")
        elif button == self.keypoint_button:
            self._set_tool("keypoint")
        elif button == self.brush_button:
            self._set_tool("brush")

    def _set_tool(self, tool_name: str):
        """Set the current tool."""
        self._current_tool = tool_name
        self.tool_indicator.setText(f"Mode: {tool_name.capitalize()}")

        # Show/hide erase button based on tool
        self.erase_button.setVisible(tool_name == "brush")

        self.tool_changed.emit(tool_name)

    def set_tool(self, tool_name: str):
        """Programmatically set the current tool."""
        if tool_name == "view":
            self.view_button.setChecked(True)
        elif tool_name == "keypoint":
            self.keypoint_button.setChecked(True)
        elif tool_name == "brush":
            self.brush_button.setChecked(True)
        self._set_tool(tool_name)

    def get_current_tool(self) -> str:
        """Get the current tool name."""
        return self._current_tool

    def is_erase_mode(self) -> bool:
        """Check if erase mode is enabled."""
        return self.erase_button.isChecked()

    def set_erase_mode(self, enabled: bool):
        """Set erase mode."""
        self.erase_button.setChecked(enabled)
