"""Theme definitions for the TUI."""

from prompt_toolkit.styles import Style

# Dark theme (default)
DARK_THEME = Style.from_dict({
    # Base colors
    '': '#ffffff',  # Default text color

    # Title bar
    'title': 'bold #00ff00',
    'title.status': '#87ceeb',

    # Conversation area
    'conversation': '#ffffff',
    'conversation.user': 'bold #00ff00',
    'conversation.agent': '#87ceeb',
    'conversation.system': '#ffff00',

    # Foldable sections
    'foldable.header': 'bold #ff6600',
    'foldable.header.expanded': 'bold #00ff00',
    'foldable.header.collapsed': 'bold #666666',
    'foldable.content': '#cccccc',

    # Thoughts and actions
    'thought': '#ffff00 bold',
    'action': '#ff00ff bold',
    'observation': '#00ff00 bold',
    'tool.success': '#00ff00',
    'tool.error': '#ff0000',

    # Side panel
    'sidepanel': '#e6e6e6 bg:#333333',
    'sidepanel.title': 'bold #ffffff bg:#333333',
    'sidepanel.content': '#cccccc bg:#333333',

    # Memory display
    'memory.working': '#87ceeb',
    'memory.semantic': '#98fb98',
    'memory.episodic': '#dda0dd',
    'memory.document': '#f0e68c',

    # Input area
    'input': '#ffffff bg:#111111',
    'input.prompt': 'bold #00ff00',
    'input.suggestion': '#666666',

    # Status bar
    'statusbar': '#000000 bg:#87ceeb',
    'statusbar.key': 'bold #000000 bg:#87ceeb',

    # Progress indicators
    'progress.bar': '#00ff00 bg:#333333',
    'progress.percentage': 'bold #ffffff',

    # Dialogs
    'dialog': '#000000 bg:#e6e6e6',
    'dialog.title': 'bold #000000 bg:#87ceeb',
    'dialog.border': '#87ceeb',

    # Buttons
    'button': '#000000 bg:#87ceeb',
    'button.focused': '#ffffff bg:#0066cc',

    # Scrollbars
    'scrollbar': '#666666',
    'scrollbar.background': '#333333',

    # Selection
    'selection': '#ffffff bg:#0066cc',

    # Syntax highlighting
    'syntax.keyword': '#ff6600',
    'syntax.string': '#00ff00',
    'syntax.comment': '#666666',
    'syntax.number': '#87ceeb',
})

# Light theme
LIGHT_THEME = Style.from_dict({
    # Base colors
    '': '#000000',  # Default text color

    # Title bar
    'title': 'bold #0066cc',
    'title.status': '#666666',

    # Conversation area
    'conversation': '#000000',
    'conversation.user': 'bold #0066cc',
    'conversation.agent': '#333333',
    'conversation.system': '#666666',

    # Foldable sections
    'foldable.header': 'bold #cc6600',
    'foldable.header.expanded': 'bold #006600',
    'foldable.header.collapsed': 'bold #999999',
    'foldable.content': '#333333',

    # Thoughts and actions
    'thought': '#cc6600 bold',
    'action': '#cc0066 bold',
    'observation': '#006600 bold',
    'tool.success': '#006600',
    'tool.error': '#cc0000',

    # Side panel
    'sidepanel': '#000000 bg:#f0f0f0',
    'sidepanel.title': 'bold #000000 bg:#e0e0e0',
    'sidepanel.content': '#333333 bg:#f0f0f0',

    # Memory display
    'memory.working': '#0066cc',
    'memory.semantic': '#006600',
    'memory.episodic': '#6600cc',
    'memory.document': '#cc6600',

    # Input area
    'input': '#000000 bg:#ffffff',
    'input.prompt': 'bold #0066cc',
    'input.suggestion': '#999999',

    # Status bar
    'statusbar': '#ffffff bg:#0066cc',
    'statusbar.key': 'bold #ffffff bg:#0066cc',

    # Progress indicators
    'progress.bar': '#006600 bg:#e0e0e0',
    'progress.percentage': 'bold #000000',

    # Dialogs
    'dialog': '#000000 bg:#ffffff',
    'dialog.title': 'bold #ffffff bg:#0066cc',
    'dialog.border': '#0066cc',

    # Buttons
    'button': '#000000 bg:#e0e0e0',
    'button.focused': '#ffffff bg:#0066cc',

    # Scrollbars
    'scrollbar': '#cccccc',
    'scrollbar.background': '#f0f0f0',

    # Selection
    'selection': '#ffffff bg:#0066cc',

    # Syntax highlighting
    'syntax.keyword': '#cc6600',
    'syntax.string': '#006600',
    'syntax.comment': '#999999',
    'syntax.number': '#0066cc',
})

# Available themes
THEMES = {
    'dark': DARK_THEME,
    'light': LIGHT_THEME,
}

def get_theme(theme_name: str) -> Style:
    """Get theme by name."""
    return THEMES.get(theme_name, DARK_THEME)