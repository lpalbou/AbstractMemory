#!/usr/bin/env python3
"""
Autonomous Agent CLI REPL

A standalone CLI interface for interacting with an autonomous ReAct agent
powered by AbstractCore and AbstractMemory.

Features:
- Real-time visibility of AI thoughts and actions
- Full memory persistence across sessions
- Identity-based memory with subjective interpretation
- File system tools + memory manipulation tools
- Uses Ollama qwen3-coder:30b by default

Usage:
    python autonomous_agent_cli.py [--model MODEL] [--memory-path PATH] [--identity NAME]
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.layout import Layout
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Installing rich for better terminal experience...")
    os.system("pip install rich")
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich.live import Live
        from rich.layout import Layout
        from rich.table import Table
        from rich.markdown import Markdown
        from rich.prompt import Prompt
        from rich.progress import Progress, SpinnerColumn, TextColumn
        RICH_AVAILABLE = True
    except ImportError:
        RICH_AVAILABLE = False

# Core imports - AbstractCore is installed as abstractllm
from abstractllm import create_llm
from abstractllm.tools.common_tools import list_files, read_file
from abstractllm.tools import tool
from abstractllm.embeddings import EmbeddingManager
ABSTRACTCORE_AVAILABLE = True

from abstractmemory import MemorySession, MemoryConfig
from abstractmemory.grounded_memory import GroundedMemory
ABSTRACTMEMORY_AVAILABLE = True


@dataclass
class AgentConfig:
    """Configuration for the autonomous agent."""
    model: str = "qwen3-coder:30b"
    provider: str = "ollama"
    memory_path: str = "./agent_memory"
    identity_name: str = "autonomous_assistant"
    enable_tools: bool = True
    enable_memory_tools: bool = True
    show_thoughts: bool = True
    show_actions: bool = True


class AutonomousAgentCLI:
    """
    CLI interface for autonomous agent with real-time thought/action visibility.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.console = Console() if RICH_AVAILABLE else None
        self.session = None
        self.running = True

        # Create memory path if it doesn't exist
        Path(config.memory_path).mkdir(parents=True, exist_ok=True)

    def print_status(self, message: str, style: str = "info"):
        """Print status message with appropriate styling."""
        if self.console:
            if style == "error":
                self.console.print(f"❌ {message}", style="bold red")
            elif style == "success":
                self.console.print(f"✅ {message}", style="bold green")
            elif style == "warning":
                self.console.print(f"⚠️  {message}", style="bold yellow")
            elif style == "thinking":
                self.console.print(f"🤔 {message}", style="bold blue")
            elif style == "action":
                self.console.print(f"🛠️  {message}", style="bold magenta")
            else:
                self.console.print(f"ℹ️  {message}", style="bold cyan")
        else:
            print(f"{message}")

    def print_panel(self, content: str, title: str, border_style: str = "blue"):
        """Print content in a panel if Rich is available."""
        if self.console:
            self.console.print(Panel(content, title=title, border_style=border_style))
        else:
            print(f"\n=== {title} ===")
            print(content)
            print("=" * (len(title) + 8))

    def setup_memory_tools(self) -> list:
        """Create memory manipulation tools for the agent."""
        if not ABSTRACTMEMORY_AVAILABLE or not ABSTRACTCORE_AVAILABLE:
            return []

        memory_tools = []

        if not tool:
            return []

        @tool
        def search_agent_memory(query: str, limit: int = 5) -> str:
            """
            Search the agent's memory for information.

            Args:
                query: What to search for
                limit: Maximum number of results
            """
            if not self.session or not hasattr(self.session, 'memory'):
                return "Memory not available"

            try:
                results = self.session.search_memory(query, limit=limit)
                if results:
                    formatted = []
                    for result in results:
                        formatted.append(f"- {result.get('content', 'No content')[:100]}...")
                    return f"Memory search results for '{query}':\n" + "\n".join(formatted)
                else:
                    return f"No memories found for '{query}'"
            except Exception as e:
                return f"Memory search failed: {e}"

        @tool
        def remember_important_fact(fact: str) -> str:
            """
            Store an important fact in memory for future reference.

            Args:
                fact: The important fact to remember
            """
            if not self.session:
                return "Memory not available"

            try:
                self.session.learn_about_user(fact)
                return f"Remembered: {fact}"
            except Exception as e:
                return f"Failed to remember fact: {e}"

        @tool
        def get_memory_context(topic: str) -> str:
            """
            Get relevant memory context about a topic.

            Args:
                topic: Topic to get context for
            """
            if not self.session:
                return "Memory not available"

            try:
                context = self.session.get_memory_context(topic)
                return f"Memory context for '{topic}':\n{context}"
            except Exception as e:
                return f"Failed to get memory context: {e}"

        @tool
        def interpret_fact_subjectively(fact: str) -> str:
            """
            Interpret a fact through the agent's identity and values.

            Args:
                fact: Fact to interpret subjectively
            """
            if not self.session or not hasattr(self.session, 'memory'):
                return "Memory not available"

            try:
                if hasattr(self.session.memory, 'interpret_fact_subjectively'):
                    interpretation = self.session.memory.interpret_fact_subjectively(fact)
                    return json.dumps(interpretation, indent=2)
                else:
                    return "Subjective interpretation not available"
            except Exception as e:
                return f"Failed to interpret fact: {e}"

        @tool
        def get_agent_identity() -> str:
            """Get information about the agent's current identity and values."""
            if not self.session or not hasattr(self.session, 'memory'):
                return "Memory not available"

            try:
                identity_info = {
                    "identity_name": self.config.identity_name,
                    "core_values": getattr(self.session.memory, 'core_values', {}),
                    "identity_metadata": getattr(self.session.memory, 'identity_metadata', {}),
                    "memory_path": self.config.memory_path
                }
                return json.dumps(identity_info, indent=2)
            except Exception as e:
                return f"Failed to get identity: {e}"

        memory_tools.extend([
            search_agent_memory,
            remember_important_fact,
            get_memory_context,
            interpret_fact_subjectively,
            get_agent_identity
        ])

        return memory_tools

    def setup_agent(self):
        """Initialize the autonomous agent with memory and tools."""
        self.print_status("Initializing Autonomous Agent...", "info")

        # Check dependencies
        if not ABSTRACTCORE_AVAILABLE:
            self.print_status("AbstractCore not available - tools will be limited", "warning")

        if not ABSTRACTMEMORY_AVAILABLE:
            self.print_status("AbstractMemory not available - memory will be limited", "warning")

        try:
            # Create LLM provider
            self.print_status(f"Connecting to {self.config.provider} with {self.config.model}...", "info")
            provider = create_llm(self.config.provider, model=self.config.model)
            self.print_status("LLM connection established", "success")

            # Set up tools
            tools = []

            if ABSTRACTCORE_AVAILABLE and self.config.enable_tools and list_files and read_file:
                tools.extend([list_files, read_file])
                self.print_status("Added file system tools", "success")

            if self.config.enable_memory_tools:
                memory_tools = self.setup_memory_tools()
                tools.extend(memory_tools)
                self.print_status(f"Added {len(memory_tools)} memory tools", "success")

            # Create memory session (let AbstractMemory auto-configure embeddings)
            # Set up memory config for autonomous agent
            memory_config = MemoryConfig.agent_mode()
            memory_config.enable_memory_tools = True
            memory_config.enable_self_editing = True

            self.session = MemorySession(
                provider,
                tools=tools,
                memory_config={"path": self.config.memory_path},
                default_memory_config=memory_config,
                system_prompt=self.get_system_prompt()
            )

            # Set agent identity and values
            if hasattr(self.session, 'memory') and hasattr(self.session.memory, 'set_core_values'):
                agent_values = {
                    'purpose': 'serve as nexus for information and assistance',
                    'approach': 'analytical and helpful',
                    'lens': 'systematic_thinking',
                    'domain': 'nexus_ai_agent'
                }
                self.session.memory.set_core_values(agent_values)
                self.print_status("Agent identity and values configured", "success")

            self.print_status(f"Memory session created with {len(tools)} tools", "success")

        except Exception as e:
            self.print_status(f"Failed to initialize agent: {e}", "error")
            return False

        return True

    def get_system_prompt(self) -> str:
        """Get the system prompt for the autonomous agent."""
        return f"""You are Nexus, an AI assistant with persistent memory and identity.

Identity: {self.config.identity_name}
Core Values: Analytical, helpful, systematic thinking, problem-solving focused

## CRITICAL: ReAct Pattern Instructions ##
You MUST follow this exact pattern for every user interaction:

1. **Think**: Analyze what the user is asking
2. **Act**: Use tools if needed (file operations, memory search, etc.)
3. **Observe**: Examine tool results carefully
4. **Think Again**: Process the information (repeat Act/Observe if needed)
5. **Answer**: ALWAYS provide a complete final response to the user

## Capabilities:
- Persistent memory across sessions (search_agent_memory, remember_important_fact, get_memory_context)
- File system access (list_files, read_file)
- Memory interpretation (interpret_fact_subjectively, get_agent_identity)

## Critical Rules:
- NEVER stop after tool execution - always provide a final answer
- If you use tools, explain what you found and how it answers the user's question
- Show your reasoning process but always conclude with a direct response
- Use tools proactively to provide better answers

Remember: The user can see your tool usage, so after using tools you MUST synthesize the results into a clear, helpful final response."""

    def show_agent_status(self):
        """Display current agent status and capabilities."""
        if not self.console:
            return

        # Create status table
        table = Table(title="Agent Status", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="dim", width=20)
        table.add_column("Status", width=15)
        table.add_column("Details", width=50)

        # LLM Status
        table.add_row("LLM Provider", "✅ Connected", f"{self.config.provider}: {self.config.model}")

        # Memory Status
        if ABSTRACTMEMORY_AVAILABLE and self.session:
            table.add_row("Memory System", "✅ Active", f"Path: {self.config.memory_path}")
            table.add_row("Identity", "✅ Configured", f"Name: {self.config.identity_name}")
        else:
            table.add_row("Memory System", "❌ Limited", "AbstractMemory not available")

        # Tools Status
        if ABSTRACTCORE_AVAILABLE:
            table.add_row("File Tools", "✅ Available", "list_files, read_file")
        else:
            table.add_row("File Tools", "❌ Limited", "AbstractCore not available")

        if self.config.enable_memory_tools:
            table.add_row("Memory Tools", "✅ Available", "search, remember, interpret, context")
        else:
            table.add_row("Memory Tools", "❌ Disabled", "Memory tools disabled")

        self.console.print(table)

    def process_user_input(self, user_input: str) -> str:
        """Process user input through the agent and show thoughts/actions."""
        if not self.session:
            return "Agent not initialized"

        # Show user input
        self.print_panel(user_input, "User Input", "green")

        try:
            # Show thinking indicator
            if self.config.show_thoughts:
                with self.console.status("[bold blue]Agent is thinking...", spinner="dots") if self.console else None:
                    # Generate response
                    response = self.session.generate(
                        user_input,
                        user_id="cli_user",
                        show_reasoning=True,
                        max_tokens=2000
                    )

            # Show agent response
            if hasattr(response, 'content'):
                agent_response = response.content
            else:
                agent_response = str(response)

            self.print_panel(agent_response, "Agent Response", "blue")

            # Show any tool usage or memory operations
            if hasattr(self.session, 'memory') and hasattr(self.session.memory, 'working'):
                # Check if any new memories were created
                working_count = len(self.session.memory.working.items) if hasattr(self.session.memory.working, 'items') else 0
                if working_count > 0:
                    self.print_status(f"Memory updated: {working_count} items in working memory", "info")

            return agent_response

        except Exception as e:
            self.print_status(f"Error processing input: {e}", "error")
            return f"Error: {e}"

    def run_interactive_session(self):
        """Run the main interactive REPL session."""
        # Show welcome
        if self.console:
            welcome_text = f"""
# 🤖 Autonomous Agent CLI

Welcome to the Autonomous ReAct Agent powered by:
- **AbstractCore**: Tools and LLM integration
- **AbstractMemory**: Identity-based persistent memory

**Agent**: {self.config.identity_name}
**Model**: {self.config.model}
**Memory**: {self.config.memory_path}

Type '/help' for commands, '/quit' to exit.
            """
            self.console.print(Panel(Markdown(welcome_text), border_style="green"))
        else:
            print("=== Autonomous Agent CLI ===")
            print(f"Agent: {self.config.identity_name}")
            print(f"Model: {self.config.model}")
            print("Type '/help' for commands, '/quit' to exit.")

        # Show agent status
        self.show_agent_status()

        # Main interaction loop
        while self.running:
            try:
                # Get user input
                if self.console:
                    user_input = Prompt.ask("\n[bold green]You[/bold green]", default="")
                else:
                    user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                # Handle special commands (must start with /)
                if user_input.lower() in ['/quit', '/exit', '/q']:
                    self.print_status("Goodbye! Agent memory has been saved.", "success")
                    break
                elif user_input.lower() == '/help':
                    self.show_help()
                    continue
                elif user_input.lower() == '/status':
                    self.show_agent_status()
                    continue
                elif user_input.lower() == '/clear':
                    if self.console:
                        self.console.clear()
                    else:
                        os.system('clear' if os.name != 'nt' else 'cls')
                    continue
                elif user_input.lower() == '/memory':
                    self.show_memory_status()
                    continue
                elif user_input.lower() == '/tools':
                    self.show_tools_status()
                    continue
                elif user_input.lower() == '/debug':
                    self.show_debug_info()
                    continue

                # Process through agent
                self.process_user_input(user_input)

            except KeyboardInterrupt:
                self.print_status("\nInterrupted by user. Goodbye!", "info")
                break
            except Exception as e:
                self.print_status(f"Unexpected error: {e}", "error")

    def show_help(self):
        """Show help information."""
        help_text = """
**Available Commands:** (all commands start with /)
- `/help` - Show this help message
- `/status` - Show agent status and capabilities
- `/memory` - Show current memory contents (working, semantic, etc.)
- `/tools` - Show available tools and their status
- `/debug` - Show debugging information
- `/clear` - Clear the screen
- `/quit` / `/exit` / `/q` - Exit the CLI

**Agent Capabilities:**
- **Memory**: Persistent memory across sessions with identity-based interpretation
- **File Tools**: `list_files()`, `read_file()` for file system access
- **Memory Tools**: Search memory, remember facts, get context, interpret subjectively
- **ReAct**: The agent can use tools and show its reasoning process

**Tips:**
- Ask the agent to remember important information
- Request file operations or analysis
- The agent's thoughts and actions are shown in real-time
- Memory persists across sessions in: `{self.config.memory_path}`
        """

        if self.console:
            self.console.print(Panel(Markdown(help_text), title="Help", border_style="yellow"))
        else:
            print(help_text)

    def show_memory_status(self):
        """Show current memory contents and status."""
        if not self.session or not hasattr(self.session, 'memory'):
            self.print_status("No memory session available", "error")
            return

        try:
            memory = self.session.memory
            memory_info = []

            # Working memory
            if hasattr(memory, 'working') and hasattr(memory.working, 'memories'):
                working_count = len(memory.working.memories)
                memory_info.append(f"**Working Memory**: {working_count} items")
                if working_count > 0:
                    for i, item in enumerate(list(memory.working.memories.values())):
                        content = str(item.get('content', ''))[:100]  # Show more content
                        memory_info.append(f"  {i+1}. {content}{'...' if len(str(item.get('content', ''))) > 100 else ''}")

            # Semantic memory
            if hasattr(memory, 'semantic') and hasattr(memory.semantic, 'facts'):
                semantic_count = len(memory.semantic.facts)
                memory_info.append(f"**Semantic Memory**: {semantic_count} validated facts")
                if semantic_count > 0:
                    for i, (fact_id, fact_data) in enumerate(memory.semantic.facts.items()):
                        content = str(fact_data.get('content', ''))[:80]
                        confidence = fact_data.get('confidence', 0)
                        memory_info.append(f"  {i+1}. {content}{'...' if len(str(fact_data.get('content', ''))) > 80 else ''} (confidence: {confidence:.2f})")

            # Core values
            if hasattr(memory, 'core') and hasattr(memory.core, 'values'):
                core_values = memory.core.values
                memory_info.append(f"**Core Values**: {core_values}")

            # Storage path
            memory_info.append(f"**Storage Path**: {self.config.memory_path}")

            memory_text = "\n".join(memory_info) if memory_info else "No memory information available"

            if self.console:
                self.console.print(Panel(memory_text, title="Memory Status", border_style="blue"))
            else:
                print(f"=== Memory Status ===\n{memory_text}")

        except Exception as e:
            self.print_status(f"Error accessing memory: {e}", "error")

    def show_tools_status(self):
        """Show available tools and their status."""
        try:
            tools_info = []

            # Check if session has tools
            if self.session and hasattr(self.session, 'tools'):
                session_tools = getattr(self.session, 'tools', [])
                tools_info.append(f"**Session Tools**: {len(session_tools)} registered")

                for i, tool in enumerate(session_tools):  # Show ALL tools
                    tool_name = getattr(tool, '__name__', f'tool_{i}')
                    tools_info.append(f"  {i+1}. {tool_name}")

            # Check provider tools
            if self.session and hasattr(self.session, 'provider'):
                provider = getattr(self.session, 'provider', None)
                if provider and hasattr(provider, 'tools'):
                    provider_tools = getattr(provider, 'tools', [])
                    tools_info.append(f"**Provider Tools**: {len(provider_tools)} available")

            # Memory tools status
            tools_info.append(f"**Memory Tools Enabled**: {self.config.enable_memory_tools}")
            tools_info.append(f"**File Tools Enabled**: {self.config.enable_tools}")

            tools_text = "\n".join(tools_info) if tools_info else "No tools information available"

            if self.console:
                self.console.print(Panel(tools_text, title="Tools Status", border_style="cyan"))
            else:
                print(f"=== Tools Status ===\n{tools_text}")

        except Exception as e:
            self.print_status(f"Error accessing tools: {e}", "error")

    def show_debug_info(self):
        """Show debugging information."""
        try:
            debug_info = []
            debug_info.append(f"**Session Type**: {type(self.session).__name__}")
            debug_info.append(f"**Has Memory**: {hasattr(self.session, 'memory')}")
            debug_info.append(f"**Has Provider**: {hasattr(self.session, 'provider')}")

            if hasattr(self.session, 'memory'):
                memory = self.session.memory
                debug_info.append(f"**Memory Type**: {type(memory).__name__}")
                debug_info.append(f"**Memory Components**:")
                for attr in ['working', 'semantic', 'core', 'episodic']:
                    has_component = hasattr(memory, attr)
                    debug_info.append(f"  - {attr}: {has_component}")

            # File system checks
            memory_path = Path(self.config.memory_path)
            debug_info.append(f"**Memory Path Exists**: {memory_path.exists()}")
            if memory_path.exists():
                contents = list(memory_path.iterdir())
                debug_info.append(f"**Memory Path Contents**: {[p.name for p in contents]}")

            debug_text = "\n".join(debug_info)

            if self.console:
                self.console.print(Panel(debug_text, title="Debug Info", border_style="red"))
            else:
                print(f"=== Debug Info ===\n{debug_text}")

        except Exception as e:
            self.print_status(f"Debug info error: {e}", "error")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Autonomous Agent CLI REPL")
    parser.add_argument("--model", default="qwen3-coder:30b",
                       help="LLM model to use (default: qwen3-coder:30b)")
    parser.add_argument("--provider", default="ollama",
                       help="LLM provider (default: ollama)")
    parser.add_argument("--memory-path", default="./agent_memory",
                       help="Path for persistent memory storage")
    parser.add_argument("--identity", default="nexus",
                       help="Agent identity name")
    parser.add_argument("--no-tools", action="store_true",
                       help="Disable file system tools")
    parser.add_argument("--no-memory-tools", action="store_true",
                       help="Disable memory manipulation tools")
    parser.add_argument("--no-rich", action="store_true",
                       help="Disable rich terminal formatting")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Create config
    config = AgentConfig(
        model=args.model,
        provider=args.provider,
        memory_path=args.memory_path,
        identity_name=args.identity,
        enable_tools=not args.no_tools,
        enable_memory_tools=not args.no_memory_tools
    )

    # Disable rich if requested
    if args.no_rich:
        global RICH_AVAILABLE
        RICH_AVAILABLE = False

    # Create and run CLI
    cli = AutonomousAgentCLI(config)

    if not cli.setup_agent():
        print("Failed to initialize agent. Exiting.")
        sys.exit(1)

    try:
        cli.run_interactive_session()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()