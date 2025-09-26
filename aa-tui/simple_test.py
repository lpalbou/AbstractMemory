#!/usr/bin/env python3
"""
Simple test for basic TUI functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from core.config import TUIConfig
from ui.styles.safe_themes import get_safe_theme
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.layout.containers import VSplit, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Layout


async def simple_test():
    """Simple test of prompt_toolkit basics."""
    print("🧪 Running simple TUI test...")

    # Create basic layout
    title = Window(
        content=FormattedTextControl(HTML('<b>AbstractMemory TUI Test</b>')),
        height=1
    )

    content = Window(
        content=FormattedTextControl(HTML('''
<b>Welcome to AbstractMemory TUI!</b>

This is a basic test of the prompt_toolkit interface.

Features being tested:
• HTML formatting
• Layout containers
• Theme system
• Keyboard shortcuts

Press <b>Ctrl+Q</b> to exit.
        ''')),
        wrap_lines=True
    )

    status = Window(
        content=FormattedTextControl(HTML('<b>Status:</b> Test running - Press Ctrl+Q to quit')),
        height=1
    )

    root_container = HSplit([
        title,
        content,
        status
    ])

    # Create layout
    layout = Layout(root_container)

    # Create key bindings
    from prompt_toolkit.key_binding import KeyBindings
    kb = KeyBindings()

    @kb.add('c-q')
    def quit_app(event):
        event.app.exit()

    # Create application
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=get_safe_theme('dark'),
        full_screen=True,
        mouse_support=True
    )

    print("🎯 Starting basic TUI...")

    try:
        await app.run_async()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    finally:
        print("✅ Basic TUI test completed!")


if __name__ == "__main__":
    asyncio.run(simple_test())