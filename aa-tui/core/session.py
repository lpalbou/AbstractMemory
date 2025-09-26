"""Session integration with AbstractMemory."""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Add the parent directory to sys.path to import nexus
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from nexus import AutonomousAgentCLI, AgentConfig, ReActConfig
    NEXUS_AVAILABLE = True
except ImportError:
    NEXUS_AVAILABLE = False
    AutonomousAgentCLI = None
    AgentConfig = None
    ReActConfig = None


class TUIAgentSession:
    """Wrapper for AutonomousAgentCLI to work with TUI."""

    def __init__(self, config):
        """
        Initialize the TUI agent session.

        Args:
            config: TUIConfig instance
        """
        self.config = config
        self.agent_cli = None
        self.initialized = False

    def initialize(self) -> bool:
        """
        Initialize the agent session.

        Returns:
            True if successful, False otherwise
        """
        if not NEXUS_AVAILABLE:
            return False

        try:
            # Create agent config from TUI config
            react_config = ReActConfig(
                context_tokens=self.config.context_tokens,
                max_iterations=self.config.max_iterations,
                include_memory_in_react=self.config.include_memory_in_react,
                observation_display_limit=self.config.observation_display_limit,
                save_scratchpad=self.config.save_scratchpad,
                scratchpad_confidence=self.config.scratchpad_confidence
            )

            agent_config = AgentConfig(
                model=self.config.model,
                provider=self.config.provider,
                memory_path=self.config.memory_path,
                identity_name=self.config.identity_name,
                enable_tools=self.config.enable_tools,
                enable_memory_tools=self.config.enable_memory_tools,
                timeout=self.config.timeout,
                react_config=react_config
            )

            # Create agent CLI
            self.agent_cli = AutonomousAgentCLI(agent_config)

            # Setup agent
            success = self.agent_cli.setup_agent()
            if success:
                self.initialized = True
                return True

        except Exception as e:
            print(f"Failed to initialize agent: {e}")

        return False

    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input through the agent.

        Args:
            user_input: User's input string

        Returns:
            Dictionary with response data
        """
        if not self.initialized or not self.agent_cli:
            return {
                'error': 'Agent not initialized',
                'agent_response': 'Agent is not available.'
            }

        try:
            # Process through agent
            agent_response = self.agent_cli.process_user_input(user_input)

            # Extract additional information
            result = {
                'agent_response': agent_response,
                'thoughts_actions': getattr(self.agent_cli, 'last_thoughts_actions', None),
                'tool_executions': getattr(self.agent_cli, 'last_tool_executions', []),
                'memory_injections': getattr(self.agent_cli, 'last_memory_items', []),
                'context_info': {
                    'base_tokens': getattr(self.agent_cli, 'last_context_tokens', 0),
                    'enhanced_tokens': getattr(self.agent_cli, 'last_enhanced_tokens', 0),
                    'react_time': getattr(self.agent_cli, 'last_react_total_time', 0.0),
                    'interaction_id': getattr(self.agent_cli, 'interaction_counter', 0)
                }
            }

            return result

        except Exception as e:
            return {
                'error': str(e),
                'agent_response': f'Error processing input: {e}'
            }

    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information from the agent."""
        if not self.initialized or not self.agent_cli:
            return {}

        try:
            memory = self.agent_cli.session.memory
            info = {
                'memory_path': self.config.memory_path,
                'working_count': 0,
                'semantic_count': 0,
                'pending_count': 0,
                'document_count': 0,
                'episode_count': 0
            }

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

            return info

        except Exception:
            return {}

    def get_tools_info(self) -> list:
        """Get available tools information."""
        if not self.initialized or not self.agent_cli:
            return []

        try:
            if self.agent_cli.session and hasattr(self.agent_cli.session, 'tools'):
                return [getattr(tool, '__name__', str(tool)) for tool in self.agent_cli.session.tools]
        except Exception:
            pass

        return []

    def get_status(self) -> Dict[str, Any]:
        """Get agent status information."""
        if not self.initialized or not self.agent_cli:
            return {
                'model': 'Unknown',
                'provider': 'Unknown',
                'connected': False,
                'memory_enabled': False,
                'tools_count': 0,
                'last_update': 'Never'
            }

        try:
            tools_count = len(self.get_tools_info())
            return {
                'model': self.config.model,
                'provider': self.config.provider,
                'connected': True,
                'memory_enabled': self.config.enable_memory_tools,
                'tools_count': tools_count,
                'last_update': 'Connected'
            }
        except Exception:
            return {
                'model': self.config.model,
                'provider': self.config.provider,
                'connected': False,
                'memory_enabled': False,
                'tools_count': 0,
                'last_update': 'Error'
            }

    def shutdown(self):
        """Shutdown the agent session."""
        if self.agent_cli:
            # Save any pending data
            try:
                if hasattr(self.agent_cli, 'save_chat_history'):
                    self.agent_cli.save_chat_history()
            except Exception:
                pass

        self.initialized = False