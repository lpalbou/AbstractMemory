"""
Deprecated AbstractMemory Components

This package contains legacy components that have been superseded by newer implementations.
These are preserved for backward compatibility and reference.

⚠️  WARNING: These components are deprecated and may be removed in future versions.
    Use the modern implementations in the parent abstractmemory package instead.

Migration Guide:
- Use `abstractmemory.memory_session.MemorySession` instead of `abstractmemory.deprecated.session.MemorySession`
- Background processing is now handled by TaskQueue in the modern implementation
- Structured responses are handled by AbstractCore in the modern implementation
"""

import warnings

# Issue deprecation warning when this package is imported
warnings.warn(
    "abstractmemory.deprecated is deprecated. Use the modern implementations in abstractmemory package instead.",
    DeprecationWarning,
    stacklevel=2
)
