"""Foldable/collapsible widget implementation using prompt_toolkit."""

from typing import Callable, Optional, Any
from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType


class FoldableSection:
    """A foldable/collapsible section widget."""

    def __init__(
        self,
        title: str,
        content_factory: Callable[[], Any],
        expanded: bool = False,
        style_prefix: str = "foldable",
        on_toggle: Optional[Callable[[bool], None]] = None
    ):
        """
        Initialize a foldable section.

        Args:
            title: Title to display in the header
            content_factory: Function that returns the content to display when expanded
            expanded: Whether the section starts expanded
            style_prefix: CSS style prefix for theming
            on_toggle: Optional callback when section is toggled
        """
        self.title = title
        self.content_factory = content_factory
        self._expanded = expanded
        self.style_prefix = style_prefix
        self.on_toggle = on_toggle

        # Create key bindings for the header
        self.header_kb = KeyBindings()

        @self.header_kb.add('enter')
        @self.header_kb.add(' ')
        def toggle_section(event):
            """Toggle section when Enter or Space is pressed."""
            self.toggle()

        # Create the header control
        self.header_control = FormattedTextControl(
            text=self._get_header_text,
            key_bindings=self.header_kb,
            focusable=True
        )

        # Set up mouse handler for the header
        self.header_control.mouse_handler = self._header_mouse_handler

    def _get_header_text(self) -> FormattedText:
        """Generate the header text with expand/collapse indicator."""
        indicator = "▼" if self._expanded else "▶"
        style = f"{self.style_prefix}.header.{'expanded' if self._expanded else 'collapsed'}"
        return FormattedText([
            (style, f"{indicator} {self.title}")
        ])

    def _header_mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse clicks on the header."""
        if mouse_event.event_type == MouseEventType.MOUSE_UP:
            self.toggle()

    @property
    def expanded(self) -> bool:
        """Check if section is expanded."""
        return self._expanded

    def expand(self):
        """Expand the section."""
        if not self._expanded:
            self._expanded = True
            if self.on_toggle:
                self.on_toggle(True)
            get_app().invalidate()

    def collapse(self):
        """Collapse the section."""
        if self._expanded:
            self._expanded = False
            if self.on_toggle:
                self.on_toggle(False)
            get_app().invalidate()

    def toggle(self):
        """Toggle the section state."""
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def is_expanded(self) -> bool:
        """Check if section is expanded."""
        return self._expanded

    @property
    def expanded_filter(self):
        """Get expanded filter for ConditionalContainer."""
        return Condition(lambda: self._expanded)

    def create_container(self):
        """Create the container for this foldable section."""
        header_window = Window(
            content=self.header_control,
            height=1,
            style=f"{self.style_prefix}.header"
        )

        content_container = ConditionalContainer(
            content=self.content_factory(),
            filter=self.expanded_filter
        )

        return HSplit([
            header_window,
            content_container
        ])


class FoldableConversationEntry:
    """Specialized foldable section for conversation entries with thoughts/actions."""

    def __init__(
        self,
        interaction_id: int,
        user_input: str,
        agent_response: str,
        thoughts_actions: Optional[str] = None,
        tool_executions: Optional[list] = None,
        memory_injections: Optional[list] = None,
        expanded: bool = False
    ):
        """
        Initialize a foldable conversation entry.

        Args:
            interaction_id: Unique identifier for this interaction
            user_input: The user's input
            agent_response: The agent's final response
            thoughts_actions: The agent's reasoning process
            tool_executions: List of tool executions
            memory_injections: List of memory items injected
            expanded: Whether to start expanded
        """
        self.interaction_id = interaction_id
        self.user_input = user_input
        self.agent_response = agent_response
        self.thoughts_actions = thoughts_actions
        self.tool_executions = tool_executions or []
        self.memory_injections = memory_injections or []

        # Create main sections
        self.main_section = FoldableSection(
            title=f"Interaction #{interaction_id}",
            content_factory=self._create_main_content,
            expanded=expanded
        )

        # Create subsections if content exists
        self.thoughts_section = None
        if self.thoughts_actions:
            self.thoughts_section = FoldableSection(
                title="💭 Thoughts & Actions",
                content_factory=self._create_thoughts_content,
                expanded=False,
                style_prefix="foldable.thoughts"
            )

        self.tools_section = None
        if self.tool_executions:
            self.tools_section = FoldableSection(
                title=f"🔧 Tool Executions ({len(self.tool_executions)})",
                content_factory=self._create_tools_content,
                expanded=False,
                style_prefix="foldable.tools"
            )

        self.memory_section = None
        if self.memory_injections:
            self.memory_section = FoldableSection(
                title=f"🧠 Memory Injections ({len(self.memory_injections)})",
                content_factory=self._create_memory_content,
                expanded=False,
                style_prefix="foldable.memory"
            )

    def _create_main_content(self):
        """Create the main content container."""
        content_parts = []

        # User input
        content_parts.append(Window(
            content=FormattedTextControl(
                text=FormattedText([
                    ("conversation.user", f"👤 User: {self.user_input}")
                ])
            ),
            height=1,
            wrap_lines=True
        ))

        # Add subsections
        if self.thoughts_section:
            content_parts.append(self.thoughts_section.create_container())

        if self.tools_section:
            content_parts.append(self.tools_section.create_container())

        if self.memory_section:
            content_parts.append(self.memory_section.create_container())

        # Agent response
        content_parts.append(Window(
            content=FormattedTextControl(
                text=FormattedText([
                    ("conversation.agent", f"🤖 Agent: {self.agent_response}")
                ])
            ),
            wrap_lines=True,
            style="conversation.agent"
        ))

        return HSplit(content_parts)

    def _create_thoughts_content(self):
        """Create thoughts and actions content."""
        return Window(
            content=FormattedTextControl(
                text=self._format_thoughts_actions()
            ),
            wrap_lines=True,
            style="foldable.content"
        )

    def _create_tools_content(self):
        """Create tool executions content."""
        return Window(
            content=FormattedTextControl(
                text=self._format_tool_executions()
            ),
            wrap_lines=True,
            style="foldable.content"
        )

    def _create_memory_content(self):
        """Create memory injections content."""
        return Window(
            content=FormattedTextControl(
                text=self._format_memory_injections()
            ),
            wrap_lines=True,
            style="foldable.content"
        )

    def _format_thoughts_actions(self) -> FormattedText:
        """Format thoughts and actions with syntax highlighting."""
        if not self.thoughts_actions:
            return FormattedText([("", "No thoughts available.")])

        formatted_parts = []
        lines = self.thoughts_actions.split('\n')

        for line in lines:
            line = line.strip()
            if line.startswith('Thought:'):
                formatted_parts.append(('thought', line))
            elif line.startswith('Action:'):
                formatted_parts.append(('action', line))
            elif line.startswith('Observation:'):
                formatted_parts.append(('observation', line))
            else:
                formatted_parts.append(('foldable.content', line))
            formatted_parts.append(('', '\n'))

        return FormattedText(formatted_parts)

    def _format_tool_executions(self) -> FormattedText:
        """Format tool executions."""
        if not self.tool_executions:
            return FormattedText([("", "No tool executions.")])

        formatted_parts = []
        for i, execution in enumerate(self.tool_executions, 1):
            tool_name = execution.get('tool_name', 'unknown')
            tool_input = execution.get('tool_input', {})
            tool_result = execution.get('tool_result', '')
            success = not tool_result.startswith('Error:')

            status_style = 'tool.success' if success else 'tool.error'
            status_icon = '✅' if success else '❌'

            formatted_parts.extend([
                ('', f"{i}. "),
                (status_style, f"{status_icon} {tool_name}"),
                ('', f"({tool_input})\n"),
                ('foldable.content', f"   Result: {tool_result[:200]}"),
                ('', '...\n' if len(tool_result) > 200 else '\n'),
                ('', '\n')
            ])

        return FormattedText(formatted_parts)

    def _format_memory_injections(self) -> FormattedText:
        """Format memory injections."""
        if not self.memory_injections:
            return FormattedText([("", "No memory injections.")])

        formatted_parts = []
        for i, item in enumerate(self.memory_injections, 1):
            item_type = item.get('type', 'unknown')
            content = str(item.get('content', ''))[:100]
            confidence = item.get('confidence', 0.0)

            formatted_parts.extend([
                ('', f"{i}. "),
                ('memory.' + item_type, f"[{item_type}] "),
                ('foldable.content', content),
                ('', '...\n' if len(str(item.get('content', ''))) > 100 else '\n'),
                ('', f"   Confidence: {confidence:.2f}\n\n")
            ])

        return FormattedText(formatted_parts)

    def create_container(self):
        """Create the container for this conversation entry."""
        return self.main_section.create_container()