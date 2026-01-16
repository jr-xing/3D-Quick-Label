"""Annotation tools module.

Note: For this lightweight implementation, tool logic is handled directly
in the main_window.py for simplicity. This module provides base classes
and constants that could be used for a more modular tool system.
"""

from .segment_tool import SegmentTool

# Note: BaseTool, KeypointTool, BrushTool have metaclass conflicts and are not used
# The tool logic is handled directly in main_window.py for simplicity

__all__ = ["SegmentTool"]
