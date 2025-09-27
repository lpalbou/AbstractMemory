"""Global key bindings for the TUI."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from prompt_toolkit.application import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition


class GlobalKeyBindings:
    """Global key bindings manager."""

    def __init__(self, main_layout, dialog_manager=None):
        """
        Initialize global key bindings.

        Args:
            main_layout: Main layout instance
            dialog_manager: Dialog manager instance
        """
        self.main_layout = main_layout
        self.dialog_manager = dialog_manager

        # Create key bindings
        self.kb = KeyBindings()
        self._setup_global_bindings()

    def _setup_global_bindings(self):
        """Setup minimal global key bindings that don't conflict with input."""

        @self.kb.add('c-q')
        def quit_application(event):
            """Quit the application."""
            event.app.exit()

        @self.kb.add('f2')
        def toggle_side_panel(event):
            """Toggle side panel visibility."""
            self.main_layout.toggle_side_panel()

        # Keep only essential bindings to avoid conflicts with input
        # All other keys should go to the input buffer when it's focused

    def _is_input_focused(self):
        """Check if the input area is currently focused."""
        try:
            from prompt_toolkit.application import get_app
            app = get_app()
            current_control = app.layout.current_control
            return hasattr(current_control, 'buffer') and current_control.buffer is not None
        except:
            return False

    def get_key_bindings(self):
        """Get the key bindings object."""
        # Merge with input area key bindings if available
        if hasattr(self.main_layout, 'input_area') and hasattr(self.main_layout.input_area, 'kb'):
            from prompt_toolkit.key_binding import merge_key_bindings
            return merge_key_bindings([
                self.kb,
                self.main_layout.input_area.kb
            ])
        return self.kb


class DialogManager:
    """Manager for modal dialogs."""

    def __init__(self, main_layout):
        """
        Initialize the dialog manager.

        Args:
            main_layout: Main layout instance
        """
        self.main_layout = main_layout
        self.current_dialog = None

    def show_help(self):
        """Show the help dialog."""
        if self.current_dialog:
            return  # Already showing a dialog

        from ui.dialogs.help import HelpDialog

        help_dialog = HelpDialog(on_close=self._close_dialog)
        self.current_dialog = help_dialog

        self.main_layout.add_modal_dialog(
            help_dialog.container,
            help_dialog.get_float_spec()
        )

        # Focus the dialog
        get_app().layout.focus(help_dialog.container)

    def show_search(self):
        """Show the search dialog."""
        if self.current_dialog:
            return  # Already showing a dialog

        from ui.dialogs.help import SearchDialog

        search_dialog = SearchDialog(
            on_search=self._handle_search,
            on_close=self._close_dialog
        )
        self.current_dialog = search_dialog

        self.main_layout.add_modal_dialog(
            search_dialog.container,
            search_dialog.get_float_spec()
        )

        # Focus the search input
        search_dialog.focus()

    def show_memory_search(self):
        """Show memory search dialog."""
        # For now, show regular search - can be enhanced for memory-specific search
        self.show_search()

    def _handle_search(self, query: str):
        """Handle search query."""
        results = self.main_layout.search_conversation(query)

        if results:
            message = f"Found {len(results)} results for '{query}'"
            self.main_layout.add_system_message(message, "success")

            # Expand the first few results
            for i, entry in enumerate(results[:3]):
                entry.main_section.expand()
        else:
            message = f"No results found for '{query}'"
            self.main_layout.add_system_message(message, "warning")

    def _close_dialog(self):
        """Close the current dialog."""
        if self.current_dialog:
            self.main_layout.remove_modal_dialog()
            self.current_dialog = None

            # Return focus to input
            self.main_layout.focus_input()

    def is_dialog_open(self) -> bool:
        """Check if a dialog is currently open."""
        return self.current_dialog is not None


