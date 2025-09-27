"""Input area with autocomplete and suggestions."""

from typing import Callable, Optional, List
from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.validation import Validator


class CommandCompleter(Completer):
    """Completer for commands and common patterns."""

    def __init__(self):
        self.commands = [
            '/help', '/status', '/memory', '/tools', '/debug', '/context',
            '/compact', '/scratch', '/clear', '/quit', '/exit'
        ]

        self.common_patterns = [
            'list files in',
            'read file',
            'search memory for',
            'remember that',
            'what do you know about',
            'analyze the code in',
            'explain how',
            'create a function that',
            'fix the bug in',
            'optimize the performance of'
        ]

    def get_completions(self, document, complete_event):
        """Get completions for the current document."""
        text = document.text_before_cursor.lower()

        # Command completions
        if text.startswith('/'):
            for command in self.commands:
                if command.lower().startswith(text):
                    yield Completion(
                        command,
                        start_position=-len(text),
                        display=command,
                        display_meta="command"
                    )

        # Pattern completions for regular input
        else:
            for pattern in self.common_patterns:
                if pattern.lower().startswith(text) or any(
                    word in text for word in pattern.lower().split()
                ):
                    yield Completion(
                        pattern,
                        start_position=-len(text),
                        display=pattern,
                        display_meta="suggestion"
                    )


class InputArea:
    """Enhanced input area with autocomplete and suggestions."""

    def __init__(
        self,
        on_submit: Callable[[str], None],
        placeholder: str = "Enter your message or command...",
        enable_history: bool = True,
        enable_multiline: bool = True
    ):
        """
        Initialize the input area.

        Args:
            on_submit: Callback when user submits input
            placeholder: Placeholder text
            enable_history: Whether to enable input history
            enable_multiline: Whether to allow multiline input
        """
        self.on_submit = on_submit
        self.placeholder = placeholder
        self.enable_multiline = enable_multiline

        # Create history
        self.history = InMemoryHistory() if enable_history else None

        # Create completer
        self.completer = CommandCompleter()

        # Create buffer with explicit input configuration
        self.buffer = Buffer(
            multiline=enable_multiline,
            history=self.history,
            completer=self.completer,
            complete_while_typing=True,
            accept_handler=self._accept_handler,
            read_only=False,  # Explicitly allow input
        )

        # Create key bindings
        self.kb = KeyBindings()
        self._setup_key_bindings()

        # Create buffer control - let prompt_toolkit handle input processing naturally
        # Remove key_bindings to allow natural text input
        self.buffer_control = BufferControl(
            buffer=self.buffer,
            focusable=True
        )

        # Status information
        self._is_processing = False
        self._last_command = ""

    def _setup_key_bindings(self):
        """Setup key bindings for the input area."""

        @self.kb.add('enter')
        def submit_input(event):
            """Submit input with Enter."""
            self.buffer.validate_and_handle()

        # All other keys go directly to the buffer for natural text input
        # No other key bindings to avoid conflicts

    def _accept_handler(self, buffer):
        """Handle when user submits input."""
        text = buffer.text.strip()
        if text:
            self._last_command = text
            self.on_submit(text)
            buffer.reset()

    @property
    def is_processing(self) -> bool:
        """Check if currently processing a command."""
        return self._is_processing

    def set_processing(self, processing: bool):
        """Set processing state."""
        self._is_processing = processing
        get_app().invalidate()

    def get_prompt_text(self) -> FormattedText:
        """Get the prompt text with current state."""
        if self._is_processing:
            return FormattedText([
                ('class:input.prompt', '🤔 Processing... '),
            ])
        else:
            return FormattedText([
                ('class:input.prompt', '👤 You: '),
            ])

    def get_status_text(self) -> FormattedText:
        """Get status text for the input area."""
        if self._is_processing:
            return FormattedText([
                ('class:statusbar', ' Processing command... Press Ctrl+C to interrupt ')
            ])
        elif self.enable_multiline:
            return FormattedText([
                ('class:statusbar.key', ' Enter '),
                ('class:statusbar', ' new line | '),
                ('class:statusbar.key', ' Ctrl+Enter '),
                ('class:statusbar', ' submit | '),
                ('class:statusbar.key', ' Ctrl+C '),
                ('class:statusbar', ' clear ')
            ])
        else:
            return FormattedText([
                ('class:statusbar.key', ' Enter '),
                ('class:statusbar', ' submit | '),
                ('class:statusbar.key', ' Ctrl+C '),
                ('class:statusbar', ' clear | '),
                ('class:statusbar.key', ' ↑↓ '),
                ('class:statusbar', ' history ')
            ])

    def create_container(self):
        """Create the container for the input area."""
        prompt_window = Window(
            content=FormattedTextControl(text=self.get_prompt_text),
            width=12,
            style='class:input.prompt'
        )

        # Store reference to input window for focus management
        self.input_window = Window(
            content=self.buffer_control,
            height=3 if self.enable_multiline else 1,
            wrap_lines=True,
            style='class:input'
        )

        status_window = Window(
            content=FormattedTextControl(text=self.get_status_text),
            height=1,
            style='class:statusbar'
        )

        from prompt_toolkit.layout.containers import VSplit
        input_line = VSplit([
            prompt_window,
            self.input_window
        ])

        return HSplit([
            input_line,
            status_window
        ])

    def focus(self):
        """Focus the input area."""
        try:
            # Focus the window containing the buffer control, not the control itself
            if hasattr(self, 'input_window'):
                get_app().layout.focus(self.input_window)
            else:
                # Fallback: try to focus the buffer control directly
                get_app().layout.focus(self.buffer_control)
        except:
            # Layout might not be ready yet, ignore for now
            pass

    def clear(self):
        """Clear the input buffer."""
        self.buffer.text = ""

    def set_text(self, text: str):
        """Set the input text."""
        self.buffer.text = text

    def get_text(self) -> str:
        """Get the current input text."""
        return self.buffer.text