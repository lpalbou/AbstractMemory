"""Conversation area with foldable sections and scrolling."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from ui.widgets.foldable import FoldableConversationEntry


class ConversationArea:
    """Main conversation display area with foldable entries."""

    def __init__(self, auto_scroll: bool = True, max_entries: int = 1000):
        """
        Initialize the conversation area.

        Args:
            auto_scroll: Whether to auto-scroll to bottom on new entries
            max_entries: Maximum number of entries to keep in memory
        """
        self.auto_scroll = auto_scroll
        self.max_entries = max_entries
        self.entries: List[FoldableConversationEntry] = []
        self._container_cache = None

    def add_interaction(
        self,
        interaction_id: int,
        user_input: str,
        agent_response: str,
        thoughts_actions: Optional[str] = None,
        tool_executions: Optional[List[Dict]] = None,
        memory_injections: Optional[List[Dict]] = None,
        context_info: Optional[Dict] = None,
        expanded: bool = False
    ):
        """
        Add a new interaction to the conversation.

        Args:
            interaction_id: Unique identifier for the interaction
            user_input: User's input
            agent_response: Agent's response
            thoughts_actions: Agent's reasoning process
            tool_executions: Tool executions performed
            memory_injections: Memory items that were injected
            context_info: Context information (tokens, time, etc.)
            expanded: Whether to start expanded
        """
        entry = FoldableConversationEntry(
            interaction_id=interaction_id,
            user_input=user_input,
            agent_response=agent_response,
            thoughts_actions=thoughts_actions,
            tool_executions=tool_executions,
            memory_injections=memory_injections,
            expanded=expanded
        )

        self.entries.append(entry)

        # Limit number of entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        # Invalidate cache and refresh
        self._container_cache = None
        get_app().invalidate()

        # Auto-scroll to bottom if enabled
        if self.auto_scroll:
            self.scroll_to_bottom()

    def add_system_message(self, message: str, message_type: str = "info"):
        """
        Add a system message to the conversation.

        Args:
            message: System message text
            message_type: Type of message (info, warning, error, success)
        """
        # Create a simple system message entry
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        # Add as a special entry
        self.entries.append({
            'type': 'system',
            'message': formatted_message,
            'message_type': message_type,
            'timestamp': timestamp
        })

        self._container_cache = None
        get_app().invalidate()

        if self.auto_scroll:
            self.scroll_to_bottom()

    def update_current_interaction(
        self,
        thoughts_actions: Optional[str] = None,
        tool_executions: Optional[List[Dict]] = None,
        memory_injections: Optional[List[Dict]] = None
    ):
        """
        Update the current (last) interaction with new information.

        Args:
            thoughts_actions: Updated reasoning process
            tool_executions: Updated tool executions
            memory_injections: Updated memory injections
        """
        if not self.entries:
            return

        last_entry = self.entries[-1]
        if isinstance(last_entry, FoldableConversationEntry):
            if thoughts_actions is not None:
                last_entry.thoughts_actions = thoughts_actions
                # Recreate thoughts section if needed
                if thoughts_actions and not last_entry.thoughts_section:
                    last_entry.thoughts_section = last_entry._create_thoughts_section()

            if tool_executions is not None:
                last_entry.tool_executions = tool_executions
                # Recreate tools section if needed
                if tool_executions and not last_entry.tools_section:
                    last_entry.tools_section = last_entry._create_tools_section()

            if memory_injections is not None:
                last_entry.memory_injections = memory_injections
                # Recreate memory section if needed
                if memory_injections and not last_entry.memory_section:
                    last_entry.memory_section = last_entry._create_memory_section()

            self._container_cache = None
            get_app().invalidate()

    def expand_all(self):
        """Expand all foldable sections."""
        for entry in self.entries:
            if isinstance(entry, FoldableConversationEntry):
                entry.main_section.expand()
                if entry.thoughts_section:
                    entry.thoughts_section.expand()
                if entry.tools_section:
                    entry.tools_section.expand()
                if entry.memory_section:
                    entry.memory_section.expand()

    def collapse_all(self):
        """Collapse all foldable sections."""
        for entry in self.entries:
            if isinstance(entry, FoldableConversationEntry):
                entry.main_section.collapse()
                if entry.thoughts_section:
                    entry.thoughts_section.collapse()
                if entry.tools_section:
                    entry.tools_section.collapse()
                if entry.memory_section:
                    entry.memory_section.collapse()

    def clear(self):
        """Clear all conversation entries."""
        self.entries.clear()
        self._container_cache = None
        get_app().invalidate()

    def scroll_to_bottom(self):
        """Scroll to the bottom of the conversation."""
        # This will be handled by the ScrollablePane
        get_app().invalidate()

    def get_entry_count(self) -> int:
        """Get the number of entries."""
        return len(self.entries)

    def get_last_interaction_id(self) -> Optional[int]:
        """Get the ID of the last interaction."""
        if self.entries:
            last_entry = self.entries[-1]
            if isinstance(last_entry, FoldableConversationEntry):
                return last_entry.interaction_id
        return None

    def search_entries(self, query: str) -> List[FoldableConversationEntry]:
        """
        Search for entries containing the query.

        Args:
            query: Search query

        Returns:
            List of matching entries
        """
        results = []
        query_lower = query.lower()

        for entry in self.entries:
            if isinstance(entry, FoldableConversationEntry):
                # Search in user input
                if query_lower in entry.user_input.lower():
                    results.append(entry)
                    continue

                # Search in agent response
                if query_lower in entry.agent_response.lower():
                    results.append(entry)
                    continue

                # Search in thoughts/actions
                if entry.thoughts_actions and query_lower in entry.thoughts_actions.lower():
                    results.append(entry)
                    continue

        return results

    def _create_system_message_control(self, entry: Dict) -> Window:
        """Create a control for system messages."""
        message = entry['message']
        message_type = entry.get('message_type', 'info')

        style_map = {
            'info': 'conversation.system',
            'warning': 'tool.error',
            'error': 'tool.error',
            'success': 'tool.success'
        }

        style = style_map.get(message_type, 'conversation.system')

        return Window(
            content=FormattedTextControl(
                text=FormattedText([(f'class:{style}', f"ℹ️  {message}")])
            ),
            height=1,
            wrap_lines=True,
            style=f'class:{style}'
        )

    def create_container(self):
        """Create the container for the conversation area."""
        if self._container_cache is None:
            children = []

            # Add welcome message if no entries
            if not self.entries:
                welcome_text = FormattedText([
                    ('class:title', '🤖 AbstractMemory TUI\n'),
                    ('class:conversation', '\nWelcome! Start a conversation by typing below.\n'),
                    ('class:conversation.system', 'Use '),
                    ('class:conversation.system', '/help'),
                    ('class:conversation.system', ' for available commands.\n\n')
                ])

                children.append(Window(
                    content=FormattedTextControl(text=welcome_text),
                    wrap_lines=True,
                    style='class:conversation'
                ))

            # Add all entries
            for entry in self.entries:
                if isinstance(entry, FoldableConversationEntry):
                    children.append(entry.create_container())
                elif isinstance(entry, dict) and entry.get('type') == 'system':
                    children.append(self._create_system_message_control(entry))

            # Add padding at the bottom
            children.append(Window(height=2))

            # Create main container
            self._container_cache = HSplit(children)

        return self._container_cache

    def invalidate_cache(self):
        """Invalidate the container cache to force rebuild."""
        self._container_cache = None