class CommandProcessor:
    """Process slash commands."""

    def __init__(self, main_layout, agent_cli=None):
        """
        Initialize the command processor.

        Args:
            main_layout: Main layout instance
            agent_cli: Agent CLI instance for command execution
        """
        self.main_layout = main_layout
        self.agent_cli = agent_cli

    def process_command(self, command: str) -> bool:
        """
        Process a slash command.

        Args:
            command: Command string starting with '/'

        Returns:
            True if command was handled, False otherwise
        """
        if not command.startswith('/'):
            return False

        parts = command.lower().split()
        cmd = parts[0]

        try:
            if cmd in ['/quit', '/exit', '/q']:
                self._handle_quit()
                return True

            elif cmd == '/help':
                self._handle_help()
                return True

            elif cmd == '/clear':
                self._handle_clear()
                return True

            elif cmd == '/status':
                self._handle_status()
                return True

            elif cmd == '/memory':
                if len(parts) > 1:
                    self._handle_memory_config(parts[1])
                else:
                    self._handle_memory_status()
                return True

            elif cmd == '/tools':
                self._handle_tools_status()
                return True

            elif cmd == '/debug':
                self._handle_debug()
                return True

            elif cmd == '/context':
                self._handle_context()
                return True

            elif cmd.startswith('/compact'):
                self._handle_compact(command)
                return True

            elif cmd.startswith('/scratch'):
                self._handle_scratch(parts)
                return True

            else:
                self.main_layout.add_system_message(
                    f"Unknown command: {cmd}. Type /help for available commands.",
                    "error"
                )
                return True

        except Exception as e:
            self.main_layout.add_system_message(
                f"Error executing command {cmd}: {e}",
                "error"
            )
            return True

    def _handle_quit(self):
        """Handle quit command."""
        get_app().exit()

    def _handle_help(self):
        """Handle help command."""
        # Show system message instead of dialog for now
        help_text = """Available commands:
/help - Show this help
/status - Show agent status
/memory - Show memory status
/tools - Show available tools
/clear - Clear conversation
/quit - Exit application

Press F1 for detailed help with keyboard shortcuts."""

        self.main_layout.add_system_message(help_text, "info")

    def _handle_clear(self):
        """Handle clear command."""
        self.main_layout.clear_conversation()
        self.main_layout.add_system_message("Conversation cleared.", "success")

    def _handle_status(self):
        """Handle status command."""
        if self.agent_cli:
            # Get status from agent CLI
            stats = self.main_layout.get_conversation_stats()
            status_text = f"""Agent Status:
- Interactions: {stats['entry_count']}
- Last ID: {stats.get('last_interaction_id', 'None')}
- Side Panel: {'Visible' if stats['side_panel_visible'] else 'Hidden'}"""

            self.main_layout.add_system_message(status_text, "info")
        else:
            self.main_layout.add_system_message("Agent not initialized.", "error")

    def _handle_memory_status(self):
        """Handle memory status display."""
        self.main_layout.add_system_message("Memory status shown in side panel (F2 to toggle).", "info")

    def _handle_memory_config(self, value: str):
        """Handle memory configuration."""
        try:
            max_tokens = int(value)
            if max_tokens > 0:
                self.main_layout.add_system_message(f"Max tokens set to {max_tokens:,}", "success")
                # TODO: Actually update the configuration
            else:
                self.main_layout.add_system_message("Max tokens must be positive.", "error")
        except ValueError:
            self.main_layout.add_system_message("Invalid number for max tokens.", "error")

    def _handle_tools_status(self):
        """Handle tools status display."""
        self.main_layout.add_system_message("Tools status shown in side panel (F2 to toggle).", "info")

    def _handle_debug(self):
        """Handle debug command."""
        stats = self.main_layout.get_conversation_stats()
        debug_text = f"""Debug Information:
- Layout: MainLayout active
- Entries: {stats['entry_count']} in conversation
- Side Panel: {stats['side_panel_visible']}
- Input Focus: Available
- Theme: Active"""

        self.main_layout.add_system_message(debug_text, "info")

    def _handle_context(self):
        """Handle context display."""
        self.main_layout.add_system_message("Context information would be displayed here.", "info")

    def _handle_compact(self, command: str):
        """Handle compact command."""
        self.main_layout.add_system_message("Compact functionality not yet implemented in TUI.", "warning")

    def _handle_scratch(self, parts: list):
        """Handle scratch command."""
        if len(parts) < 2:
            self.main_layout.add_system_message("Usage: /scratch <interaction_id>", "error")
            return

        try:
            interaction_id = int(parts[1])
            self.main_layout.add_system_message(
                f"Scratch details for interaction #{interaction_id} would be displayed here.",
                "info"
            )
        except ValueError:
            self.main_layout.add_system_message("Invalid interaction ID.", "error")