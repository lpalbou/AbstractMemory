#!/usr/bin/env python3
"""
Debug version of TUI to isolate the color format error.
"""

import asyncio
import sys
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

# Very simple safe style
SIMPLE_STYLE = Style.from_dict({
    '': '#ffffff',
    'title': '#00ff00',
    'error': '#ff0000',
    'info': '#00ffff',
})

class DebugTUI:
    def __init__(self):
        # Create key bindings
        self.kb = KeyBindings()

        @self.kb.add('c-q')
        def quit_app(event):
            event.app.exit()

        # Create simple layout
        title_window = Window(
            content=FormattedTextControl(
                text=FormattedText([('title', ' Debug TUI Test ')])
            ),
            height=1
        )

        main_window = Window(
            content=FormattedTextControl(
                text=FormattedText([('info', 'This is a debug TUI test. Press Ctrl+Q to quit.')])
            )
        )

        layout = Layout(HSplit([
            title_window,
            main_window,
        ]))

        # Create application
        self.app = Application(
            layout=layout,
            key_bindings=self.kb,
            style=SIMPLE_STYLE,
            full_screen=True
        )

    async def run_async(self):
        print("🚀 Starting debug TUI...")
        print("Press Ctrl+Q to quit")
        try:
            await self.app.run_async()
            print("✅ TUI ran successfully")
        except Exception as e:
            print(f"❌ TUI failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    tui = DebugTUI()
    asyncio.run(tui.run_async())