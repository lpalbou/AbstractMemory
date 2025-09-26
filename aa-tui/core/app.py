"""Main TUI Application class."""

import asyncio
import sys
from typing import Optional, Dict, Any
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.config import TUIConfig
from ui.layouts.main_layout import MainLayout
from ui.styles.safe_themes import get_safe_theme
from handlers.key_bindings import GlobalKeyBindings, DialogManager, CommandProcessor


class AbstractMemoryTUI:
    """Main TUI application for AbstractMemory."""

    def __init__(self, config: Optional[TUIConfig] = None):
        """
        Initialize the TUI application.

        Args:
            config: Configuration object, creates default if None
        """
        self.config = config or TUIConfig()
        self.running = False
        self.agent_session = None  # Will be set when agent is initialized

        # Create main layout
        self.main_layout = MainLayout(
            on_input_submit=self._handle_user_input,
            title="AbstractMemory TUI",
            show_side_panel=self.config.show_side_panel,
            side_panel_width=self.config.side_panel_width
        )

        # Create dialog manager
        self.dialog_manager = DialogManager(self.main_layout)

        # Create key bindings
        self.key_bindings = GlobalKeyBindings(
            self.main_layout,
            self.dialog_manager
        )

        # Create command processor
        self.command_processor = CommandProcessor(
            self.main_layout,
            self.agent_session
        )

        # Create prompt_toolkit Application with proper key bindings
        self.app = Application(
            layout=self.main_layout.get_layout(),
            key_bindings=self.key_bindings.get_key_bindings(),
            style=get_safe_theme(self.config.theme),
            mouse_support=self.config.mouse_support,
            full_screen=True,
            enable_page_navigation_bindings=False,  # Disable conflicting built-in bindings
            include_default_pygments_style=False,  # Disable default styling that might include bindings
        )

        # Track interaction counter
        self.interaction_counter = 0

    def _handle_user_input(self, user_input: str):
        """
        Handle user input from the input area.

        Args:
            user_input: User's input string
        """
        user_input = user_input.strip()
        if not user_input:
            return

        # Check if it's a command
        if user_input.startswith('/'):
            # Process command
            handled = self.command_processor.process_command(user_input)
            if handled:
                return

        # If we have an agent, process through it
        if self.agent_session:
            self._process_agent_input(user_input)
        else:
            # No agent available
            self.main_layout.add_system_message(
                "Agent not initialized. Please initialize the agent first.",
                "error"
            )

    def _process_agent_input(self, user_input: str):
        """
        Process input through the agent.

        Args:
            user_input: User's input
        """
        self.interaction_counter += 1
        interaction_id = self.interaction_counter

        # Show processing state
        self.main_layout.set_processing_state(True, "Processing...")

        try:
            # Add user input to conversation immediately
            self.main_layout.add_interaction(
                interaction_id=interaction_id,
                user_input=user_input,
                agent_response="",  # Will be updated
                expanded=True  # Start expanded for active interaction
            )

            # Process through agent session
            if hasattr(self.agent_session, 'process_input'):
                # This is a simplified version - in reality this should be async
                result = self.agent_session.process_input(user_input)
                agent_response = result.get('agent_response', 'No response')

                # Update the conversation with the response
                self.main_layout.conversation_area.entries[-1].agent_response = agent_response

                # TODO: Get thoughts/actions and tool executions from agent
                # For now, add placeholder data
                thoughts_actions = "Thought: Processing user request...\nAction: Analyzing input..."
                tool_executions = []
                memory_injections = []

                # Update the interaction
                self.main_layout.update_current_interaction(
                    thoughts_actions=thoughts_actions,
                    tool_executions=tool_executions,
                    memory_injections=memory_injections
                )

                # Update metrics
                self._update_metrics()

            else:
                # Mock response for testing
                agent_response = f"I received your message: '{user_input}'. This is a mock response from the TUI."

                # Update conversation
                last_entry = self.main_layout.conversation_area.entries[-1]
                last_entry.agent_response = agent_response

                # Invalidate to refresh display
                self.main_layout.invalidate()

        except Exception as e:
            # Handle errors
            self.main_layout.add_system_message(f"Error processing input: {e}", "error")

        finally:
            # Clear processing state
            self.main_layout.set_processing_state(False)

    def _update_metrics(self):
        """Update metrics in the side panel."""
        metrics = {
            'base_tokens': 1500,  # Mock data
            'enhanced_tokens': 2200,
            'max_tokens': self.config.model.split(':')[-1] if ':' in self.config.model else 8192,
            'react_time': 2.5,
            'memory_items_count': 3,
            'interaction_count': self.interaction_counter
        }

        self.main_layout.update_context_metrics(metrics)

    def set_agent(self, agent_session):
        """
        Set the agent session instance.

        Args:
            agent_session: TUIAgentSession instance
        """
        self.agent_session = agent_session
        self.command_processor.agent_cli = agent_session

        # Update agent status
        status = {
            'model': agent_session.config.model,
            'provider': agent_session.config.provider,
            'connected': True,
            'memory_enabled': agent_session.config.enable_memory_tools,
            'tools_count': 1,  # Mock value for now
            'last_update': 'Just now'
        }
        self.main_layout.update_agent_status(status)
        self.main_layout.update_title_info(
            model=agent_session.config.model,
            status="Connected"
        )

        # Update memory info with mock data
        memory_info = {
            'memory_path': agent_session.config.memory_path,
            'working_count': 0,
            'semantic_count': 0,
            'pending_count': 0,
            'document_count': 0,
            'episode_count': 0
        }
        self.main_layout.update_memory_info(memory_info)

        # Update tools info with mock data
        tools = ['list_files', 'mock_tool']
        self.main_layout.update_tools_info(tools)

    def _extract_memory_info(self, memory) -> Dict[str, Any]:
        """Extract memory information for display."""
        info = {
            'memory_path': self.config.memory_path,
            'working_count': 0,
            'semantic_count': 0,
            'pending_count': 0,
            'document_count': 0,
            'episode_count': 0
        }

        try:
            # Working memory
            if hasattr(memory, 'working'):
                if hasattr(memory.working, 'items'):
                    info['working_count'] = len(memory.working.items)
                elif hasattr(memory.working, 'memories'):
                    info['working_count'] = len(memory.working.memories)

            # Semantic memory
            if hasattr(memory, 'semantic'):
                if hasattr(memory.semantic, 'facts'):
                    info['semantic_count'] = len(memory.semantic.facts)
                if hasattr(memory.semantic, 'pending_facts'):
                    info['pending_count'] = len(memory.semantic.pending_facts)

            # Document memory
            if hasattr(memory, 'document'):
                try:
                    doc_summary = memory.document.get_document_summary()
                    info['document_count'] = doc_summary.get('total_documents', 0)
                except:
                    pass

            # Episodic memory
            if hasattr(memory, 'episodic'):
                if hasattr(memory.episodic, 'episodes'):
                    info['episode_count'] = len(memory.episodic.episodes)

        except Exception:
            # Ignore errors in memory introspection
            pass

        return info

    async def run_async(self):
        """Run the application asynchronously."""
        self.running = True

        # Show welcome message
        self.main_layout.add_system_message(
            "Welcome to AbstractMemory TUI! Type your message below or use /help for commands.",
            "info"
        )

        # Focus input area - ensure it gets focus on startup
        try:
            from prompt_toolkit.application import get_app
            # Give the layout time to initialize, then focus
            get_app().invalidate()  # Force a redraw first
            self.main_layout.focus_input()
        except:
            # Fallback - try to focus after app starts
            self.main_layout.focus_input()

        try:
            # Run the application
            await self.app.run_async()
        finally:
            self.running = False

    def run(self):
        """Run the application synchronously."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            self.main_layout.add_system_message("Interrupted by user.", "info")
        except Exception as e:
            self.main_layout.add_system_message(f"Application error: {e}", "error")

    def shutdown(self):
        """Shutdown the application."""
        self.running = False
        if self.app.is_running:
            self.app.exit()

    def add_system_message(self, message: str, message_type: str = "info"):
        """Add a system message to the conversation."""
        self.main_layout.add_system_message(message, message_type)

    def update_theme(self, theme_name: str):
        """Update the application theme."""
        self.config.theme = theme_name
        self.app.style = get_safe_theme(theme_name)

    def save_config(self):
        """Save current configuration."""
        config_path = Path(self.config.memory_path) / "tui_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.save_to_file(config_path)

    def load_config(self):
        """Load configuration from file."""
        config_path = Path(self.config.memory_path) / "tui_config.json"
        if config_path.exists():
            self.config = TUIConfig.load_from_file(config_path)

    def get_stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        stats = self.main_layout.get_conversation_stats()
        stats.update({
            'running': self.running,
            'theme': self.config.theme,
            'agent_initialized': self.agent_session is not None,
            'interaction_counter': self.interaction_counter
        })
        return stats