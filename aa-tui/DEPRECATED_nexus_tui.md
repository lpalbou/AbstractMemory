# DEPRECATED: nexus_tui.py

This file is deprecated in favor of `enhanced_tui.py`.

## Reason for Deprecation

`nexus_tui.py` used a now-deleted duplicate session (`core/session.py`).
The correct architecture uses `abstractmemory.MemorySession` directly.

## Current Entry Point

Use: `python -m aa-tui.enhanced_tui`

## Migration

If you need the functionality from nexus_tui.py:
1. Use `enhanced_tui.py` instead
2. It provides the same features with proper MemorySession integration