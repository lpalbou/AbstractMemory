#!/usr/bin/env python3
"""
Enhanced AbstractMemory TUI - Based on working simple version
Focuses on text input working first, then adds features
"""

import asyncio
import sys
import argparse
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
from prompt_toolkit.completion import Completer, Completion


class CommandCompleter(Completer):
    """Simple command completer."""

    def __init__(self):
        self.commands = [
            '/help', '/status', '/memory', '/tools', '/clear', '/quit'
        ]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()
        if text.startswith('/'):
            for command in self.commands:
                if command.lower().startswith(text):
                    yield Completion(
                        command,
                        start_position=-len(text),
                        display=command,
                        display_meta="command"
                    )


class EnhancedTUI:
    """Enhanced TUI with AbstractMemory integration."""

    def __init__(self, model="qwen3-coder:30b", memory_path="./agent_memory"):
        self.model = model
        self.memory_path = memory_path
        self.conversation_history = []
        self.agent_session = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components with PROVEN working input approach."""

        # Create input buffer - SAME APPROACH THAT WORKS
        self.input_buffer = Buffer(
            multiline=False,
            accept_handler=self.handle_input,
            read_only=False,
            completer=CommandCompleter(),
            complete_while_typing=True,
        )

        # Create conversation buffer - keep it simple
        self.conversation_text = f"🚀 Enhanced AbstractMemory TUI\n📦 Model: {self.model}\n🧠 Memory: {self.memory_path}\n\nType your message below or use commands like /help\n\n"
        self.conversation_buffer = Buffer(
            multiline=True,
            read_only=True,
        )

        # Create side panel buffer
        self.side_panel_buffer = Buffer(
            multiline=True,
            read_only=False,
        )
        self.side_panel_buffer.text = "📋 Control Panel\n\n⚡ Status: Ready\n🔧 Tools: Available\n💭 Memory: Active\n\nPress F2 to toggle this panel"
        self.side_panel_buffer.read_only = True

        # Key bindings - MINIMAL AND PROVEN TO WORK
        self.kb = KeyBindings()

        @self.kb.add('c-q')
        def quit_app(event):
            """Quit with Ctrl+Q"""
            event.app.exit()

        @self.kb.add('f2')
        def toggle_side_panel(event):
            """Toggle side panel with F2"""
            self.toggle_side_panel()

        # Layout components
        conversation_window = Window(
            content=BufferControl(buffer=self.conversation_buffer),
            wrap_lines=True,
        )

        side_panel_window = Window(
            content=BufferControl(buffer=self.side_panel_buffer),
            width=25,
        )

        # Create main content (with optional side panel)
        self.show_side_panel = True
        self.main_content = VSplit([
            conversation_window,
            side_panel_window,
        ])

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
            content=FormattedTextControl(
                text=HTML("Press <b>Enter</b> to send | <b>F2</b> toggle panel | <b>Ctrl+Q</b> to quit | Type <b>/help</b> for commands")
            ),
            height=1,
        )

        # Root container
        root_container = HSplit([
            self.main_content,  # Top: conversation + side panel
            input_area,         # Middle: input
            help_bar,          # Bottom: help
        ])

        self.layout = Layout(root_container)

        # Application with working settings
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=Style.from_dict({
                'input': '#ffffff',
                'conversation': '#cccccc',
                'side-panel': '#e6e6e6',
            }),
            full_screen=True,
            mouse_support=False,  # Keep disabled to avoid complications
        )

    def toggle_side_panel(self):
        """Toggle side panel visibility."""
        if self.show_side_panel:
            # Hide side panel - show only conversation
            self.main_content.children = [self.main_content.children[0]]  # Keep only conversation
            self.show_side_panel = False
            self.add_system_message("Side panel hidden. Press F2 to show.")
        else:
            # Show side panel - add it back
            conversation_window = self.main_content.children[0]
            side_panel_window = Window(
                content=BufferControl(buffer=self.side_panel_buffer),
                width=25,
            )
            self.main_content.children = [conversation_window, side_panel_window]
            self.show_side_panel = True
            self.add_system_message("Side panel shown. Press F2 to hide.")

        self.app.invalidate()

    def handle_input(self, buffer):
        """Handle when user submits input."""
        user_input = buffer.text.strip()
        if not user_input:
            return

        # Handle commands
        if user_input.startswith('/'):
            self.handle_command(user_input)
            buffer.reset()
            return

        # Add user message
        self.add_message("User", user_input)

        # For now, simple echo - can be replaced with actual agent call
        if self.agent_session:
            self.add_message("Assistant", "Agent integration will be added here")
        else:
            self.add_message("Assistant", f"Echo: {user_input} (Agent not connected)")

        # Clear input
        buffer.reset()

    def handle_command(self, command):
        """Handle slash commands."""
        parts = command.lower().split()
        cmd = parts[0]

        if cmd in ['/quit', '/exit']:
            self.app.exit()
        elif cmd == '/help':
            help_text = """Available commands:
