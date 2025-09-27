#!/usr/bin/env python3
"""
Enhanced AbstractMemory TUI - Based on working simple version
Focuses on text input working first, then adds features
"""

import asyncio
import concurrent.futures
import sys
import argparse
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

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
from prompt_toolkit.widgets import TextArea, Frame

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
    max_tokens: int = 8192

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

        # Initial welcome text
        initial_text = "Enhanced AbstractMemory TUI\nModel: {} | Provider: {}\nType /help for commands or start chatting\n\n".format(
            self.model, self.provider
        )
        self.conversation_text = initial_text

        # Separate actual conversation history (for agent context)
        self.actual_conversation_history = []

        # Create conversation display using TextArea widget (has built-in scrolling)
        # Make it NOT read-only so we can update it programmatically
        self.conversation_textarea = TextArea(
            text=initial_text,
            multiline=True,
            read_only=False,  # Not read-only so we can update programmatically
            scrollbar=True,  # Enable scrollbar
            wrap_lines=True,  # Wrap long lines
            dont_extend_height=False,  # Allow content to grow beyond window
            focusable=True,  # Allow focus for keyboard scrolling
        )
        # Immediately set it to read-only after creation
        self.conversation_textarea.read_only = True

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
                event.app.layout.focus(self.conversation_textarea)
            else:
                # Otherwise switch to input
                event.app.layout.focus(self.input_buffer)

        @self.kb.add('s-tab')  # Shift+Tab
        def focus_previous(event):
            """Shift+Tab to switch focus back"""
            # Reverse of Tab
            if event.app.layout.current_buffer == self.input_buffer:
                event.app.layout.focus(self.conversation_textarea)
            else:
                event.app.layout.focus(self.input_buffer)

        # Add explicit scrolling key bindings - these work when conversation is focused
        @self.kb.add('pageup')
        def scroll_up_page(event):
            """Scroll conversation up with PageUp"""
            # If conversation is focused OR input is empty, scroll
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                buffer = self.conversation_textarea.buffer
                # Move cursor up by ~10 lines
                for _ in range(10):
                    buffer.cursor_up()
                event.app.invalidate()

        @self.kb.add('pagedown')
        def scroll_down_page(event):
            """Scroll conversation down with PageDown"""
            # If conversation is focused OR input is empty, scroll
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                buffer = self.conversation_textarea.buffer
                # Move cursor down by ~10 lines
                for _ in range(10):
                    buffer.cursor_down()
                event.app.invalidate()

        @self.kb.add('c-u')
        def scroll_up_half(event):
            """Scroll up half page with Ctrl+U"""
            buffer = self.conversation_textarea.buffer
            for _ in range(5):
                buffer.cursor_up()
            event.app.invalidate()

        @self.kb.add('c-d')
        def scroll_down_half(event):
            """Scroll down half page with Ctrl+D"""
            buffer = self.conversation_textarea.buffer
            for _ in range(5):
                buffer.cursor_down()
            event.app.invalidate()

        # Arrow keys for scrolling
        @self.kb.add('up')
        def scroll_up_line(event):
            """Scroll up one line with Up arrow"""
            # Works when conversation is focused or input is empty
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                self.conversation_textarea.buffer.cursor_up()
                event.app.invalidate()

        @self.kb.add('down')
        def scroll_down_line(event):
            """Scroll down one line with Down arrow"""
            # Works when conversation is focused or input is empty
            if event.app.layout.current_buffer != self.input_buffer or not self.input_buffer.text:
                self.conversation_textarea.buffer.cursor_down()
                event.app.invalidate()

        @self.kb.add('home')
        def scroll_to_top(event):
            """Scroll to top with Home key"""
            if event.app.layout.current_buffer != self.input_buffer:
                buffer = self.conversation_textarea.buffer
                buffer.cursor_position = 0
                event.app.invalidate()

        @self.kb.add('end')
        def scroll_to_bottom(event):
            """Scroll to bottom with End key"""
            if event.app.layout.current_buffer != self.input_buffer:
                buffer = self.conversation_textarea.buffer
                buffer.cursor_position = len(buffer.text)
                event.app.invalidate()

        # Escape key to return focus to input
        @self.kb.add('escape')
        def focus_input(event):
            """Escape to return focus to input field"""
            event.app.layout.focus(self.input_buffer)

        # Layout components - Use TextArea for proper scrolling
        # TextArea already is a complete widget with scrolling

        # Create a narrower side panel to avoid crowding
        side_panel_container = Window(
            content=self.side_panel_textarea.control,
            width=25,  # Reduced width to avoid crowding
        )

        # Create main content (with optional side panel)
        self.show_side_panel = True
        self.main_content = VSplit([
            self.conversation_textarea,  # TextArea widget with built-in scrolling
            side_panel_container,
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

        # Root container
        root_container = HSplit([
            self.main_content,  # Top: conversation + side panel
            status_line,        # Status line showing current operations
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
                # UI elements
                'thinking-animation': 'yellow',
                'status-idle': 'green',
                'status-thinking': 'yellow',
                'status-acting': 'orange',
                'status-observing': 'blue',
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
            side_panel_container = Window(
                content=self.side_panel_textarea.control,
                width=25,
            )
            self.main_content.children = [self.conversation_textarea, side_panel_container]
            self.show_side_panel = True
            self.add_system_message("Side panel shown. Press F2 to hide.")

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
        base_shortcuts = "<b>Tab</b> switch focus | <b>Enter</b> send | <b>Ctrl+Q</b> quit | <b>PgUp/PgDn</b> scroll | <b>F2</b> panel"

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
                char = self.thinking_animation_chars[self.thinking_animation_index]
                # Update the thinking message in the conversation
                if "🤔 Agent is thinking..." in self.conversation_text:
                    self.conversation_text = self.conversation_text.replace(
                        "🤔 Agent is thinking...",
                        f'<thinking-animation>{char}</thinking-animation> <system>Agent is thinking...</system>'
                    )
                    if hasattr(self, 'app'):
                        self.app.invalidate()

                self.thinking_animation_index = (self.thinking_animation_index + 1) % len(self.thinking_animation_chars)
                await asyncio.sleep(0.1)  # 100ms animation speed
        except asyncio.CancelledError:
            pass

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

        # Show LLM information
        if self.agent_session:
            content_lines.extend([
                "🧠 LLM Connection",
                f"Model: {self.model}",
                f"Provider: {self.provider}",
                f"Status: Connected",
                "",
            ])

            # Show conversation stats
            conv_count = len(self.actual_conversation_history)
            content_lines.extend([
                "💬 Conversation",
                f"Exchanges: {conv_count // 2}",
                f"Messages: {conv_count}",
                "",
            ])

            # Show memory information if available
            total_memory = sum(self.agent_state.memory_components.values())
            if total_memory > 0:
                content_lines.extend([
                    "🧠 Memory Active",
                    f"Items: {total_memory}",
                    f"Path: {self.memory_path}",
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
                "🧠 LLM Connection",
                "Status: Not Connected",
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
        """Process user input through MemorySession with real-time observability."""
        try:
            # Update status
            self.agent_state.status = "thinking"
            self.agent_state.current_thought = "Processing your request..."
            self.update_side_panel_content()

            # Generate response using MemorySession (run in thread to avoid blocking UI)
            loop = asyncio.get_event_loop()

            # Run the blocking generate call in a thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: self.agent_session.generate(
                        user_input,  # Just the user input, not complex prompt
                        user_id="tui_user",
                        include_memory=True
                    )
                )

            # Extract response content
            if hasattr(response, 'content'):
                agent_response = response.content.strip()
            else:
                agent_response = str(response).strip()

            # Display the response
            self.add_message("Assistant", agent_response)
            # Don't add system message - keep chat clean

            # Update memory display with new information
            self._update_memory_display()

            # Reset status
            self.agent_state.status = "idle"
            self.agent_state.current_thought = ""
            self.agent_state.current_action = ""
            self.update_side_panel_content()

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.add_system_message(f"Error processing request: {e}")
            if self.detail_level >= 4:  # Show full error in raw mode
                self.add_system_message(f"Debug details: {error_details}")
            self.agent_state.status = "idle"
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

        self.agent_state.memory_components = memory_counts
        self.update_side_panel_content()

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

        # Store timestamp for side panel display
        self.agent_state.last_activity = __import__('datetime').datetime.now()

        # Add visual separator between conversation pairs
        separator_line = ""
        if sender == "User" and self.last_message_type == "Assistant":
            separator_line = "\n" + "─" * 60 + "\n\n"

        if sender == "User":
            formatted_message = f'{separator_line}You: {message}\n'
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
        """Add a system message to the conversation."""
        formatted_message = f'[System] {message}\n'
        self._append_to_conversation(formatted_message)

    def _append_to_conversation(self, text):
        """Append text to conversation TextArea."""
        # Update our text storage
        self.conversation_text += text

        # Temporarily make TextArea writable to update it
        was_readonly = self.conversation_textarea.read_only
        self.conversation_textarea.read_only = False

        # Update the TextArea text
        self.conversation_textarea.buffer.text = self.conversation_text

        # Move cursor to end for auto-scroll
        self.conversation_textarea.buffer.cursor_position = len(self.conversation_text)

        # Restore read-only state
        self.conversation_textarea.read_only = was_readonly

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
        was_readonly = self.conversation_textarea.read_only
        self.conversation_textarea.read_only = False
        self.conversation_textarea.buffer.text = self.conversation_text
        self.conversation_textarea.read_only = was_readonly

        if hasattr(self, 'app'):
            self.app.invalidate()

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

            # Configure memory - using working pattern from nexus.py
            memory_config = MemoryConfig.agent_mode()
            memory_config.enable_memory_tools = True
            memory_config.enable_self_editing = True

            # Create tools list
            tools = []

            # Add basic file system tools
            if list_files:
                tools.append(list_files)

            # Create the memory session - using EXACT pattern from nexus.py
            self.agent_session = MemorySession(
                provider,
                tools=tools,
                memory_config={"path": self.memory_path, "semantic_threshold": 1},  # Immediate validation
                default_memory_config=memory_config,
                system_prompt=self.get_system_prompt()
            )

            # Add memory-aware read_file tool
            read_file_tool = self.create_memory_aware_read_file(self.agent_session)
            self.agent_session.tools.append(read_file_tool)

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

            return True

        except Exception as e:
            import traceback
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

## Your Identity and Capabilities ##
- You have persistent memory across conversations
- You can read, analyze, and remember files using read_file
- You can search your memory for relevant information
- You maintain user profiles and adapt to individual preferences
- You learn from every interaction and build knowledge over time

## Response Guidelines ##
- Always be helpful and thorough
- Use your memory to provide contextual responses
- When analyzing code or files, remember key insights for future reference
- Be proactive in offering relevant information from your memory

Remember: Your memory persists across sessions, so everything you learn becomes part of your knowledge base."""

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