"""
Reasoning module for AbstractMemory.

This module contains reasoning logic that will eventually move to AbstractAgent.
For now, it lives here to maintain development velocity while keeping clear
architectural boundaries.

NOTE: This module should have ZERO dependencies on TUI or display logic.
      It works purely with MemorySession and standard Python types.
"""

from .react_loop import ReactLoop, ReactConfig

__all__ = ['ReactLoop', 'ReactConfig']