/help - Show this help
/status - Show current status
/memory - Show memory information
/tools - Show available tools
/clear - Clear conversation
/quit - Exit application

You can also type regular messages to chat with the AI assistant."""
            self.add_system_message(help_text)
        elif cmd == '/clear':
            self.clear_conversation()
        elif cmd == '/status':
            status = f"Model: {self.model}\nMemory: {self.memory_path}\nAgent: {'Connected' if self.agent_session else 'Not connected'}\nSide panel: {'Visible' if self.show_side_panel else 'Hidden'}"
            self.add_system_message(status)
        elif cmd == '/memory':
            self.add_system_message("Memory information would be displayed here")
        elif cmd == '/tools':
            self.add_system_message("Available tools would be listed here")
        else:
            self.add_system_message(f"Unknown command: {cmd}. Type /help for available commands.")

    def add_message(self, sender, message):
        """Add a message to the conversation."""
        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")

        if sender == "User":
            formatted_message = f"[{timestamp}] 👤 {sender}: {message}\n"
        elif sender == "Assistant":
            formatted_message = f"[{timestamp}] 🤖 {sender}: {message}\n"
        else:
            formatted_message = f"[{timestamp}] {sender}: {message}\n"

        self._append_to_conversation(formatted_message)

    def add_system_message(self, message):
        """Add a system message to the conversation."""
        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] ℹ️  System: {message}\n"
        self._append_to_conversation(formatted_message)

    def _append_to_conversation(self, text):
        """Append text to conversation buffer."""
        # Update our text storage
        self.conversation_text += text

        # Recreate the buffer content (this works reliably)
        self.conversation_buffer = Buffer(
            multiline=True,
            read_only=True,
        )
        # Set the text after creating the buffer
        self._set_buffer_text(self.conversation_buffer, self.conversation_text)

    def _set_buffer_text(self, buffer, text):
        """Safely set buffer text."""
        # For read-only buffers, we need to temporarily make them writable
        was_readonly = buffer.read_only
        buffer.read_only = False
        try:
            buffer.text = text
            buffer.cursor_position = len(text)
        except:
            # If there's still an issue, ignore it - this is fallback behavior
            pass
        buffer.read_only = was_readonly

    def clear_conversation(self):
        """Clear the conversation."""
        self.conversation_text = f"🚀 Enhanced AbstractMemory TUI\n📦 Model: {self.model}\n🧠 Memory: {self.memory_path}\n\nConversation cleared.\n\n"
        self._set_buffer_text(self.conversation_buffer, self.conversation_text)

    def init_agent(self):
        """Initialize the AbstractMemory agent (mock for now)."""
        try:
            # This would be replaced with actual agent initialization
            # For now, just mark as "connected"
            self.agent_session = True
            self.add_system_message("Agent initialized successfully!")
            return True
        except Exception as e:
            self.add_system_message(f"Agent initialization failed: {e}")
            return False

    async def run(self):
        """Run the TUI application."""
        # Set initial focus to input
        self.app.layout.focus(self.input_buffer)

        # Initialize agent in background
        if self.init_agent():
            self.add_system_message("Ready for conversation!")
        else:
            self.add_system_message("Running in limited mode (no agent)")

        # Run the app
        await self.app.run_async()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Enhanced AbstractMemory TUI")
    parser.add_argument('--model', default='qwen3-coder:30b', help='LLM model to use')
    parser.add_argument('--memory-path', default='./agent_memory', help='Path to agent memory')
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    print("🚀 Starting Enhanced AbstractMemory TUI...")
    print(f"📦 Model: {args.model}")
    print(f"🧠 Memory: {args.memory_path}")
    print("✨ Features: Working text input, side panel, commands")
    print()

    tui = EnhancedTUI(model=args.model, memory_path=args.memory_path)
    asyncio.run(tui.run())


if __name__ == "__main__":
    main()