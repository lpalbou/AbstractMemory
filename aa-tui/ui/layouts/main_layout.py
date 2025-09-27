"""Main layout composition for the TUI."""

from typing import Optional

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Layout

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from ui.layouts.conversation import ConversationArea
from ui.layouts.input_area import InputArea
from ui.layouts.side_panel import SidePanel, ProgressIndicator


class MainLayout:
    """Main layout manager for the TUI application."""

    def __init__(
        self,
        on_input_submit,
        title: str = "AbstractMemory TUI",
        show_side_panel: bool = True,
        side_panel_width: int = 30
    ):
        """
        Initialize the main layout.

        Args:
            on_input_submit: Callback for when user submits input
            title: Application title
            show_side_panel: Whether to show the side panel
            side_panel_width: Width of the side panel
        """
        self.title = title
        self.on_input_submit = on_input_submit

        # Create main components
        self.conversation_area = ConversationArea(auto_scroll=True)
        self.input_area = InputArea(on_submit=on_input_submit)
        self.side_panel = SidePanel(visible=show_side_panel, width=side_panel_width)
        self.progress_indicator = ProgressIndicator()

        # Modal dialogs will be added here
        self.current_dialog = None

        # Create the layout
        self.layout = self._create_layout()

    def _create_title_bar(self) -> Window:
        """Create the title bar."""
        def get_title_text():
            # Get current time
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S")

            # Get agent status info
            model = getattr(self, '_current_model', 'Unknown')
            status = getattr(self, '_connection_status', 'Unknown')

            return FormattedText([
                ('class:title', f' {self.title} '),
                ('class:title.status', f' | Model: {model} | Status: {status} | Time: {current_time} ')
            ])

        return Window(
            content=FormattedTextControl(text=get_title_text),
            height=1
        )

    def _create_status_bar(self) -> Window:
        """Create the status bar."""
        def get_status_text():
            # Show keyboard shortcuts
            shortcuts = [
                ('class:statusbar.key', ' F1 '),
                ('class:statusbar', ' Help | '),
                ('class:statusbar.key', ' F2 '),
                ('class:statusbar', ' Panel | '),
                ('class:statusbar.key', ' F3 '),
                ('class:statusbar', ' Search | '),
                ('class:statusbar.key', ' Ctrl+L '),
                ('class:statusbar', ' Clear | '),
                ('class:statusbar.key', ' Ctrl+Q '),
                ('class:statusbar', ' Quit ')
            ]

            # Add current operation status if any
            if hasattr(self, '_current_operation') and self._current_operation:
                shortcuts.insert(0, ('class:statusbar', f' {self._current_operation} | '))

            return FormattedText(shortcuts)

        return Window(
            content=FormattedTextControl(text=get_status_text),
            height=1,
            style='class:statusbar'
        )

    def _create_layout(self) -> Layout:
        """Create the main layout structure."""
        # Title bar
        title_bar = self._create_title_bar()

        # Main content area (conversation + side panel)
        main_content = VSplit([
            # Left side: conversation area
            self.conversation_area.create_container(),

            # Right side: side panel (conditional)
            self.side_panel.create_container()
        ])

        # Progress indicator
        progress_container = self.progress_indicator.create_container()

        # Input area
        input_container = self.input_area.create_container()

        # Status bar
        status_bar = self._create_status_bar()

        # Main vertical layout
        main_container = HSplit([
            title_bar,           # Title bar at top
            main_content,        # Main content area
            progress_container,  # Progress indicator (conditional)
            input_container,     # Input area at bottom
            status_bar          # Status bar at bottom
        ])

        # Wrap in FloatContainer to support modal dialogs
        root_container = FloatContainer(
            content=main_container,
            floats=[]  # Dialogs will be added here dynamically
        )

        # Create layout - focus will be set when the app starts
        layout = Layout(container=root_container)

        return layout

    def get_layout(self) -> Layout:
        """Get the prompt_toolkit Layout object."""
        return self.layout

    def add_interaction(
        self,
        interaction_id: int,
        user_input: str,
        agent_response: str,
        thoughts_actions: Optional[str] = None,
        tool_executions: Optional[list] = None,
        memory_injections: Optional[list] = None,
        context_info: Optional[dict] = None
    ):
        """Add a new interaction to the conversation."""
        self.conversation_area.add_interaction(
            interaction_id=interaction_id,
            user_input=user_input,
            agent_response=agent_response,
            thoughts_actions=thoughts_actions,
            tool_executions=tool_executions,
            memory_injections=memory_injections,
            context_info=context_info
        )

    def add_system_message(self, message: str, message_type: str = "info"):
        """Add a system message to the conversation."""
        self.conversation_area.add_system_message(message, message_type)

    def update_current_interaction(
        self,
        thoughts_actions: Optional[str] = None,
        tool_executions: Optional[list] = None,
        memory_injections: Optional[list] = None
    ):
        """Update the current interaction with new information."""
        self.conversation_area.update_current_interaction(
            thoughts_actions=thoughts_actions,
            tool_executions=tool_executions,
            memory_injections=memory_injections
        )

    def clear_conversation(self):
        """Clear the conversation area."""
        self.conversation_area.clear()

    def toggle_side_panel(self):
        """Toggle the side panel visibility."""
        self.side_panel.toggle_visibility()

    def show_side_panel(self):
        """Show the side panel."""
        self.side_panel.show()

    def hide_side_panel(self):
        """Hide the side panel."""
        self.side_panel.hide()

    def update_memory_info(self, memory_info: dict):
        """Update memory information in the side panel."""
        self.side_panel.update_memory_info(memory_info)

    def update_tools_info(self, tools: list):
        """Update tools information in the side panel."""
        self.side_panel.update_tools_info(tools)

    def update_context_metrics(self, metrics: dict):
        """Update context metrics in the side panel."""
        self.side_panel.update_context_metrics(metrics)

    def update_agent_status(self, status: dict):
        """Update agent status in the side panel."""
        self.side_panel.update_agent_status(status)

    def start_progress(self, message: str):
        """Start the progress indicator."""
        self.progress_indicator.start(message)

    def update_progress(self, progress: float, message: Optional[str] = None):
        """Update the progress indicator."""
        self.progress_indicator.update(progress, message)

    def stop_progress(self):
        """Stop the progress indicator."""
        self.progress_indicator.stop()

    def set_processing_state(self, processing: bool, operation: str = ""):
        """Set the processing state for the input area."""
        self.input_area.set_processing(processing)
        self._current_operation = operation if processing else ""
        get_app().invalidate()

    def focus_input(self):
        """Focus the input area."""
        self.input_area.focus()

    def clear_input(self):
        """Clear the input area."""
        self.input_area.clear()

    def set_input_text(self, text: str):
        """Set text in the input area."""
        self.input_area.set_text(text)

    def get_input_text(self) -> str:
        """Get current input text."""
        return self.input_area.get_text()

    def expand_all_sections(self):
        """Expand all foldable sections in the conversation."""
        self.conversation_area.expand_all()

    def collapse_all_sections(self):
        """Collapse all foldable sections in the conversation."""
        self.conversation_area.collapse_all()

    def search_conversation(self, query: str):
        """Search the conversation for entries matching the query."""
        return self.conversation_area.search_entries(query)

    def get_conversation_stats(self) -> dict:
        """Get conversation statistics."""
        return {
            'entry_count': self.conversation_area.get_entry_count(),
            'last_interaction_id': self.conversation_area.get_last_interaction_id(),
            'side_panel_visible': self.side_panel.visible
        }

    def add_modal_dialog(self, dialog_container, float_spec):
        """Add a modal dialog to the layout."""
        from prompt_toolkit.layout.containers import Float

        dialog_float = Float(
            content=dialog_container,
            **float_spec
        )

        self.layout.container.floats.append(dialog_float)
        self.current_dialog = dialog_float
        get_app().invalidate()

    def remove_modal_dialog(self):
        """Remove the current modal dialog."""
        if self.current_dialog:
            if self.current_dialog in self.layout.container.floats:
                self.layout.container.floats.remove(self.current_dialog)
            self.current_dialog = None
            get_app().invalidate()

    def invalidate(self):
        """Invalidate the layout to force refresh."""
        self.conversation_area.invalidate_cache()
        get_app().invalidate()

    def update_title_info(self, model: str = None, status: str = None):
        """Update information shown in the title bar."""
        if model:
            self._current_model = model
        if status:
            self._connection_status = status
        get_app().invalidate()