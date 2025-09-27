#!/usr/bin/env python3
"""
Modern Enhanced AbstractMemory TUI with Professional UI/UX
Clean, minimal design with proper scrolling and visual hierarchy
"""

import asyncio
import sys
import argparse
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import concurrent.futures

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, ScrollablePane, FloatContainer, Float
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.formatted_text import HTML, ANSI, merge_formatted_text, to_formatted_text
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition, has_focus

# AbstractMemory imports
try:
    from abstractllm import create_llm
    from abstractllm.tools.common_tools import list_files
    from abstractllm.tools import tool
    from abstractmemory import MemorySession, MemoryConfig
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False


@dataclass
class AgentState:
    """Track agent state for UI display."""
    status: str = "idle"  # idle, thinking, responding
    current_operation: str = ""
    model: str = ""
    provider: str = ""
    connected: bool = False
    conversation_count: int = 0
    last_activity: Optional[datetime] = None


class CommandCompleter(Completer):
    """Command completer for slash commands."""
    def __init__(self):
        self.commands = ['/help', '/clear', '/status', '/quit']

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()
        if text.startswith('/'):
            for command in self.commands:
                if command.startswith(text):
                    yield Completion(command, start_position=-len(text))


class ModernTUI:
    """Modern TUI with clean design and proper functionality."""

    def __init__(self, model="qwen3-coder:30b", memory_path="./agent_memory", provider="ollama"):
        self.model = model
        self.provider = provider
        self.memory_path = memory_path
        self.agent_session = None
        self.agent_state = AgentState(model=model, provider=provider)

        # Conversation tracking
        self.conversation_history = []  # List of (role, content) tuples
        self.formatted_conversation = []  # List of formatted text for display

        # Animation state
        self.thinking_animation_task = None
        self.animation_running = False

        # Create memory path
        Path(memory_path).mkdir(parents=True, exist_ok=True)

        self.setup_ui()

    def setup_ui(self):
        """Set up the modern UI components."""

        # Key bindings
        self.kb = KeyBindings()

        @self.kb.add('c-q')
        def quit_app(event):
            """Quit with Ctrl+Q."""
            event.app.exit()

        @self.kb.add('c-l')
        def clear_screen(event):
            """Clear screen with Ctrl+L."""
            self.clear_conversation()

        @self.kb.add('pageup')
        def scroll_up(event):
            """Scroll up in conversation."""
            if self.scrollable_pane:
                # Get the window that contains our conversation
                for window in event.app.layout.find_all_windows():
                    if hasattr(window, 'vertical_scroll'):
                        window.vertical_scroll = max(0, window.vertical_scroll - 5)
                event.app.invalidate()

        @self.kb.add('pagedown')
        def scroll_down(event):
            """Scroll down in conversation."""
            if self.scrollable_pane:
                for window in event.app.layout.find_all_windows():
                    if hasattr(window, 'vertical_scroll'):
                        # Scroll down by 5 lines
                        window.vertical_scroll = window.vertical_scroll + 5
                event.app.invalidate()

        # Create input field
        self.input_field = TextArea(
            height=1,
            prompt='▶ ',
            multiline=False,
            wrap_lines=False,
            completer=CommandCompleter(),
            complete_while_typing=True,
            accept_handler=self.handle_input,
        )

        # Create conversation display with proper scrolling
        self.conversation_control = FormattedTextControl(
            text=self.get_formatted_conversation,
            focusable=True,
        )

        self.conversation_window = Window(
            content=self.conversation_control,
            wrap_lines=True,
        )

        # Wrap in scrollable pane for proper scrolling
        self.scrollable_pane = ScrollablePane(
            self.conversation_window,
            keep_cursor_visible=True,
            show_scrollbar=True,
        )

        # Side panel for status
        self.status_window = Window(
            content=FormattedTextControl(text=self.get_status_text),
            width=35,  # Wider panel
        )

        # Status bar at bottom
        self.status_bar = Window(
            content=FormattedTextControl(text=self.get_status_bar),
            height=1,
            style='class:status-bar',
        )

        # Main layout
        main_content = VSplit([
            Frame(
                self.scrollable_pane,
                title='Conversation',
                style='class:conversation-frame',
            ),
            Frame(
                self.status_window,
                title='Status',
                style='class:status-frame',
            ),
        ])

        root_container = HSplit([
            main_content,
            self.status_bar,
            self.input_field,
        ])

        self.layout = Layout(root_container)

        # Modern style
        self.style = Style.from_dict({
            'conversation-frame': 'bg:#1a1a1a',
            'status-frame': 'bg:#1a1a1a',
            'status-bar': 'bg:#2d2d2d fg:#888888',
            'user-message': 'fg:#00d7ff bold',  # Bright cyan for user
            'assistant-message': 'fg:#ffffff bold',  # White for assistant
            'timestamp': 'fg:#666666',  # Dim gray for timestamps
            'separator': 'fg:#444444',  # Dark gray for separators
            'thinking': 'fg:#ffaf00',  # Gold for thinking
            'error': 'fg:#ff5555 bold',  # Red for errors
            'success': 'fg:#50fa7b',  # Green for success
            'info': 'fg:#8be9fd',  # Light blue for info
        })

        # Application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True,
        )

        # Initial message
        self.add_to_conversation("system", "Welcome to Enhanced AbstractMemory TUI")
        self.add_to_conversation("system", f"Model: {self.model} | Provider: {self.provider}")
        self.add_to_conversation("system", "Type /help for commands or start chatting")

    def get_formatted_conversation(self):
        """Get the formatted conversation for display."""
        if not self.formatted_conversation:
            return HTML('<dim>No messages yet...</dim>')

        # Merge all formatted text
        return merge_formatted_text(self.formatted_conversation)

    def get_status_text(self):
        """Get status panel content."""
        now = datetime.now().strftime("%H:%M:%S")

        status_icon = "⚡" if self.agent_state.status == "idle" else "⚙️"
        connection_status = "✓ Connected" if self.agent_state.connected else "✗ Not Connected"

        return HTML(f"""<b>Time:</b> {now}

<b>Agent Status</b>
{status_icon} {self.agent_state.status.title()}
{self.agent_state.current_operation}

<b>Connection</b>
{connection_status}
Model: {self.agent_state.model}
Provider: {self.agent_state.provider}

<b>Conversation</b>
Messages: {len(self.conversation_history)}
Exchanges: {len(self.conversation_history) // 2}

<b>Memory</b>
Path: {self.memory_path}
Active: {'Yes' if self.agent_session else 'No'}

<b>Controls</b>
Enter: Send message
Ctrl+L: Clear chat
Ctrl+Q: Quit
PageUp/Down: Scroll
""")

    def get_status_bar(self):
        """Get status bar content."""
        if self.agent_state.status == "thinking":
            spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(time.time() * 10) % 10]
            status = f"{spinner} Processing..."
        elif self.agent_state.current_operation:
            status = self.agent_state.current_operation
        else:
            status = "Ready"

        return HTML(f'<status-bar>{status} | Model: {self.model} | <b>Ctrl+Q</b> to quit</status-bar>')

    def add_to_conversation(self, role: str, content: str):
        """Add a message to the conversation with proper formatting."""
        # Store raw conversation
        self.conversation_history.append((role, content))

        # Format for display
        if role == "user":
            formatted = HTML(f'\n<user-message>You:</user-message> {content}\n')
        elif role == "assistant":
            formatted = HTML(f'<assistant-message>Assistant:</assistant-message> {content}\n')
        elif role == "system":
            formatted = HTML(f'<dim>{content}</dim>\n')
        else:
            formatted = HTML(f'{content}\n')

        self.formatted_conversation.append(formatted)

        # Auto-scroll to bottom
        if hasattr(self, 'app'):
            self.app.invalidate()

    def clear_conversation(self):
        """Clear the conversation history."""
        self.conversation_history = []
        self.formatted_conversation = []
        self.add_to_conversation("system", "Conversation cleared")
        if hasattr(self, 'app'):
            self.app.invalidate()

    def handle_input(self, buffer):
        """Handle user input."""
        user_input = buffer.text.strip()
        if not user_input:
            return

        # Clear the input
        buffer.reset()

        # Handle commands
        if user_input.startswith('/'):
            self.handle_command(user_input)
            return

        # Add user message
        self.add_to_conversation("user", user_input)

        # Process with agent
        if self.agent_session:
            # Update status
            self.agent_state.status = "thinking"
            self.agent_state.current_operation = "Processing your message..."

            # Process in background
            asyncio.create_task(self.process_with_agent(user_input))
        else:
            self.add_to_conversation("assistant", f"Echo: {user_input} (Agent not connected)")

    def handle_command(self, command):
        """Handle slash commands."""
        cmd = command.lower().split()[0]

        if cmd == '/quit':
            self.app.exit()
        elif cmd == '/clear':
            self.clear_conversation()
        elif cmd == '/help':
            help_text = """Available commands:
/help - Show this help
/clear - Clear conversation
/status - Show agent status
/quit - Exit application"""
            self.add_to_conversation("system", help_text)
        elif cmd == '/status':
            status = f"Agent: {'Connected' if self.agent_session else 'Not connected'}"
            self.add_to_conversation("system", status)
        else:
            self.add_to_conversation("system", f"Unknown command: {cmd}")

    async def process_with_agent(self, user_input: str):
        """Process user input with the agent."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: self.agent_session.generate(
                        user_input,
                        user_id="tui_user",
                        include_memory=True
                    )
                )

            # Extract response
            if hasattr(response, 'content'):
                agent_response = response.content.strip()
            else:
                agent_response = str(response).strip()

            # Add response
            self.add_to_conversation("assistant", agent_response)

        except Exception as e:
            self.add_to_conversation("system", f"Error: {e}")
        finally:
            # Reset status
            self.agent_state.status = "idle"
            self.agent_state.current_operation = ""
            self.app.invalidate()

    def init_agent(self):
        """Initialize the agent connection."""
        if not ABSTRACTCORE_AVAILABLE:
            self.add_to_conversation("system", "AbstractCore not available")
            return False

        try:
            # Create provider
            provider = create_llm(self.provider, model=self.model, timeout=7200.0)

            # Configure memory
            memory_config = MemoryConfig.agent_mode()
            memory_config.enable_memory_tools = True

            # Create session
            self.agent_session = MemorySession(
                provider,
                memory_config={"path": self.memory_path},
                default_memory_config=memory_config,
                system_prompt="You are a helpful AI assistant with memory capabilities."
            )

            self.agent_state.connected = True
            self.add_to_conversation("system", "✓ Agent connected successfully")
            return True

        except Exception as e:
            self.add_to_conversation("system", f"Failed to initialize agent: {e}")
            return False

    async def run(self):
        """Run the TUI application."""
        # Initialize agent in background
        self.init_agent()

        # Run the app
        await self.app.run_async()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Modern Enhanced AbstractMemory TUI')
    parser.add_argument('--model', default='qwen3-coder:30b', help='Model to use')
    parser.add_argument('--provider', default='ollama', help='Provider to use')
    parser.add_argument('--memory-path', default='./agent_memory', help='Memory path')

    args = parser.parse_args()

    tui = ModernTUI(
        model=args.model,
        provider=args.provider,
        memory_path=args.memory_path
    )

    print("🚀 Starting Modern Enhanced TUI...")
    print(f"📦 Model: {args.model}")
    print(f"🔗 Provider: {args.provider}")
    print(f"🧠 Memory: {args.memory_path}")

    asyncio.run(tui.run())


if __name__ == "__main__":
    main()