"""Annotation tools module.

Note: For this lightweight implementation, tool logic is handled directly
in the main_window.py for simplicity. This module provides base classes
and constants that could be used for a more modular tool system.
"""

from .base_tool import BaseTool
from .keypoint_tool import KeypointTool
from .brush_tool import BrushTool

__all__ = ["BaseTool", "KeypointTool", "BrushTool"]
