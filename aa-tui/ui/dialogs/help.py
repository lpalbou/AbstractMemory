"""Help dialog for the TUI."""

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window, Frame
from prompt_toolkit.layout.controls import FormattedTextControl


class HelpDialog:
    """Help dialog showing keyboard shortcuts and commands."""

    def __init__(self, on_close=None):
        """
        Initialize the help dialog.

        Args:
            on_close: Callback when dialog is closed
        """
        self.on_close = on_close

        # Create key bindings
        self.kb = KeyBindings()
        self._setup_key_bindings()

        # Create the dialog content
        self.container = self._create_container()

    def _setup_key_bindings(self):
        """Setup key bindings for the dialog."""

        @self.kb.add('escape')
        @self.kb.add('q')
        @self.kb.add('c-c')
        def close_dialog(event):
            """Close the dialog."""
            if self.on_close:
                self.on_close()

    def _get_help_content(self) -> FormattedText:
        """Get the help content."""
        return FormattedText([
            ('', 'AbstractMemory TUI - Help\n\n'),

            ('', 'KEYBOARD SHORTCUTS:\n'),
            ('', '─' * 40 + '\n'),

            ('', 'F1           Show this help\n'),
            ('', 'F2           Toggle side panel\n'),
            ('', 'F3           Search conversation\n'),
            ('', 'F4           Memory search\n'),
            ('', 'Ctrl+L       Clear screen\n'),
            ('', 'Ctrl+Q       Quit application\n'),
            ('', 'Ctrl+C       Clear input / Cancel\n'),
            ('', 'Tab          Cycle through UI elements\n'),
            ('', 'Enter        Submit input / Expand sections\n'),
            ('', 'Space        Expand/collapse sections\n'),
            ('', '↑/↓          History navigation (empty input)\n\n'),

            ('', 'COMMANDS:\n'),
            ('', '─' * 40 + '\n'),

            ('', '/help         Show this help\n'),
            ('', '/status       Show agent status\n'),
            ('', '/memory       Show memory contents\n'),
            ('', '/tools        Show available tools\n'),
            ('', '/clear        Clear conversation\n'),
            ('', '/quit         Exit application\n\n'),

            ('', 'AGENT CAPABILITIES:\n'),
            ('', '─' * 40 + '\n'),

            ('', '• Memory: Persistent memory across sessions\n'),
            ('', '• Facts: Learns and remembers important information\n'),
            ('', '• Files: Can read and analyze files\n'),
            ('', '• Tools: Has access to various tools\n'),
            ('', '• ReAct: Shows reasoning process\n\n'),

            ('', 'CONVERSATION FEATURES:\n'),
            ('', '─' * 40 + '\n'),

            ('', '• Foldable Sections: Click or press Enter/Space\n'),
            ('', '• User Messages: Your input shown in green\n'),
            ('', '• Agent Responses: AI responses in blue\n'),
            ('', '• Thoughts: AI reasoning process\n'),
            ('', '• Actions: Tool executions\n'),
            ('', '• Observations: Tool results\n\n'),

            ('', 'Press Escape, Q, or Ctrl+C to close this dialog.')
        ])

    def _create_container(self):
        """Create the dialog container."""
        help_content = Window(
            content=FormattedTextControl(
                text=self._get_help_content,
                key_bindings=self.kb,
                focusable=True
            ),
            wrap_lines=True,
            style='class:dialog'
        )

        # Wrap in a frame
        return Frame(
            body=help_content,
            title="Help",
            style='class:dialog.border'
        )

    def get_float_spec(self):
        """Get the float specification for this dialog."""
        return {
            'top': 2,
            'left': 4,
            'width': 80,
            'height': 30
        }


class SearchDialog:
    """Search dialog for finding content in the conversation."""

    def __init__(self, on_search=None, on_close=None):
        """
        Initialize the search dialog.

        Args:
            on_search: Callback when search is performed
            on_close: Callback when dialog is closed
        """
        self.on_search = on_search
        self.on_close = on_close

        # Create buffer for search input
        from prompt_toolkit.buffer import Buffer
        self.search_buffer = Buffer(
            multiline=False,
            accept_handler=self._handle_search
        )

        # Create key bindings
        self.kb = KeyBindings()
        self._setup_key_bindings()

        # Create the dialog content
        self.container = self._create_container()

    def _setup_key_bindings(self):
        """Setup key bindings for the dialog."""

        @self.kb.add('escape')
        @self.kb.add('c-c')
        def close_dialog(event):
            """Close the dialog."""
            if self.on_close:
                self.on_close()

        @self.kb.add('enter')
        def perform_search(event):
            """Perform the search."""
            self._handle_search(self.search_buffer)

    def _handle_search(self, buffer):
        """Handle search submission."""
        query = buffer.text.strip()
        if query and self.on_search:
            self.on_search(query)
        if self.on_close:
            self.on_close()

    def _create_container(self):
        """Create the dialog container."""
        from prompt_toolkit.layout.containers import VSplit
        from prompt_toolkit.layout.controls import BufferControl

        # Search prompt
        prompt_window = Window(
            content=FormattedTextControl(
                text=FormattedText([('class:dialog', 'Search: ')])
            ),
            width=8,
            style='class:dialog'
        )

        # Search input
        input_window = Window(
            content=BufferControl(
                buffer=self.search_buffer,
                key_bindings=self.kb,
                focusable=True
            ),
            style='class:input'
        )

        # Instructions
        instructions = Window(
            content=FormattedTextControl(
                text=FormattedText([
                    ('', '\nEnter search query and press Enter to search.\nPress Escape to cancel.')
                ])
            ),
            height=3,
            style='class:dialog'
        )

        search_line = VSplit([prompt_window, input_window])

        content = HSplit([
            search_line,
            instructions
        ])

        # Wrap in a frame
        return Frame(
            body=content,
            title="Search Conversation",
            style='class:dialog.border'
        )

    def get_float_spec(self):
        """Get the float specification for this dialog."""
        return {
            'top': 8,
            'left': 10,
            'width': 60,
            'height': 8
        }

    def focus(self):
        """Focus the search input."""
        get_app().layout.focus(self.search_buffer)