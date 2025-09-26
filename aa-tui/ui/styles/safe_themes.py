"""Safe theme definitions with minimal styling to avoid color format errors."""

from prompt_toolkit.styles import Style

# Minimal safe dark theme
SAFE_DARK_THEME = Style.from_dict({
    # Use safe color specifications
    '': '#ffffff',  # Default text
    'bold': 'bold',
    'title': '#00ff00',
    'title.status': '#87ceeb',
    'error': '#ff0000',
    'success': '#00ff00',
    'warning': '#ffff00',
    'info': '#00ffff',

    # Conversation styles
    'conversation': '#ffffff',
    'conversation.user': 'bold #00ff00',
    'conversation.agent': '#87ceeb',
    'conversation.system': '#ffff00',

    # Foldable sections
    'foldable.header': 'bold #ff6600',
    'foldable.header.expanded': 'bold #00ff00',
    'foldable.header.collapsed': 'bold #666666',
    'foldable.content': '#cccccc',

    # Side panel
    'sidepanel': '#e6e6e6',
    'sidepanel.title': 'bold #ffffff',
    'sidepanel.content': '#cccccc',

    # Dialog
    'dialog': '#ffffff',
    'dialog.title': 'bold #ffffff',
    'dialog.border': '#87ceeb',

    # Input
    'input': '#ffffff',
    'input.prompt': 'bold #00ff00',
    'status': '#87ceeb',
    'statusbar': '#87ceeb',
    'statusbar.key': 'bold #87ceeb',

    # Progress
    'progress.bar': '#00ff00',

    # Memory types
    'memory': '#98fb98',
    'memory.working': '#87ceeb',
    'memory.semantic': '#98fb98',
    'memory.episodic': '#dda0dd',
    'memory.document': '#f0e68c',

    # Tools and actions
    'tool': '#ff6600',
    'tool.success': '#00ff00',
    'tool.error': '#ff0000',
    'thought': '#ffff00',
    'action': '#ff00ff',
    'observation': '#00ff00',
})

# Minimal safe light theme
SAFE_LIGHT_THEME = Style.from_dict({
    '': '#000000',  # Default text
    'bold': 'bold',
    'title': '#0066cc',
    'title.status': '#666666',
    'error': '#cc0000',
    'success': '#006600',
    'warning': '#cc6600',
    'info': '#0066cc',

    # Conversation styles
    'conversation': '#000000',
    'conversation.user': 'bold #0066cc',
    'conversation.agent': '#333333',
    'conversation.system': '#666666',

    # Foldable sections
    'foldable.header': 'bold #cc6600',
    'foldable.header.expanded': 'bold #006600',
    'foldable.header.collapsed': 'bold #999999',
    'foldable.content': '#333333',

    # Side panel
    'sidepanel': '#000000',
    'sidepanel.title': 'bold #000000',
    'sidepanel.content': '#333333',

    # Dialog
    'dialog': '#000000',
    'dialog.title': 'bold #000000',
    'dialog.border': '#0066cc',

    # Input
    'input': '#000000',
    'input.prompt': 'bold #0066cc',
    'status': '#0066cc',
    'statusbar': '#0066cc',
    'statusbar.key': 'bold #0066cc',

    # Progress
    'progress.bar': '#006600',

    # Memory types
    'memory': '#006600',
    'memory.working': '#0066cc',
    'memory.semantic': '#006600',
    'memory.episodic': '#6600cc',
    'memory.document': '#cc6600',

    # Tools and actions
    'tool': '#cc6600',
    'tool.success': '#006600',
    'tool.error': '#cc0000',
    'thought': '#cc6600',
    'action': '#cc0066',
    'observation': '#006600',
})

# Available themes
SAFE_THEMES = {
    'dark': SAFE_DARK_THEME,
    'light': SAFE_LIGHT_THEME,
}

def get_safe_theme(theme_name: str) -> Style:
    """Get safe theme by name."""
    return SAFE_THEMES.get(theme_name, SAFE_DARK_THEME)