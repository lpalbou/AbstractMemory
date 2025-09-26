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
            ('dialog.title', 'AbstractMemory TUI - Help\n\n'),

            ('dialog', 'KEYBOARD SHORTCUTS:\n'),
            ('dialog', '─' * 40 + '\n'),

            ('button.focused', 'F1'), ('dialog', '           Show this help\n'),
            ('button.focused', 'F2'), ('dialog', '           Toggle side panel\n'),
            ('button.focused', 'F3'), ('dialog', '           Search conversation\n'),
            ('button.focused', 'F4'), ('dialog', '           Memory search\n'),
            ('button.focused', 'Ctrl+L'), ('dialog', '       Clear screen\n'),
            ('button.focused', 'Ctrl+Q'), ('dialog', '       Quit application\n'),
            ('button.focused', 'Ctrl+C'), ('dialog', '       Clear input / Cancel\n'),
            ('button.focused', 'Tab'), ('dialog', '          Cycle through UI elements\n'),
            ('button.focused', 'Enter'), ('dialog', '        Submit input / Expand sections\n'),
            ('button.focused', 'Space'), ('dialog', '        Expand/collapse sections\n'),
            ('button.focused', '↑/↓'), ('dialog', '          History navigation (empty input)\n\n'),

            ('dialog', 'COMMANDS:\n'),
            ('dialog', '─' * 40 + '\n'),

            ('tool.success', '/help'), ('dialog', '         Show this help\n'),
            ('tool.success', '/status'), ('dialog', '       Show agent status\n'),
            ('tool.success', '/memory'), ('dialog', '       Show memory contents\n'),
            ('tool.success', '/memory N'), ('dialog', '     Set max tokens to N\n'),
            ('tool.success', '/tools'), ('dialog', '        Show available tools\n'),
            ('tool.success', '/debug'), ('dialog', '        Show debug information\n'),
            ('tool.success', '/context'), ('dialog', '      Show last context used\n'),
            ('tool.success', '/compact'), ('dialog', '      Compact session history\n'),
            ('tool.success', '/scratch N'), ('dialog', '    Show full reasoning for interaction N\n'),
            ('tool.success', '/clear'), ('dialog', '        Clear conversation\n'),
            ('tool.success', '/quit'), ('dialog', '         Exit application\n\n'),

            ('dialog', 'AGENT CAPABILITIES:\n'),
            ('dialog', '─' * 40 + '\n'),

            ('memory.working', '• Memory:'), ('dialog', ' Persistent memory across sessions\n'),
            ('memory.semantic', '• Facts:'), ('dialog', ' Learns and remembers important information\n'),
            ('memory.document', '• Files:'), ('dialog', ' Can read and analyze files\n'),
            ('tool.success', '• Tools:'), ('dialog', ' Has access to various tools\n'),
            ('thought', '• ReAct:'), ('dialog', ' Shows reasoning process\n\n'),

            ('dialog', 'CONVERSATION FEATURES:\n'),
            ('dialog', '─' * 40 + '\n'),

            ('foldable.header', '• Foldable Sections:'), ('dialog', ' Click or press Enter/Space\n'),
            ('conversation.user', '• User Messages:'), ('dialog', ' Your input shown in green\n'),
            ('conversation.agent', '• Agent Responses:'), ('dialog', ' AI responses in blue\n'),
            ('thought', '• Thoughts:'), ('dialog', ' AI reasoning process\n'),
            ('action', '• Actions:'), ('dialog', ' Tool executions\n'),
            ('observation', '• Observations:'), ('dialog', ' Tool results\n\n'),

            ('dialog', 'Press '),
            ('button.focused', 'Escape'),
            ('dialog', ', '),
            ('button.focused', 'Q'),
            ('dialog', ', or '),
            ('button.focused', 'Ctrl+C'),
            ('dialog', ' to close this dialog.')
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
            style='dialog'
        )

        # Wrap in a frame
        return Frame(
            body=help_content,
            title="Help",
            style='dialog.border'
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
                text=FormattedText([('dialog', 'Search: ')])
            ),
            width=8,
            style='dialog'
        )

        # Search input
        input_window = Window(
            content=BufferControl(
                buffer=self.search_buffer,
                key_bindings=self.kb,
                focusable=True
            ),
            style='input'
        )

        # Instructions
        instructions = Window(
            content=FormattedTextControl(
                text=FormattedText([
                    ('dialog', '\nEnter search query and press '),
                    ('button.focused', 'Enter'),
                    ('dialog', ' to search.\nPress '),
                    ('button.focused', 'Escape'),
                    ('dialog', ' to cancel.')
                ])
            ),
            height=3,
            style='dialog'
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
            style='dialog.border'
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