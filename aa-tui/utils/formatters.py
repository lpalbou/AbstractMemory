"""Text formatting utilities for the TUI."""

import re
from typing import List, Tuple
from prompt_toolkit.formatted_text import FormattedText


def format_code_block(text: str, language: str = "") -> FormattedText:
    """
    Format a code block with syntax highlighting.

    Args:
        text: Code text
        language: Programming language for highlighting

    Returns:
        FormattedText with syntax highlighting
    """
    # Simple syntax highlighting based on common patterns
    lines = text.split('\n')
    formatted_parts = []

    for line in lines:
        line_parts = []

        # Keywords (Python-like)
        keywords = ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'import', 'from', 'return', 'yield']

        # Simple tokenization
        tokens = re.split(r'(\s+|[(){}[\],.:;])', line)

        for token in tokens:
            if token in keywords:
                line_parts.append(('class:syntax.keyword', token))
            elif token.startswith('"') and token.endswith('"'):
                line_parts.append(('class:syntax.string', token))
            elif token.startswith("'") and token.endswith("'"):
                line_parts.append(('class:syntax.string', token))
            elif token.startswith('#'):
                line_parts.append(('class:syntax.comment', token))
            elif token.isdigit():
                line_parts.append(('class:syntax.number', token))
            else:
                line_parts.append(('', token))

        formatted_parts.extend(line_parts)
        formatted_parts.append(('', '\n'))

    return FormattedText(formatted_parts)


def format_json(text: str) -> FormattedText:
    """
    Format JSON text with basic highlighting.

    Args:
        text: JSON text

    Returns:
        FormattedText with JSON highlighting
    """
    formatted_parts = []

    # Simple JSON highlighting
    for char in text:
        if char in '{}[]':
            formatted_parts.append(('class:syntax.keyword', char))
        elif char in '":,':
            formatted_parts.append(('', char))
        else:
            formatted_parts.append(('', char))

    return FormattedText(formatted_parts)


def format_tool_result(tool_name: str, tool_input: dict, tool_result: str, success: bool = True) -> FormattedText:
    """
    Format tool execution result.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters
        tool_result: Tool execution result
        success: Whether execution was successful

    Returns:
        FormattedText with formatted tool result
    """
    status_style = 'tool.success' if success else 'tool.error'
    status_icon = '✅' if success else '❌'

    parts = [
        (status_style, f"{status_icon} {tool_name}"),
        ('', f"({tool_input})\n"),
        ('class:foldable.content', f"Result: {tool_result}")
    ]

    return FormattedText(parts)


def format_memory_item(item: dict, item_type: str = "unknown") -> FormattedText:
    """
    Format memory item for display.

    Args:
        item: Memory item data
        item_type: Type of memory item

    Returns:
        FormattedText with formatted memory item
    """
    content = str(item.get('content', ''))[:100]
    confidence = item.get('confidence', 0.0)

    type_style = f'memory.{item_type}' if item_type in ['working', 'semantic', 'episodic', 'document'] else 'default'

    parts = [
        (type_style, f"[{item_type}] "),
        ('class:foldable.content', content),
        ('', '...\n' if len(str(item.get('content', ''))) > 100 else '\n'),
        ('', f"Confidence: {confidence:.2f}")
    ]

    return FormattedText(parts)


def format_thought_action(text: str) -> FormattedText:
    """
    Format ReAct thought/action text with highlighting.

    Args:
        text: Thought/action text

    Returns:
        FormattedText with highlighted keywords
    """
    formatted_parts = []
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith('Thought:'):
            formatted_parts.append(('class:thought', line))
        elif line.startswith('Action:'):
            formatted_parts.append(('class:action', line))
        elif line.startswith('Action Input:'):
            formatted_parts.append(('class:action', line))
        elif line.startswith('Observation:'):
            formatted_parts.append(('class:observation', line))
        elif line.startswith('Final Answer:'):
            formatted_parts.append(('class:conversation.agent', line))
        else:
            formatted_parts.append(('class:foldable.content', line))
        formatted_parts.append(('', '\n'))

    return FormattedText(formatted_parts)


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def format_time_duration(seconds: float) -> str:
    """
    Format time duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.0f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f"{hours}h {remaining_minutes}m"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def wrap_text(text: str, width: int = 80) -> List[str]:
    """
    Wrap text to specified width.

    Args:
        text: Text to wrap
        width: Maximum line width

    Returns:
        List of wrapped lines
    """
    import textwrap
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)