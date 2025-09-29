#!/usr/bin/env python3
"""
Enhanced AbstractMemory TUI - Based on working simple version
Focuses on text input working first, then adds features
"""

import asyncio
import concurrent.futures
import sys
import os
import argparse
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import subprocess
import threading

# Force offline mode for Hugging Face models (use cached models only)
# This MUST be set before any imports that might use transformers
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
# Point to the default cache directory
os.environ.setdefault('HF_HOME', os.path.expanduser('~/.cache/huggingface'))
os.environ.setdefault('SENTENCE_TRANSFORMERS_HOME', os.path.expanduser('~/.cache/huggingface'))

# Add the project root and aa-tui dir to path for local imports
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.layout.margins import ScrollbarMargin, Margin

# AbstractMemory imports
try:
    from abstractllm import create_llm
    from abstractllm.tools.common_tools import list_files
    from abstractllm.tools import tool
    from abstractmemory import MemorySession, MemoryConfig
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False
    create_llm = None
    list_files = None
    MemorySession = None
    MemoryConfig = None


@dataclass
class AgentState:
    """Track the current state of the agent for real-time display."""
    status: str = "idle"  # idle, thinking, acting, observing
    current_thought: str = ""
    current_action: str = ""
    current_observation: str = ""
    tools_available: List[str] = None
    memory_components: Dict[str, int] = None
    context_tokens: int = 0
    enhanced_tokens: int = 0
    system_prompt_tokens: int = 0
    max_tokens: int = 8192
    # Core memory tracking
    core_memories: int = 0
    core_size: int = 0
    # Additional metrics
    last_activity: Any = None
    # Embedding tracking
    embedding_model: str = None  # Model name if active
    embedding_status: str = "disabled"  # enabled, disabled, offline, error
    embedding_dim: int = 0  # Dimension of embeddings
    storage_backend: str = "markdown"  # markdown, dual

    def __post_init__(self):
        if self.tools_available is None:
            self.tools_available = []
        if self.memory_components is None:
            self.memory_components = {
                'working': 0,
                'semantic': 0,
                'episodic': 0,
                'document': 0
            }


