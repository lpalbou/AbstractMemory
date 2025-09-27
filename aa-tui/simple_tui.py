#!/usr/bin/env python3
"""
Simple AbstractMemory TUI - Built from scratch with focus on working text input
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style


class SimpleTUI:
    """Minimal TUI implementation focused on working text input."""

    def __init__(self):
        self.conversation_history = []
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""

        # Create input buffer - THIS IS THE CRITICAL PART
        self.input_buffer = Buffer(
            multiline=False,  # Single line for now to avoid complications
            accept_handler=self.handle_input,
            read_only=False,  # MUST be writable
        )

        # Create conversation buffer (writable for updates, then set read-only)
        self.conversation_buffer = Buffer(
            multiline=True,
            read_only=False,
        )
        # Set initial text
        self.conversation_buffer.text = "Welcome to AbstractMemory TUI!\nType your message below and press Enter.\n\n"
        # Now make it read-only
        self.conversation_buffer.read_only = True

        # Create key bindings - MINIMAL SET ONLY
        self.kb = KeyBindings()

        @self.kb.add('c-q')
        def quit_app(event):
            """Quit with Ctrl+Q"""
            event.app.exit()

        # NO OTHER KEY BINDINGS - let everything else go to input

        # Create layout
        conversation_window = Window(
            content=BufferControl(buffer=self.conversation_buffer),
            wrap_lines=True,
        )

        input_prompt = Window(
            content=FormattedTextControl(text=HTML("<b>You:</b> ")),
            width=5,
            dont_extend_width=True,
        )

        input_window = Window(
            content=BufferControl(buffer=self.input_buffer),
            height=1,
        )

        input_area = VSplit([
            input_prompt,
            input_window,
        ])

        help_bar = Window(
            content=FormattedTextControl(text=HTML("Press <b>Enter</b> to send | <b>Ctrl+Q</b> to quit")),
            height=1,
        )

        root_container = HSplit([
            conversation_window,  # Top: conversation
            input_area,          # Bottom: input
            help_bar,           # Very bottom: help
        ])

        self.layout = Layout(root_container)

        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=Style.from_dict({
                'input': '#ffffff',
                'conversation': '#cccccc',
            }),
            full_screen=True,
            mouse_support=False,  # Disable mouse to avoid complications
        )

    def handle_input(self, buffer):
        """Handle when user submits input."""
        user_input = buffer.text.strip()
        if not user_input:
            return

        # Add to conversation
        self.add_message("User", user_input)

        # Simple echo response for now
        self.add_message("Assistant", f"You said: {user_input}")

        # Clear input
        buffer.reset()

    def add_message(self, sender, message):
        """Add a message to the conversation."""
        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {sender}: {message}\n"

        # Temporarily make buffer writable to update it
        self.conversation_buffer.read_only = False

        # Append to conversation buffer
        current_text = self.conversation_buffer.text
        self.conversation_buffer.text = current_text + formatted_message

        # Auto-scroll to bottom
        self.conversation_buffer.cursor_position = len(self.conversation_buffer.text)

        # Make read-only again
        self.conversation_buffer.read_only = True

    async def run(self):
        """Run the TUI application."""

        # Set initial focus to input
        self.app.layout.focus(self.input_buffer)

        # Run the app
        await self.app.run_async()


def main():
    """Main entry point."""
    print("🚀 Starting Simple AbstractMemory TUI...")
    print("Focus: Working text input from the start")
    print("Type in the input field and press Enter to test")
    print()

    tui = SimpleTUI()
    asyncio.run(tui.run())


if __name__ == "__main__":
    main()