class CommandCompleter(Completer):
    """Simple command completer."""

    def __init__(self):
        self.commands = [
            '/help', '/status', '/memory', '/tools', '/clear', '/reset', '/quit'
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

    def __init__(self, model="qwen3-coder:30b", memory_path="./agent_memory", provider="ollama"):
        self.model = model
        self.provider = provider
        self.memory_path = memory_path
        self.conversation_history = []
        self.agent_session = None
        self.agent_state = AgentState()

        # Create memory path if it doesn't exist
        Path(memory_path).mkdir(parents=True, exist_ok=True)

        # Animation state
        self.thinking_animation_running = False
        self.thinking_animation_task = None
        self.thinking_animation_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.thinking_animation_index = 0

        # Conversation tracking for separators
        self.last_message_type = None

        # Status line for current operations
        self.current_status = "Ready"

        # Ephemeral message for clipboard feedback (bottom of side panel)
        self.clipboard_feedback = ""
        self.feedback_timer = None

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components with PROVEN working input approach."""

        # Create input buffer - multiline for better input
        # Note: In multiline mode, Enter creates newline, our bindings handle send
        self.input_buffer = Buffer(
            multiline=True,  # Allow multiline input
            accept_handler=self.handle_input,  # Called on our custom bindings
            read_only=False,
            completer=CommandCompleter(),
            complete_while_typing=True,
        )

        # Start with empty conversation - info is in side panel
        initial_text = ""
        self.conversation_text = initial_text

        # Separate actual conversation history (for agent context)
        self.actual_conversation_history = []

        # Create conversation display (we'll add an internal right spacer before the scrollbar)
        conversation_textarea_raw = TextArea(
            text=initial_text,
            multiline=True,
            read_only=False,  # Not read-only so we can update programmatically
            scrollbar=True,  # Enable scrollbar
            wrap_lines=True,  # Wrap long lines
            dont_extend_height=False,  # Allow content to grow beyond window
            focusable=True,  # Allow focus for keyboard scrolling
        )
        conversation_textarea_raw.read_only = True

        # Add a small blank margin before the scrollbar for readability
        # This ensures text doesn't touch the scrollbar directly
        class BlankMargin(Margin):
            def __init__(self, width: int = 5, style: str = 'class:margin'):
                self._width = width
                self.style = style

            def get_width(self, get_ui_content):
                return self._width

            def create_margin(self, window_render_info, width, height):
                blank = ' ' * self._width
                fragments = []
                for i in range(height):
                    fragments.append((self.style, blank))
                    # Newline between rows, not after the last
                    if i < height - 1:
                        fragments.append((self.style, '\n'))
                return fragments

        # Replace the default right margins with a spacer and a scrollbar
        # Note: TextArea exposes its underlying Window via `.window`.
        conversation_textarea_raw.window.right_margins = [
            BlankMargin(width=5),
            ScrollbarMargin(display_arrows=False),
        ]

        # Use the TextArea directly (simpler than wrapping in extra containers)
        self.conversation_textarea = conversation_textarea_raw
        # Keep reference to the textarea for updates and focus helpers
        self._conversation_textarea_widget = conversation_textarea_raw

        # Create side panel as TextArea for consistency
        self.side_panel_textarea = TextArea(
            text="📋 Info\n\n⚡ Status: Ready\n🔧 Tools: Available\n💭 Memory: Active\n\nF2: toggle panel",
            multiline=True,
            read_only=False,  # Start writable so we can update it
            scrollbar=False,  # No scrollbar needed for side panel
            wrap_lines=True,
            focusable=False,  # Don't allow focus on side panel
        )
        # Make it read-only after creation
        self.side_panel_textarea.read_only = True

        # Key bindings - MINIMAL AND PROVEN TO WORK + Observability shortcuts
        self.kb = KeyBindings()
        self.detail_level = 1  # 1=clean, 2=details, 3=debug, 4=raw

        @self.kb.add('c-q')
        def quit_app(event):
            """Quit with Ctrl+Q"""
            event.app.exit()

        @self.kb.add('f2')
        def toggle_side_panel(event):
            """Toggle side panel with F2"""
            self.toggle_side_panel()

        @self.kb.add('f3')
        def toggle_details(event):
            """Toggle detail level with F3"""
            self.detail_level = 2 if self.detail_level == 1 else 1
            self.update_detail_display()

        @self.kb.add('f4')
        def debug_mode(event):
            """Toggle debug mode with F4"""
            self.detail_level = 3 if self.detail_level != 3 else 1
            self.update_detail_display()

        @self.kb.add('f5')
        def raw_mode(event):
            """Toggle raw mode with F5"""
            self.detail_level = 4 if self.detail_level != 4 else 1
            self.update_detail_display()

        # Add Tab navigation to switch focus between input and conversation
        @self.kb.add('tab')
        def focus_next(event):
            """Tab to switch focus to conversation panel"""
            # If input has focus, switch to conversation
            if event.app.layout.current_buffer == self.input_buffer:
                event.app.layout.focus(self._conversation_textarea_widget)
            else:
                # Otherwise switch to input
                event.app.layout.focus(self.input_buffer)

        @self.kb.add('s-tab')  # Shift+Tab
        def focus_previous(event):
            """Shift+Tab to switch focus back"""
            # Reverse of Tab
            if event.app.layout.current_buffer == self.input_buffer:
                event.app.layout.focus(self._conversation_textarea_widget)
            else:
                event.app.layout.focus(self.input_buffer)

        # Add explicit scrolling key bindings - these work when conversation is focused
        @self.kb.add('pageup')
        def scroll_up_page(event):
            """Scroll conversation up with PageUp"""
            # If conversation is focused OR input is empty, scroll
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                buffer = self._conversation_textarea_widget.buffer
                # Move cursor up by ~10 lines
                for _ in range(10):
                    buffer.cursor_up()
                event.app.invalidate()

        @self.kb.add('pagedown')
        def scroll_down_page(event):
            """Scroll conversation down with PageDown"""
            # If conversation is focused OR input is empty, scroll
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                buffer = self._conversation_textarea_widget.buffer
                # Move cursor down by ~10 lines
                for _ in range(10):
                    buffer.cursor_down()
                event.app.invalidate()

        @self.kb.add('c-u')
        def scroll_up_half(event):
            """Scroll up half page with Ctrl+U"""
            buffer = self._conversation_textarea_widget.buffer
            for _ in range(5):
                buffer.cursor_up()
            event.app.invalidate()

        @self.kb.add('c-d')
        def scroll_down_half(event):
            """Scroll down half page with Ctrl+D"""
            buffer = self._conversation_textarea_widget.buffer
            for _ in range(5):
                buffer.cursor_down()
            event.app.invalidate()

        # Note: Arrow keys are handled naturally by the focused buffer
        # No need to override them - they work in both input and conversation

        @self.kb.add('home')
        def scroll_to_top(event):
            """Scroll to top with Home key"""
            if event.app.layout.current_buffer != self.input_buffer:
                buffer = self._conversation_textarea_widget.buffer
                buffer.cursor_position = 0
                event.app.invalidate()

        @self.kb.add('end')
        def scroll_to_bottom(event):
            """Scroll to bottom with End key"""
            if event.app.layout.current_buffer != self.input_buffer:
                buffer = self._conversation_textarea_widget.buffer
                buffer.cursor_position = len(buffer.text)
                event.app.invalidate()

        # Escape key to return focus to input
        @self.kb.add('escape')
        def focus_input(event):
            """Escape to return focus to input field"""
            event.app.layout.focus(self.input_buffer)

        # Control+J to send message (works like Ctrl+Enter)
        @self.kb.add('c-j')
        def send_message_ctrl_j(event):
            """Send message with Ctrl+J"""
            # Only send if we have text and input buffer has focus
            if event.app.layout.current_buffer == self.input_buffer and self.input_buffer.text.strip():
                self.input_buffer.validate_and_handle()

        # Also bind Escape+Enter as alternative (works like Shift+Enter in some terminals)
        @self.kb.add('escape', 'enter')
        def send_message_alt_enter(event):
            """Send message with Alt+Enter (alternative)"""
            # Only send if we have text and input buffer has focus
            if event.app.layout.current_buffer == self.input_buffer and self.input_buffer.text.strip():
                self.input_buffer.validate_and_handle()

        # Control+M is another way to send (some terminals)
        @self.kb.add('c-m')
        def send_message_ctrl_m(event):
            """Send message with Ctrl+M (Return key)"""
            # Check if we're in the input buffer
            if event.app.layout.current_buffer == self.input_buffer:
                # If there's text and it's not multiline, send it
                text = self.input_buffer.text.strip()
                if text and '\n' not in text:
                    # Single line - send
                    self.input_buffer.validate_and_handle()
                elif text:
                    # Multiline - insert newline
                    self.input_buffer.insert_text('\n')
                # else: empty - do nothing

        @self.kb.add('c-c')
        def copy_conversation_for_sft(event):
            """Copy user query and assistant response in SFT format to clipboard with Ctrl+C"""
            if len(self.actual_conversation_history) < 2:
                return

            # Find the last user-assistant pair
            user_msg = None
            assistant_msg = None
            
            # Traverse backwards to find the most recent user-assistant pair
            for i in range(len(self.actual_conversation_history) - 1, 0, -1):
                if (self.actual_conversation_history[i]["role"] == "assistant" and 
                    self.actual_conversation_history[i-1]["role"] == "user"):
                    user_msg = self.actual_conversation_history[i-1]["content"]
                    assistant_msg = self.actual_conversation_history[i]["content"]
                    break
            
            if user_msg and assistant_msg:
                # Format for supervised fine-tuning
                sft_format = f"[INST] {user_msg} [/INST]\n{assistant_msg}"
                try:
                    subprocess.run(['pbcopy'], input=sft_format.encode('utf-8'), check=True)
                    self.set_clipboard_feedback("✅ Copied user query and assistant response in SFT format")
                except subprocess.CalledProcessError:
                    self.set_clipboard_feedback("❌ Failed to copy to clipboard")
            else:
                self.set_clipboard_feedback("⚠️ No user-assistant pair found to copy")

        # Note: Mouse wheel scrolling is handled automatically by TextArea when mouse_support=True

        # Layout components - Use TextArea for proper scrolling
        # TextArea already is a complete widget with scrolling

        # Create a narrower side panel to avoid crowding
        # Use ConditionalContainer to show/hide the side panel
        self.show_side_panel = True

        # Create condition for side panel visibility
        @Condition
        def is_side_panel_visible():
            return self.show_side_panel

        side_panel_container = ConditionalContainer(
            Window(
                content=self.side_panel_textarea.control,
                width=25,  # Reduced width to avoid crowding
            ),
            filter=is_side_panel_visible
        )

        # Create a minimal separator between conversation and side panel
        margin_spacer = ConditionalContainer(
            Window(
                content=FormattedTextControl(text="│"),  # Thin visual separator
                width=1,
                dont_extend_width=True,
                style='class:separator',  # Use separator styling
            ),
            filter=is_side_panel_visible  # Only show margin when side panel is visible
        )

        # Create main content with proper spacing between conversation and side panel
        self.main_content = VSplit([
            self.conversation_textarea,  # TextArea widget with built-in scrolling
            margin_spacer,               # Visual separator when side panel is visible
            side_panel_container,        # Conditionally visible side panel
        ])

        input_prompt = Window(
            content=FormattedTextControl(text=HTML("<b>You:</b> ")),
            width=5,
            dont_extend_width=True,
        )

        input_window = Window(
            content=BufferControl(buffer=self.input_buffer),
            height=3,  # 3 lines for multiline input with scrolling
        )

        input_area = VSplit([
            input_prompt,
            input_window,
        ])

        # Status line above input
        status_line = Window(
            content=FormattedTextControl(
                text=self.get_status_text
            ),
            height=1,
        )

        help_bar = Window(
            content=FormattedTextControl(
                text=self.get_help_text
            ),
            height=1,
        )

        # Horizontal separator line
        separator = Window(
            content=FormattedTextControl(
                text=lambda: '─' * 200  # Horizontal line
            ),
            height=1,
            style='class:separator',
        )

        # Root container
        root_container = HSplit([
            self.main_content,  # Top: conversation + side panel
            status_line,        # Status line showing current operations
            input_area,         # Middle: input (now 2 lines)
            separator,          # Horizontal line separator
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
                # ReAct pattern colors
                'user': 'cyan bold',
                'assistant': 'white bold',
                'thought': 'blue',
                'action': 'yellow bold',
                'observation': 'green',
                'system': 'ansibrightblack',  # Grey for system messages
                'error': 'red bold',
                'timestamp': 'ansibrightblack',
                'separator': 'ansibrightblack',
                'margin': 'ansibrightblack',  # Margin area styling
                # UI elements
                'thinking-animation': 'yellow',
                'status-idle': 'green',
                'status-thinking': 'yellow',
                'status-acting': 'orange',
                'status-observing': 'blue',
            }),
            full_screen=True,
            mouse_support=True,  # Enable mouse for scrolling
        )

    def toggle_side_panel(self):
        """Toggle side panel visibility."""
        # Simply toggle the flag - ConditionalContainer handles the rest
        self.show_side_panel = not self.show_side_panel
        self.app.invalidate()

    def get_status_text(self):
        """Get current status text for the status line."""
        # Color codes for status
        if self.agent_state.status == "thinking":
            char = self.thinking_animation_chars[self.thinking_animation_index % len(self.thinking_animation_chars)]
            return HTML(f'<ansibrightblack>Status:</ansibrightblack> <thinking-animation>{char}</thinking-animation> <ansibrightblack>{self.current_status}</ansibrightblack>')
        elif self.agent_state.status == "acting":
            return HTML(f'<ansibrightblack>Status:</ansibrightblack> <action>🔧 {self.current_status}</action>')
        elif self.agent_state.status == "observing":
            return HTML(f'<ansibrightblack>Status:</ansibrightblack> <observation>👁️ {self.current_status}</observation>')
        else:
            return HTML(f'<ansibrightblack>Status:</ansibrightblack> <status-idle>⚡ {self.current_status}</status-idle>')

    def get_help_text(self):
        """Get dynamic help text based on current detail level."""
        base_shortcuts = "<b>Tab</b> switch | <b>Ctrl+J</b> or <b>Alt+Enter</b> send | <b>Ctrl+Q</b> quit | <b>F2</b> panel"

        if self.detail_level == 1:
            return HTML(f"{base_shortcuts}")
        elif self.detail_level == 2:
            return HTML(f"{base_shortcuts} | <b>F3</b> simple")
        elif self.detail_level == 3:
            return HTML(f"{base_shortcuts} | <b>F4</b> exit debug")
        elif self.detail_level == 4:
            return HTML(f"{base_shortcuts} | <b>F5</b> exit raw")


    def update_detail_display(self):
        """Update the display based on current detail level."""
        self.update_side_panel_content()
        self.app.invalidate()


    async def start_thinking_animation(self):
        """Start the thinking animation."""
        if self.thinking_animation_running:
            return

        self.thinking_animation_running = True
        self.thinking_animation_task = asyncio.create_task(self._animate_thinking())

    async def stop_thinking_animation(self):
        """Stop the thinking animation."""
        self.thinking_animation_running = False
        if self.thinking_animation_task:
            self.thinking_animation_task.cancel()
            try:
                await self.thinking_animation_task
            except asyncio.CancelledError:
                pass

    async def _animate_thinking(self):
        """Animate the thinking indicator."""
        try:
            while self.thinking_animation_running:
                # Update the animation index
                self.thinking_animation_index = (self.thinking_animation_index + 1) % len(self.thinking_animation_chars)

                # Trigger UI redraw to show the new animation frame
                if hasattr(self, 'app'):
                    self.app.invalidate()

                await asyncio.sleep(0.1)  # 100ms animation speed
        except asyncio.CancelledError:
            pass

    def set_clipboard_feedback(self, message):
        """Set ephemeral feedback message at bottom of side panel"""
        self.clipboard_feedback = message
        # Schedule to clear the feedback after 3 seconds
        if self.feedback_timer:
            self.feedback_timer.cancel()
        self.feedback_timer = threading.Timer(3.0, self.clear_clipboard_feedback)
        self.feedback_timer.start()
        self.update_side_panel_content()

    def clear_clipboard_feedback(self):
        """Clear the ephemeral feedback message"""
        self.clipboard_feedback = ""
        self.update_side_panel_content()

    def update_side_panel_content(self):
        """Update side panel with current agent state and time."""
        # Get current time
        now = __import__('datetime').datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Status indicator
        status_icon = {
            "idle": "⚡",
            "thinking": "🤔",
            "acting": "🔧",
            "observing": "📋"
        }.get(self.agent_state.status, "⚡")

        # Build content with real agent information
        content_lines = [
            f"⏰ {time_str}",
            "",
            "🤖 Agent Status",
            f"{status_icon} {self.agent_state.status.title()}",
            "",
        ]

        # Show LLM & Embeddings information with enhanced UI/UX
        if self.agent_session:
            # LLM Status with better visual hierarchy
            llm_status = "✅ Connected" if self.agent_session else "⚠️ Disconnected"
            content_lines.extend([
                "🧠 AI Models",
                f"├─ LLM: {llm_status}",
                f"│  ├─ {self.model}",
                f"│  └─ {self.provider}",
            ])

            # Embeddings status with clear visual indicators
            if self.agent_state.embedding_status == "enabled":
                embed_icon = "✅"
                embed_status = "Active"
            elif self.agent_state.embedding_status == "offline":
                embed_icon = "📵"
                embed_status = "Offline"
            elif self.agent_state.embedding_status == "error":
                embed_icon = "❌"
                embed_status = "Error"
            else:
                embed_icon = "⭕"
                embed_status = "Disabled"

            content_lines.append(f"├─ Embeddings: {embed_icon} {embed_status}")

            if self.agent_state.embedding_model:
                content_lines.append(f"│  ├─ {self.agent_state.embedding_model}")
                content_lines.append(f"│  └─ {self.agent_state.embedding_dim}D vectors")
            elif self.agent_state.embedding_status == "offline":
                content_lines.append(f"│  └─ No cached model")
            else:
                content_lines.append(f"│  └─ Not available")

            # Storage backend info
            storage_icon = "🗂️" if self.agent_state.storage_backend == "dual" else "📝"
            content_lines.append(f"└─ Storage: {storage_icon} {self.agent_state.storage_backend.title()}")

            content_lines.append("")

            # Show conversation stats
            conv_count = len(self.actual_conversation_history)
            content_lines.extend([
                "💬 Conversation",
                f"Exchanges: {conv_count // 2}",
                f"Messages: {conv_count}",
                "",
            ])

            # Show memory metrics in nexus.py format
            working = self.agent_state.memory_components.get('working', 0)
            semantic = self.agent_state.memory_components.get('semantic', 0)
            episodic = self.agent_state.memory_components.get('episodic', 0)
            files = self.agent_state.memory_components.get('document', 0)
            user = self.agent_state.memory_components.get('user_profile', 0)
            total_mem = working + semantic + episodic + files + user

            content_lines.extend([
                "📊 Memory Stats",
                f"Total: {total_mem}",
                f"├─ Working: {working}",
                f"├─ Semantic: {semantic}",
                f"├─ Episodic: {episodic}",
                f"├─ Files: {files}",
                f"└─ User: {user}",
                "",
            ])

            # Show core memory if available
            if self.agent_state.core_memories > 0:
                content_lines.extend([
                    "🧠 Core Memory",
                    f"Items: {self.agent_state.core_memories}",
                    f"Size: {self.agent_state.core_size:,} b",
                    "",
                ])

            # Show token usage in nexus.py format
            ctx = self.agent_state.context_tokens
            enh = self.agent_state.enhanced_tokens
            sys_prompt = self.agent_state.system_prompt_tokens
            max_tok = self.agent_state.max_tokens
            used = ctx + sys_prompt
            percent = (used / max_tok * 100) if max_tok > 0 else 0

            content_lines.extend([
                "📈 Token Usage",
                f"Used: {used:,}/{max_tok:,} ({percent:.1f}%)",
                f"├─ Context: {ctx:,} tk",
                f"├─ Enhanced: {enh:,} tk",
                f"├─ System: {sys_prompt:,} tk",
                f"└─ Available: {max_tok - used:,} tk",
                "",
            ])

            # Show tools
            tool_count = len(self.agent_state.tools_available)
            content_lines.extend([
                "🔧 Tools Available",
                f"Count: {tool_count}",
            ])
        else:
            content_lines.extend([
                "🧠 AI Models",
                "├─ LLM: ⚠️ Not Connected",
                "├─ Embeddings: ⭕ Disabled",
                "└─ Storage: 📝 Local Only",
                "",
                "💬 Conversation",
                "Mode: Echo Only",
                "",
            ])

        # Current operation
        if self.agent_state.current_thought:
            content_lines.extend([
                "",
                "💭 Current Thought:",
                self.agent_state.current_thought[:30] + "..." if len(self.agent_state.current_thought) > 30 else self.agent_state.current_thought,
            ])

        if self.agent_state.current_action:
            content_lines.extend([
                "",
                "⚡ Current Action:",
                self.agent_state.current_action[:30] + "..." if len(self.agent_state.current_action) > 30 else self.agent_state.current_action,
            ])

        if self.detail_level >= 2:
            content_lines.extend([
                "",
                "🛠️ Active Tools:",
            ])
            for tool in self.agent_state.tools_available[:5]:  # Show first 5
                content_lines.append(f"✓ {tool}")

            if len(self.agent_state.tools_available) > 5:
                content_lines.append(f"... and {len(self.agent_state.tools_available) - 5} more")

        if self.detail_level >= 3:
            content_lines.extend([
                "",
                "🧠 Current State:",
                f"Thought: {self.agent_state.current_thought[:50]}..." if len(self.agent_state.current_thought) > 50 else f"Thought: {self.agent_state.current_thought}",
                f"Action: {self.agent_state.current_action}",
            ])

        if self.detail_level >= 4:
            content_lines.extend([
                "",
                "🔍 Raw Debug Info:",
                f"Model: {self.model}",
                f"Provider: {self.provider}",
                f"Memory Path: {self.memory_path}",
                f"Session Active: {self.agent_session is not None}",
            ])

        # Add ephemeral feedback message at bottom if present
        if self.clipboard_feedback:
            content_lines.append("")
            # Use HTML-like small tag for subtle styling
            content_lines.append(f"{self.clipboard_feedback}")

        # Update side panel TextArea (temporarily make writable)
        was_readonly = self.side_panel_textarea.read_only
        self.side_panel_textarea.read_only = False
        self.side_panel_textarea.buffer.text = "\n".join(content_lines)
        self.side_panel_textarea.read_only = was_readonly
        
        # Force application to redraw
        if hasattr(self, 'app'):
            self.app.invalidate()

    def handle_input(self, buffer):
        """Handle when user submits input."""
        user_input = buffer.text.strip()
        if not user_input:
            return

        # Immediately clear input and show user message
        buffer.reset()
        self.add_message("User", user_input)

        # Handle commands
        if user_input.startswith('/'):
            self.handle_command(user_input)
            return

        # Show immediate thinking indicator
        if self.agent_session:
            # Update status to show thinking immediately
            self.agent_state.status = "thinking"
            self.agent_state.current_thought = "Processing your request..."
            self.agent_state.current_action = ""
            self.current_status = "Agent is thinking..."
            self.update_side_panel_content()

            # Don't add system message to chat - it's shown in status line
            # Status is already shown in the status line above input

            # Start thinking animation
            asyncio.create_task(self.start_thinking_animation())

            # Schedule agent processing
            self.app.create_background_task(self._process_agent_response_with_completion(user_input))
        else:
            self.add_message("Assistant", f"Echo: {user_input} (Agent not connected)")

    def _handle_task_exception(self, task):
        """Handle exceptions from async tasks."""
        try:
            # This will raise any exception that occurred in the task
            task.result()
        except Exception as e:
            # Add error message to conversation
            self.add_system_message(f"❌ Error: {e}")
            # Reset agent status
            self.agent_state.status = "idle"
            self.agent_state.current_thought = ""
            self.agent_state.current_action = ""
            self.update_side_panel_content()

    async def _process_agent_response_with_completion(self, user_input: str):
        """Wrapper that handles thinking indicator and completion properly."""
        try:
            # Start thinking animation
            await self.start_thinking_animation()
            await self._process_agent_response(user_input)
        except Exception as e:
            # Handle any unhandled exceptions
            self.add_system_message(f"❌ Error: {e}")
        finally:
            # Stop thinking animation
            await self.stop_thinking_animation()

            # Always reset status and remove thinking indicator
            self.agent_state.status = "idle"
            self.agent_state.current_thought = ""
            self.agent_state.current_action = ""
            self.current_status = "Ready"
            self.update_side_panel_content()

    async def _process_agent_response(self, user_input: str):
        """Process user input through ReAct loop with real-time observability (non-blocking)."""
        try:
            from react_loop import ReactLoop, ReactConfig

            # Configure ReAct loop (keeps calls off the UI thread)
            config = ReactConfig(
                max_iterations=25,
                observation_display_limit=500,
                include_memory=True
            )

            # Create ReAct loop instance
            reactor = ReactLoop(self.agent_session, config)

            # Set up callbacks for live UI updates
            callbacks = {
                'on_iteration': self._on_react_iteration,
                'on_response': self._on_react_response,
                'on_action': self._on_react_action,
                'on_observation': self._on_react_observation,
                'on_final_answer': self._on_react_final_answer
            }

            # Initial status
            self.agent_state.status = "thinking"
            self.agent_state.current_thought = "Starting ReAct reasoning..."
            self.current_status = "Agent is thinking..."
            self.update_side_panel_content()

            # Process through ReAct loop (generation runs in a worker thread)
            final_answer = await reactor.process_query(user_input, callbacks)

            # If reactor could not complete, fall back to direct MemorySession.generate
            if not final_answer or final_answer.strip().startswith("I apologize"):
                self.current_status = "Fallback generation"
                self.update_side_panel_content()
                resp = self.agent_session.generate(
                    user_input,
                    user_id="tui_user",
                    include_memory=True
                )
                final_answer = getattr(resp, 'content', None) or str(resp)
                final_answer = final_answer.strip()

            # Display the final answer
            self.add_message("Assistant", final_answer)

            # Persist chat history (if BasicSession available)
            self.save_chat_history()

            # Update memory display
            self._update_memory_display()

            # Reset status
            self.agent_state.status = "idle"
            self.agent_state.current_thought = ""
            self.agent_state.current_action = ""
            self.current_status = "Ready"
            self.update_side_panel_content()

        except Exception as e:
            error_details = ""
            if self.detail_level >= 4:  # Only get traceback in raw mode
                import traceback
                error_details = traceback.format_exc()
            self.add_system_message(f"Error in ReAct processing: {e}")
            if self.detail_level >= 4:  # Show full error in raw mode
                self.add_system_message(f"Debug details: {error_details}")
            self.agent_state.status = "idle"
            self.agent_state.current_thought = ""
            self.agent_state.current_action = ""
            self.current_status = "Ready"
            self.update_side_panel_content()

    def save_chat_history(self):
        """Save chat history from BasicSession to disk (compatible with nexus)."""
        try:
            if self.agent_session and hasattr(self.agent_session, '_basic_session') and self.agent_session._basic_session:
                history_path = Path(self.memory_path) / "chat_history.json"
                history_path.parent.mkdir(parents=True, exist_ok=True)

                messages = getattr(self.agent_session._basic_session, 'messages', [])
                messages_data = []
                for msg in messages:
                    # Prefer a simple interoperable format
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        messages_data.append({
                            'role': getattr(msg, 'role'),
                            'content': getattr(msg, 'content')
                        })
                    elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                        messages_data.append({'role': msg['role'], 'content': msg['content']})
                    elif hasattr(msg, 'to_dict'):
                        try:
                            d = msg.to_dict()
                            messages_data.append({'role': d.get('role'), 'content': d.get('content', '')})
                        except Exception:
                            continue

                import json
                with open(history_path, 'w', encoding='utf-8') as f:
                    json.dump(messages_data, f, indent=2, default=str)
        except Exception:
            pass

    def load_chat_history(self):
        """Load chat history into BasicSession if available (compatible with nexus)."""
        try:
            if self.agent_session and hasattr(self.agent_session, '_basic_session') and self.agent_session._basic_session:
                history_path = Path(self.memory_path) / "chat_history.json"
                if history_path.exists():
                    import json
                    with open(history_path, 'r', encoding='utf-8') as f:
                        messages_data = json.load(f)

                    # Normalize by reconstructing messages via API instead of assigning raw dicts
                    # 1) Clear existing history but keep system message (system prompt)
                    try:
                        self.agent_session.clear_history(keep_system=True)
                    except Exception:
                        pass

                    # 2) Re-add messages using the session API to ensure proper types
                    for msg in messages_data:
                        if not isinstance(msg, dict):
                            continue
                        role = msg.get('role')
                        content = msg.get('content', '')
                        if role in ('user', 'assistant') and content:
                            try:
                                self.agent_session.add_message(role, content)
                            except Exception:
                                continue
        except Exception:
            pass

    def _on_react_iteration(self, iteration: int, max_iterations: int):
        """Callback for ReAct iteration start."""
        self.agent_state.current_thought = f"ReAct cycle {iteration}/{max_iterations}"
        self.current_status = f"Cycle {iteration}/{max_iterations}"
        self.update_side_panel_content()

    def _on_react_response(self, response: str):
        """Callback for ReAct response."""
        # Show thinking in detail mode
        if self.detail_level >= 2:
            # Extract and display thoughts
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith("Thought:"):
                    thought = line[8:].strip()
                    self.add_message("🤔 Thinking", thought)

    def _on_react_action(self, tool_name: str, tool_input: dict):
        """Callback for ReAct tool action."""
        self.agent_state.status = "acting"
        self.agent_state.current_action = f"{tool_name}"
        self.current_status = f"Running {tool_name}"
        self.update_side_panel_content()

        # Show action in detail mode
        if self.detail_level >= 2:
            params_str = ", ".join([f"{k}={v}" for k, v in tool_input.items()]) if tool_input else "no params"
            self.add_message("🔧 Action", f"{tool_name}({params_str})")

    def _on_react_observation(self, tool_result: str):
        """Callback for ReAct observation."""
        self.agent_state.status = "observing"
        self.current_status = "Observing tool results"
        self.update_side_panel_content()

        # Show observation in detail mode
        if self.detail_level >= 2:
            # Truncate long observations for display
            display_obs = tool_result
            if len(tool_result) > 200:
                display_obs = tool_result[:200] + "... (truncated)"
            self.add_message("📋 Observation", display_obs)

    def _on_react_final_answer(self, answer: str):
        """Callback for ReAct final answer."""
        self.agent_state.status = "completing"
        self.agent_state.current_thought = "Finalizing response..."
        self.current_status = "Finalizing"
        self.update_side_panel_content()

    def _get_recent_context(self, max_tokens: int = 2000) -> str:
        """Get recent conversation context limited by token count."""
        # Get actual conversation history (user/assistant exchanges only)
        if not self.actual_conversation_history:
            return ""

        # Build context from actual conversation history
        context_lines = []
        for exchange in self.actual_conversation_history[-10:]:  # Last 10 exchanges
            role = exchange["role"].title()
            content = exchange["content"]
            context_lines.append(f"{role}: {content}")

        context = "\n".join(context_lines)

        # Limit by token estimation
        max_chars = max_tokens * 4  # Rough estimation: 4 chars per token
        if len(context) > max_chars:
            # Take the last part that fits
            context = "..." + context[-max_chars:]

        return context

    def _extract_final_answer(self, response: str) -> str:
        """Extract final answer from ReAct response."""
        if "Final Answer:" in response:
            parts = response.split("Final Answer:", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return response.strip()

    def _display_react_thinking(self, react_text: str, iteration: int):
        """Display ReAct thinking process based on detail level."""
        if self.detail_level < 2:
            return

        lines = react_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("Thought:"):
                thought = line[8:].strip()
                self.add_message(f"🤔 Thinking #{iteration}", thought)
            elif line.startswith("Action:"):
                action = line[7:].strip()
                self.add_message(f"🔧 Action #{iteration}", action)
                self.agent_state.current_action = action
            elif line.startswith("Action Input:"):
                action_input = line[13:].strip()
                if self.detail_level >= 3:
                    self.add_message(f"📝 Input #{iteration}", action_input)

    def _parse_and_execute_action(self, response: str, iteration: int) -> Optional[str]:
        """Parse action from response and execute tool."""
        lines = response.split('\n')
        action_name = None
        action_input = None

        for line in lines:
            line = line.strip()
            if line.startswith("Action:"):
                action_name = line[7:].strip()
            elif line.startswith("Action Input:"):
                action_input_str = line[13:].strip()
                try:
                    # Try to parse as JSON
                    import json
                    action_input = json.loads(action_input_str)
                except:
                    # Fallback: treat as string
                    action_input = {"input": action_input_str}

        if not action_name:
            return None

        # Update status to show tool execution
        self.agent_state.status = "acting"
        self.agent_state.current_action = f"{action_name}({action_input})"
        self.update_side_panel_content()

        # Execute the tool
        observation = self._execute_tool(action_name, action_input)

        # Display observation based on detail level
        if self.detail_level >= 2:
            # Truncate long observations for display
            display_obs = observation
            if len(observation) > 200:
                display_obs = observation[:200] + "... (truncated)"
            self.add_message(f"📋 Observation #{iteration}", display_obs)

        # Update status
        self.agent_state.status = "observing"
        self.update_side_panel_content()

        return observation

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the observation."""
        try:
            # Find the tool in the session
            for tool in self.agent_session.tools:
                if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                    # Execute the tool with the provided input
                    if isinstance(tool_input, dict):
                        result = tool(**tool_input)
                    else:
                        result = tool(tool_input)
                    return str(result)

            # Tool not found
            return f"Error: Tool '{tool_name}' not found. Available tools: {[t.__name__ for t in self.agent_session.tools if hasattr(t, '__name__')]}"

        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def _update_memory_and_context(self):
        """Update memory components and context tracking."""
        # Update memory display if available
        if hasattr(self.agent_session, 'last_memory_items'):
            self._update_memory_display()

        # Update context tokens if available
        if hasattr(self.agent_session, 'last_enhanced_context'):
            # Rough token estimation: 1 token ≈ 0.75 words ≈ 4 chars
            estimated_tokens = len(self.agent_session.last_enhanced_context) // 4
            self.agent_state.context_tokens = estimated_tokens

    def _update_memory_display(self):
        """Update memory component display based on current memory state."""
        # Try multiple ways to get memory information
        memory_counts = {
            'working': 0,
            'semantic': 0,
            'episodic': 0,
            'document': 0
        }

        # Method 1: Check last_memory_items
        if hasattr(self.agent_session, 'last_memory_items') and self.agent_session.last_memory_items:
            for item in self.agent_session.last_memory_items:
                if hasattr(item, 'tier'):
                    tier = item.tier.lower()
                    if tier in memory_counts:
                        memory_counts[tier] += 1

        # Method 2: Check memory session directly
        elif hasattr(self.agent_session, 'memory') and self.agent_session.memory:
            # Try to get memory items from the memory session
            try:
                # This is a rough estimate - count actual conversation history items
                memory_counts['working'] = len(self.actual_conversation_history)

                # If we have tools, we have some memory structure
                if hasattr(self.agent_session, 'tools'):
                    memory_counts['semantic'] = len([tool for tool in self.agent_session.tools if 'memory' in str(tool).lower()])

            except Exception:
                pass

        # Method 3: Fallback - show basic activity
        else:
            if self.agent_session and len(self.actual_conversation_history) > 0:
                memory_counts['working'] = len(self.actual_conversation_history)
                memory_counts['semantic'] = 1 if self.agent_session else 0

        # Update core memory metrics if available
        if hasattr(self.agent_session, 'memory') and self.agent_session.memory:
            try:
                # Try to access core memories
                if hasattr(self.agent_session.memory, 'core_memories'):
                    self.agent_state.core_memories = len(self.agent_session.memory.core_memories)
                    # Estimate size
                    total_size = sum(len(str(m)) for m in self.agent_session.memory.core_memories)
                    self.agent_state.core_size = total_size
            except:
                pass

        self.agent_state.memory_components = memory_counts

        # Update token metrics
        self._update_token_metrics()

        self.update_side_panel_content()

    def _update_token_metrics(self):
        """Update token usage metrics."""
        # Estimate tokens (1 token ≈ 4 chars)
        if self.agent_session:
            # Context tokens from conversation
            context_text = "\n".join([f"{m['role']}: {m['content']}" for m in self.actual_conversation_history[-10:]])  # Last 10 messages
            self.agent_state.context_tokens = len(context_text) // 4

            # System prompt tokens
            if hasattr(self.agent_session, 'system_prompt'):
                self.agent_state.system_prompt_tokens = len(self.agent_session.system_prompt) // 4
            elif hasattr(self.agent_session, 'agent') and hasattr(self.agent_session.agent, 'system_prompt'):
                self.agent_state.system_prompt_tokens = len(self.agent_session.agent.system_prompt) // 4

            # Enhanced tokens (if memory was injected)
            if hasattr(self.agent_session, 'last_enhanced_context'):
                self.agent_state.enhanced_tokens = len(self.agent_session.last_enhanced_context) // 4
            elif self.agent_state.context_tokens > 0:
                # Estimate enhanced as context + some memory
                self.agent_state.enhanced_tokens = int(self.agent_state.context_tokens * 1.2)

            # Max tokens
            if hasattr(self.agent_session, 'model_max_tokens'):
                self.agent_state.max_tokens = self.agent_session.model_max_tokens
            elif hasattr(self.agent_session, 'agent') and hasattr(self.agent_session.agent, 'max_tokens'):
                self.agent_state.max_tokens = self.agent_session.agent.max_tokens
            else:
                # Default based on model
                if 'gpt-4' in self.model.lower():
                    self.agent_state.max_tokens = 128000
                elif 'claude' in self.model.lower():
                    self.agent_state.max_tokens = 200000
                else:
                    self.agent_state.max_tokens = 8192

            # todo : fix logic above; we have abstractcore.architecture who normally detect that
            self.agent_state.max_tokens = 80000

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
/reset - Reset all memory (conversation + stored memory)
/quit - Exit application

You can also type regular messages to chat with the AI assistant."""
            # Show help in a temporary popup or just in conversation
            # Use dimmed color for help text
            DIM = '\033[2m'
            RESET = '\033[0m'
            formatted_help = f'{DIM}{help_text}{RESET}\n'
            self._append_to_conversation(formatted_help)
        elif cmd == '/clear':
            self.clear_conversation()
        elif cmd == '/status':
            status = f"Model: {self.model}\nMemory: {self.memory_path}\nAgent: {'Connected' if self.agent_session else 'Not connected'}\nSide panel: {'Visible' if self.show_side_panel else 'Hidden'}"
            # Show status in dimmed text
            DIM = '\033[2m'
            RESET = '\033[0m'
            formatted_status = f'{DIM}{status}{RESET}\n'
            self._append_to_conversation(formatted_status)
        elif cmd == '/memory':
            self.add_system_message("Memory information would be displayed here")
        elif cmd == '/tools':
            self.add_system_message("Available tools would be listed here")
        elif cmd == '/reset':
            self.reset_memory()
        else:
            self.add_system_message(f"Unknown command: {cmd}. Type /help for available commands.")

    def add_message(self, sender, message):
        """Add a message to the conversation."""
        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")

        # Store timestamp for side panel display
        self.agent_state.last_activity = __import__('datetime').datetime.now()

        # Format messages with clear labels (TextArea doesn't support colors)
        if sender == "User":
            # Add spacing between conversations
            spacing = "\n" if self.last_message_type == "Assistant" else ""
            formatted_message = f'{spacing}You: {message}\n'
            # Track actual conversation history
            self.actual_conversation_history.append({"role": "user", "content": message, "timestamp": timestamp})
            self.last_message_type = "User"
        elif sender == "Assistant":
            formatted_message = f'Assistant: {message}\n\n'
            # Track actual conversation history
            self.actual_conversation_history.append({"role": "assistant", "content": message, "timestamp": timestamp})
            self.last_message_type = "Assistant"
        elif sender.startswith("🔧 Action"):
            formatted_message = f'Action: {message}\n'
            self.last_message_type = "Action"
        elif sender.startswith("📋 Observation"):
            formatted_message = f'Result: {message}\n'
            self.last_message_type = "Observation"
        else:
            formatted_message = f'{sender}: {message}\n'
            self.last_message_type = "Other"

        self._append_to_conversation(formatted_message)

    def add_system_message(self, message):
        """Add a system message to the conversation (lightweight for observability)."""
        formatted_message = f"⚙️ System: {message}\n"
        self._append_to_conversation(formatted_message)

    def _append_to_conversation(self, text):
        """Append text to conversation TextArea with right padding to prevent crowding."""
        # Update our text storage
        self.conversation_text += text

        # The text now has built-in padding from the layout structure
        padded_text = self.conversation_text

        # Temporarily make TextArea writable to update it
        was_readonly = self._conversation_textarea_widget.read_only
        self._conversation_textarea_widget.read_only = False

        # Update the TextArea text
        self._conversation_textarea_widget.buffer.text = padded_text

        # Move cursor to end for auto-scroll
        self._conversation_textarea_widget.buffer.cursor_position = len(padded_text)

        # Restore read-only state
        self._conversation_textarea_widget.read_only = was_readonly

        # Force application to redraw
        if hasattr(self, 'app'):
            self.app.invalidate()


    def _set_buffer_text(self, buffer, text):
        """Set buffer text for buffers."""
        # Update buffer text
        buffer.document = buffer.document.insert_after(text)
        buffer.cursor_position = len(buffer.text)

    def clear_conversation(self):
        """Clear the conversation."""
        self.conversation_text = "Conversation cleared.\n\n"
        self.actual_conversation_history = []  # Also clear the actual conversation history
        self.last_message_type = None  # Reset message type tracking

        # Temporarily make writable
        was_readonly = self._conversation_textarea_widget.read_only
        self._conversation_textarea_widget.read_only = False
        self._conversation_textarea_widget.buffer.text = self.conversation_text
        self._conversation_textarea_widget.read_only = was_readonly

        if hasattr(self, 'app'):
            self.app.invalidate()

    def reset_memory(self):
        """Reset all memory - conversation, agent memory, and storage files."""
        import shutil
        from pathlib import Path

        try:
            # Show reset confirmation message
            self._append_to_conversation("🔄 Resetting all memory...\n")

            # 1. Clear conversation history
            self.conversation_text = "Memory reset completed.\n\n"
            self.actual_conversation_history = []
            self.last_message_type = None

            # 2. Reset agent session memory if available
            if self.agent_session:
                try:
                    # Clear conversation history in MemorySession
                    if hasattr(self.agent_session, 'clear_history'):
                        self.agent_session.clear_history(keep_system=True)
                        self._append_to_conversation("✅ MemorySession conversation history cleared\n")

                    # Clear memory components if available
                    if hasattr(self.agent_session, 'memory'):
                        memory = self.agent_session.memory

                        # Clear all memory components by accessing their internal data structures
                        if hasattr(memory, 'working') and memory.working:
                            if hasattr(memory.working, 'items'):
                                memory.working.items.clear()  # Clear the deque

                        if hasattr(memory, 'semantic') and memory.semantic:
                            if hasattr(memory.semantic, 'facts'):
                                memory.semantic.facts.clear()  # Clear the facts dict
                            if hasattr(memory.semantic, 'embeddings'):
                                memory.semantic.embeddings.clear()  # Clear embeddings if they exist

                        if hasattr(memory, 'episodic') and memory.episodic:
                            if hasattr(memory.episodic, 'episodes'):
                                memory.episodic.episodes.clear()  # Clear episodes list

                        if hasattr(memory, 'document') and memory.document:
                            if hasattr(memory.document, 'documents'):
                                memory.document.documents.clear()  # Clear documents dict
                            if hasattr(memory.document, 'chunks'):
                                memory.document.chunks.clear()  # Clear chunks dict

                        if hasattr(memory, 'core') and memory.core:
                            if hasattr(memory.core, 'blocks'):
                                memory.core.blocks.clear()  # Clear core memory blocks

                        # Clear user profiles and patterns
                        if hasattr(memory, 'user_profiles'):
                            memory.user_profiles.clear()
                        if hasattr(memory, 'failure_patterns'):
                            memory.failure_patterns.clear()
                        if hasattr(memory, 'success_patterns'):
                            memory.success_patterns.clear()

                        # Clear knowledge graph if available
                        if hasattr(memory, 'kg') and memory.kg:
                            if hasattr(memory.kg, 'facts'):
                                memory.kg.facts.clear()  # Clear KG facts
                            if hasattr(memory.kg, 'relationships'):
                                memory.kg.relationships.clear()  # Clear relationships

                        self._append_to_conversation("✅ Agent memory components cleared\n")

                except Exception as e:
                    self._append_to_conversation(f"⚠️ Warning: Could not clear agent memory: {e}\n")

            # 3. Clear storage backends (LanceDB and markdown files)
            storage_paths = []

            # Get configured memory path (default or from arguments)
            if hasattr(self, 'memory_path') and self.memory_path:
                storage_paths.append(Path(self.memory_path))

            # Get storage paths from agent session configuration
            if self.agent_session and hasattr(self.agent_session, 'storage_config'):
                storage_config = self.agent_session.storage_config
                if 'path' in storage_config and storage_config['path']:
                    storage_paths.append(Path(storage_config['path']))
                if 'uri' in storage_config and storage_config['uri']:
                    # LanceDB URI might be a file path like "./memory.db"
                    uri_path = Path(storage_config['uri'])
                    if not uri_path.is_absolute():
                        # Make relative to current directory
                        uri_path = Path.cwd() / uri_path
                    storage_paths.append(uri_path)

            # Add default paths that might exist
            default_paths = [
                Path("./memory.db"),
                Path("./agent_memory"),
                Path("./memory"),
            ]
            storage_paths.extend(default_paths)

            # Remove duplicates while preserving order
            seen = set()
            unique_paths = []
            for path in storage_paths:
                resolved_path = path.resolve()
                if resolved_path not in seen:
                    seen.add(resolved_path)
                    unique_paths.append(path)

            # Clear storage paths
            cleared_paths = []
            for storage_path in unique_paths:
                try:
                    if storage_path.exists():
                        if storage_path.is_dir():
                            shutil.rmtree(storage_path)
                            cleared_paths.append(str(storage_path))
                        elif storage_path.is_file():
                            storage_path.unlink()
                            cleared_paths.append(str(storage_path))
                except Exception as e:
                    self._append_to_conversation(f"⚠️ Warning: Could not clear {storage_path}: {e}\n")

            if cleared_paths:
                self._append_to_conversation(f"✅ Cleared storage: {', '.join(cleared_paths)}\n")
            else:
                self._append_to_conversation("ℹ️ No storage files found to clear\n")

            # 4. Recreate memory path if needed
            if hasattr(self, 'memory_path') and self.memory_path:
                Path(self.memory_path).mkdir(parents=True, exist_ok=True)

            # 5. Reset agent state
            if hasattr(self, 'agent_state'):
                self.agent_state.memory_components = {
                    'working': 0,
                    'semantic': 0,
                    'episodic': 0,
                    'document': 0
                }
                self.agent_state.core_memories = 0
                self.agent_state.core_size = 0
                self.agent_state.context_tokens = 0
                self.agent_state.enhanced_tokens = 0

            # 6. Update UI
            was_readonly = self.conversation_textarea.read_only
            self.conversation_textarea.read_only = False
            self.conversation_textarea.buffer.text = self.conversation_text
            self.conversation_textarea.read_only = was_readonly

            # Update side panel
            self.update_side_panel_content()

            if hasattr(self, 'app'):
                self.app.invalidate()

            self._append_to_conversation("🎉 Memory reset complete! Fresh start ready.\n")

        except Exception as e:
            error_msg = f"❌ Error during memory reset: {e}\n"
            self._append_to_conversation(error_msg)
            # Still try to update UI even if reset failed
            if hasattr(self, 'app'):
                self.app.invalidate()

    def setup_memory_tools(self) -> list:
        """Create memory manipulation tools for the agent."""
        if not ABSTRACTCORE_AVAILABLE:
            return []

        memory_tools = []

        if not tool:
            return []

        @tool
        def search_agent_memory(query: str, limit: int = 5) -> str:
            """Search the agent's persistent memory for stored information and facts."""
            if not self.agent_session or not hasattr(self.agent_session, 'memory'):
                return "FAILURE: Memory system not available."

            try:
                results = self.agent_session.search_memory(query, limit=limit)
                if results and any(result.get('content') for result in results):
                    formatted = []
                    for result in results:
                        content = result.get('content', '').strip()
                        if content:
                            formatted.append(f"- {content}")

                    if formatted:
                        return f"Memory search results for '{query}':\n" + "\n".join(formatted)
                    else:
                        return f"No relevant memories found for '{query}'"
                else:
                    return f"No memories found for '{query}'"
            except Exception as e:
                return f"Memory search failed: {e}"

        @tool
        def remember_important_fact(fact: str) -> str:
            """Store an important fact or information in persistent memory for future recall."""
            if not self.agent_session:
                return "FAILURE: Memory system not initialized."

            try:
                self.agent_session.learn_about_user(fact)
                return f"SUCCESS: Fact stored in memory.\nStored: {fact}"
            except Exception as e:
                return f"FAILURE: Could not store fact.\nReason: {e}"

        @tool
        def get_memory_context(topic: str) -> str:
            """Get relevant memory context and background information about a specific topic."""
            if not self.agent_session:
                return "FAILURE: Memory system not available."

            try:
                context = self.agent_session.get_memory_context(topic)
                return f"Memory context for '{topic}':\n{context}"
            except Exception as e:
                return f"Failed to get memory context: {e}"

        @tool
        def get_semantic_facts(limit: int = 10) -> str:
            """Retrieve validated semantic facts and knowledge from the agent's long-term memory."""
            if not self.agent_session or not hasattr(self.agent_session, 'memory'):
                return "FAILURE: Memory system not available."

            try:
                if hasattr(self.agent_session.memory, 'semantic') and hasattr(self.agent_session.memory.semantic, 'facts'):
                    facts = self.agent_session.memory.semantic.facts
                    if not facts:
                        return "No semantic facts stored yet"

                    result = [f"Found {len(facts)} semantic facts:"]
                    for i, (_, fact_data) in enumerate(list(facts.items())[:limit]):
                        content = fact_data.get('content', 'No content')
                        confidence = fact_data.get('confidence', 0.0)
                        result.append(f"  {i+1}. {content} (confidence: {confidence:.2f})")

                    return "\n".join(result)
                else:
                    return "Semantic memory component not available"
            except Exception as e:
                return f"Failed to get semantic facts: {e}"

        memory_tools.extend([
            search_agent_memory,
            remember_important_fact,
            get_memory_context,
            get_semantic_facts
        ])

        return memory_tools

    def create_memory_aware_read_file(self, session):
        """Create a memory-aware read_file tool similar to nexus.py"""
        @tool
        def read_file(filename: str) -> str:
            """Read a file and automatically remember its contents for future reference.

            Args:
                filename: Path to the file to read

            Returns:
                The contents of the file
            """
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    contents = f.read()

                # Store in document memory for future reference
                if hasattr(session, 'memory'):
                    session.memory.store_document(
                        title=f"File: {filename}",
                        content=contents,
                        metadata={"type": "file", "path": filename}
                    )

                return contents
            except Exception as e:
                return f"Error reading file {filename}: {e}"

        return read_file

    def init_agent(self):
        """Initialize the real AbstractMemory agent."""
        try:
            if not ABSTRACTCORE_AVAILABLE:
                self.add_system_message("AbstractCore not available. Install abstractllm and abstractmemory packages.")
                return False

            self.add_system_message("🔄 Initializing AbstractMemory agent...")

            # Create LLM provider with extended timeout for long conversations - exactly like nexus.py
            self.add_system_message(f"📡 Connecting to {self.provider} with {self.model}...")
            provider = create_llm(self.provider, model=self.model, timeout=7200.0)
            self.add_system_message("✅ LLM connection established")

            # Configure memory - offline-first approach for embeddings
            memory_config = MemoryConfig.agent_mode()  # Use agent_mode like nexus.py
            memory_config.enable_memory_tools = True
            memory_config.enable_self_editing = True

            # Check embeddings availability based on offline mode
            if os.environ.get('TRANSFORMERS_OFFLINE') == '1':
                # In offline mode, check if model is cached
                cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                model_cached = False
                if os.path.exists(cache_dir):
                    # Check for common embedding model in cache
                    for item in os.listdir(cache_dir):
                        if 'all-MiniLM-L6-v2' in item or 'sentence-transformers' in item:
                            model_cached = True
                            # Determine the actual model name
                            if 'all-MiniLM-L6-v2' in item:
                                self.agent_state.embedding_model = "all-MiniLM-L6-v2"
                                self.agent_state.embedding_dim = 384
                            elif 'all-mpnet-base-v2' in item:
                                self.agent_state.embedding_model = "all-mpnet-base-v2"
                                self.agent_state.embedding_dim = 768
                            break

                if not model_cached:
                    self.add_system_message("⚠️ Embedding model not cached - disabling semantic features")
                    memory_config.semantic_threshold = 999  # Effectively disable semantic memory
                    self.agent_state.embedding_status = "offline"
                    self.agent_state.embedding_model = None
                else:
                    self.add_system_message("✅ Using cached embedding model for semantic features")
                    self.agent_state.embedding_status = "enabled"
            else:
                # Online mode - embeddings should be available but check cache first
                cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                if os.path.exists(cache_dir):
                    for item in os.listdir(cache_dir):
                        if 'all-MiniLM-L6-v2' in item:
                            self.agent_state.embedding_model = "all-MiniLM-L6-v2"
                            self.agent_state.embedding_dim = 384
                            break
                        elif 'all-mpnet-base-v2' in item:
                            self.agent_state.embedding_model = "all-mpnet-base-v2"
                            self.agent_state.embedding_dim = 768
                            break

                if not self.agent_state.embedding_model:
                    # Will try to download if online
                    self.agent_state.embedding_model = "all-MiniLM-L6-v2"
                    self.agent_state.embedding_dim = 384

                self.agent_state.embedding_status = "enabled"
                self.add_system_message("✅ Embeddings enabled (online mode)")

            # Create tools list
            tools = []

            # Add basic file system tools
            if list_files:
                tools.append(list_files)

            # Add read_file tool that also stores content into document memory
            if tool:
                @tool
                def read_file(file_path: str) -> str:
                    """Read a file and store its contents in document memory for recall."""
                    try:
                        try:
                            from abstractllm.tools.common_tools import read_file as original_read_file
                        except Exception:
                            original_read_file = None

                        if original_read_file:
                            content = original_read_file(file_path)
                        else:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()

                        # Store in document memory if available
                        try:
                            if self.agent_session and hasattr(self.agent_session, 'memory') and hasattr(self.agent_session.memory, 'document'):
                                preview = content[:50000]
                                self.agent_session.memory.document.store_document(
                                    filepath=file_path,
                                    content=preview,
                                    file_type="text"
                                )
                        except Exception as store_err:
                            return f"SUCCESS: File read (storage failed).\n{content}\nNote: Document memory store failed: {store_err}"

                        return f"SUCCESS: File read.\n{content}"
                    except Exception as e:
                        return f"Error reading file {file_path}: {e}"

                tools.append(read_file)

            # Add memory tools (like nexus.py)
            memory_tools = self.setup_memory_tools()
            tools.extend(memory_tools)
            self.add_system_message(f"🔧 Added {len(memory_tools)} memory tools")

            # Build robust storage config with absolute paths
            memory_dir = Path(self.memory_path).resolve()
            memory_dir.mkdir(parents=True, exist_ok=True)
            lancedb_uri = memory_dir / "memory.db"
            lancedb_uri.parent.mkdir(parents=True, exist_ok=True)

            # Prefer dual storage if LanceDB is available; otherwise fallback to markdown-only
            # In offline mode, we might not have embeddings, so prefer markdown
            try:
                import lancedb  # noqa: F401
                use_lancedb = True
                # Only use LanceDB if we have embeddings available
                if os.environ.get('TRANSFORMERS_OFFLINE') == '1':
                    # Check if embedding model is cached
                    cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                    if not os.path.exists(cache_dir) or not any(
                        'all-MiniLM-L6-v2' in item or 'sentence-transformers' in item
                        for item in os.listdir(cache_dir) if os.path.exists(cache_dir)
                    ):
                        use_lancedb = False
                        self.add_system_message("📝 Using markdown-only storage (no embeddings)")
            except Exception:
                use_lancedb = False

            if use_lancedb:
                storage_config = {
                    "path": str(memory_dir),
                    "storage": "dual",  # markdown + LanceDB
                    "uri": str(lancedb_uri),
                    "semantic_threshold": 1
                }
                self.agent_state.storage_backend = "dual"
            else:
                storage_config = {
                    "path": str(memory_dir),
                    "storage": "markdown",
                    "semantic_threshold": 999  # Effectively disable semantic features
                }
                self.agent_state.storage_backend = "markdown"

            # Create memory session with error handling for offline mode
            try:
                self.agent_session = MemorySession(
                    provider,
                    tools=tools,
                    memory_config=storage_config,
                    default_memory_config=memory_config,
                    system_prompt=self.get_system_prompt()
                )
            except Exception as e:
                # If initialization fails due to embeddings, retry with markdown-only
                if "huggingface" in str(e).lower() or "sentence" in str(e).lower() or "embedding" in str(e).lower():
                    self.add_system_message("⚠️ Embeddings initialization failed, retrying with markdown-only storage")
                    storage_config = {
                        "path": str(memory_dir),
                        "storage": "markdown",
                        "semantic_threshold": 999
                    }
                    memory_config.semantic_threshold = 999

                    # Update agent state to reflect fallback
                    self.agent_state.embedding_status = "error"
                    self.agent_state.embedding_model = None
                    self.agent_state.storage_backend = "markdown"

                    self.agent_session = MemorySession(
                        provider,
                        tools=tools,
                        memory_config=storage_config,
                        default_memory_config=memory_config,
                        system_prompt=self.get_system_prompt()
                    )
                else:
                    raise

            # Set agent identity and values - using pattern from nexus.py
            if hasattr(self.agent_session, 'memory') and hasattr(self.agent_session.memory, 'set_core_values'):
                agent_values = {
                    'purpose': 'serve as enhanced TUI assistant with memory',
                    'approach': 'interactive and helpful',
                    'lens': 'ui_focused_thinking',
                    'domain': 'tui_agent'
                }
                self.agent_session.memory.set_core_values(agent_values)
                self.add_system_message("🤖 Agent identity and values configured")

            # Attempt to load existing memory state from storage (non-fatal if empty)
            try:
                if hasattr(self.agent_session, 'memory') and hasattr(self.agent_session.memory, 'load_from_storage'):
                    self.agent_session.memory.load_from_storage()
            except Exception as e:
                # Avoid hard failure on corrupted or missing LanceDB files. We'll continue with markdown-only content.
                self.add_system_message(f"⚠️ Memory load warning: {e}")

            # Update agent state
            self.agent_state.tools_available = [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in self.agent_session.tools]
            self.agent_state.status = "idle"

            self.add_system_message(f"🔧 Added {len(self.agent_session.tools)} tools")
            self.add_system_message("🧠 Memory system configured")
            self.add_system_message("Agent initialized successfully!")

            # Initialize memory display
            self._update_memory_display()

            # Update side panel
            self.update_side_panel_content()

            # Load previous chat history if available
            self.load_chat_history()

            return True

        except Exception as e:
            error_msg = f"Agent initialization failed: {e}"
            self.add_system_message(error_msg)
            self.add_system_message("Running in limited mode")
            # Still update the UI
            self.update_side_panel_content()
            return False

    def get_system_prompt(self) -> str:
        """Get the system prompt for the autonomous agent."""
        return f"""You are Nexus, an AI assistant with persistent memory and identity.

## CRITICAL: Iterative ReAct Format ##
You are part of an iterative ReAct loop. In each iteration, you should:

1. If you need to use a tool, respond with:
Thought: [what you're thinking]
Action: [exact tool name]
Action Input: {{"parameter": "value"}}

2. If you can answer directly, respond with:
Final Answer: [your complete response]

## Available Tools:
You have access to these tools (use exact names):
- list_files: Find and list files by names/paths using patterns
- read_file: Read file contents with automatic document memory storage
- search_agent_memory: Search persistent memory for stored information
- remember_important_fact: Store important facts in persistent memory
- get_memory_context: Get relevant background context about topics
- get_semantic_facts: Retrieve validated facts from long-term memory

## Important Notes:
- Use JSON format for Action Input: {{"parameter": "value"}}
- You will receive real tool results as "Observation:"
- Continue reasoning until you can provide a Final Answer
- Keep each iteration focused - don't try to do everything at once

## Example Flow:
Thought: I need to check what files are available first.
Action: list_files
Action Input: {{"directory_path": "."}}

[System will execute tool and provide real Observation]

Thought: Now I can read the specific file I found.
Action: read_file
Action Input: {{"filename": "example.txt"}}

[System will execute tool and provide real Observation]

Thought: Based on the file contents, I now have the information to answer the user's question.
Final Answer: [Write naturally and experientially about what you accomplished and learned. Reflect on the experience, insights gained, and how it changed your understanding. Use "I discovered...", "I realized...", "What struck me was...", "This experience taught me..." - be authentic and reflective, not mechanical.]

## CRITICAL: Final Answer Rules:
- Write in natural, experiential, self-reflective language
- Use phrases like "I discovered...", "I realized...", "What struck me was...", "This experience taught me..."
- Reflect authentically on what you learned and how it changed your understanding
- NEVER copy-paste raw tool results verbatim into Final Answer
- NEVER use mechanical bullet points or step-by-step lists
- Be comprehensive but natural - tell the story of your learning journey
- Show genuine insight and self-awareness about the experience"""

    async def run(self):
        """Run the TUI application."""
        # Set initial focus to input
        self.app.layout.focus(self.input_buffer)

        # Initialize agent in background
        if self.init_agent():
            self.add_system_message("Ready for conversation!\n")
        else:
            self.add_system_message("Running in limited mode (no agent)")

        # Run the app
        await self.app.run_async()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Enhanced AbstractMemory TUI")
    parser.add_argument('--model', default='qwen3-coder:30b', help='LLM model to use')
    parser.add_argument('--provider', default='ollama', help='LLM provider (ollama, openai, etc.)')
    parser.add_argument('--memory-path', default='./agent_memory', help='Path to agent memory')
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    print("🚀 Starting Enhanced AbstractMemory TUI...")
    print(f"📦 Model: {args.model}")
    print(f"🔗 Provider: {args.provider}")
    print(f"🧠 Memory: {args.memory_path}")
    print("✨ Features: Real agent integration, observability, progressive disclosure")
    print()

    tui = EnhancedTUI(model=args.model, provider=args.provider, memory_path=args.memory_path)
    asyncio.run(tui.run())


if __name__ == "__main__":
    main()
