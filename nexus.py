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
try:
    from abstractllm.embeddings import EmbeddingManager
    EMBEDDING_MANAGER_AVAILABLE = True
except ImportError:
    EmbeddingManager = None
    EMBEDDING_MANAGER_AVAILABLE = False
ABSTRACTCORE_AVAILABLE = True

from abstractmemory import MemorySession, MemoryConfig
from abstractmemory.grounded_memory import GroundedMemory
ABSTRACTMEMORY_AVAILABLE = True


@dataclass
class ReActConfig:
    """
    Configuration for ReAct reasoning loop.

    ReAct operates as an ISOLATED BRANCH from main conversation:
    - Limited context prevents accumulation
    - Scratchpad saved separately
    - Only Final Answer merges back
    """
    # Context limits
    context_tokens: int = 2000      # Tokens from main conversation
    max_iterations: int = 25        # Maximum reasoning cycles

    # Memory injection during ReAct
    include_memory_in_react: bool = False  # Disable memory injection in ReAct cycles

    # Observation limits (for display only - full content sent to LLM)
    observation_display_limit: int = 500   # Characters for user display

    # Scratchpad saving
    save_scratchpad: bool = True    # Save reasoning steps to episodic memory
    scratchpad_confidence: float = 0.8  # Confidence for scratchpad entries


@dataclass
class AgentConfig:
    """Configuration for the autonomous agent."""
    model: str = "qwen3-coder:30b"
    provider: str = "ollama"
    memory_path: str = "./agent_memory"
    identity_name: str = "autonomous_assistant"
    enable_tools: bool = True
    enable_memory_tools: bool = True
    timeout: float = 7200.0  # HTTP timeout in seconds (2 hours)
    react_config: ReActConfig = None  # ReAct reasoning configuration

    def __post_init__(self):
        """Initialize default ReAct configuration if not provided."""
        if self.react_config is None:
            self.react_config = ReActConfig()


class AutonomousAgentCLI:
    """
    CLI interface for autonomous agent with real-time thought/action visibility.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.console = Console() if RICH_AVAILABLE else None
        self.session = None
        self.running = True

        # Context tracking
        self.last_context_size = 0
        self.last_context_tokens = 0
        self.last_final_answer_context = ""  # Store verbatim context for /context command
        self.last_react_total_time = 0.0  # Total ReAct processing time
        self.last_react_initial_tokens = 0  # Initial context tokens for ReAct
        self.model_max_tokens = self._get_model_max_tokens()

        # Create memory path if it doesn't exist
        Path(config.memory_path).mkdir(parents=True, exist_ok=True)

    def _get_model_max_tokens(self) -> int:
        """Get maximum tokens for current model."""
        model = self.config.model.lower()

        # Common model token limits
        if 'qwen3-coder:30b' in model:
            return 32768
        elif 'qwen' in model:
            return 8192  # Conservative default for Qwen models
        elif 'llama' in model:
            return 4096  # Conservative default for Llama models
        elif 'gpt-4' in model:
            return 128000
        elif 'gpt-3.5' in model:
            return 16385
        else:
            return 4096  # Conservative default

    def set_model_max_tokens(self, max_tokens: int):
        """Update the model's max tokens setting."""
        self.model_max_tokens = max_tokens
        self.print_status(f"Model max_tokens updated to {max_tokens:,}", "success")

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    def _format_cycle_status(self, cycle_info: dict) -> str:
        """Format condensed cycle status line."""
        # Base: 🔄 Cycle 2/25 | 📊 Context: 26,429 chars
        status = f"🔄 Cycle {cycle_info['cycle_num']}/{cycle_info['max_cycles']} | 📊 Context: {cycle_info['context_chars']:,} chars"

        # Add tool info if available: | 🔧 Tool: read_file(...) ✅
        if cycle_info['tool_name']:
            tool_part = f" | 🔧 {cycle_info['tool_name']}({cycle_info['tool_params']}) {cycle_info['tool_status']}"
            status += tool_part

        # Add generation time: | 34.6s
        status += f" | {cycle_info['generation_time']:.1f}s"

        return status

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
                # Check for similar facts to prevent duplication
                if hasattr(self.session, 'memory') and hasattr(self.session.memory, 'semantic'):
                    # Check pending facts for similarity
                    fact_lower = fact.lower()
                    for pending_fact in self.session.memory.semantic.pending_facts:
                        if self._facts_are_similar(fact_lower, pending_fact):
                            return f"Similar fact already exists: {pending_fact[:100]}..."

                    # Check validated facts for similarity
                    for fact_id, fact_data in self.session.memory.semantic.facts.items():
                        existing_fact = str(fact_data.get('content', '')).lower()
                        if self._facts_are_similar(fact_lower, existing_fact):
                            return f"Similar fact already validated: {existing_fact[:100]}..."

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

        @tool
        def search_documents(query: str, limit: int = 5) -> str:
            """
            Search stored documents using semantic and keyword search.

            Args:
                query: Search query
                limit: Maximum number of documents to return
            """
            if not self.session:
                return "Memory not available"

            try:
                documents = self.session.memory.search_documents(query, limit)
                if not documents:
                    return f"No documents found for query: '{query}'"

                results = [f"Found {len(documents)} document(s):"]
                for i, doc in enumerate(documents, 1):
                    filepath = doc.get('filepath', 'unknown')
                    file_type = doc.get('file_type', 'unknown')
                    access_count = doc.get('access_count', 0)
                    content_preview = str(doc.get('content', ''))[:150]

                    results.append(f"\n{i}. **{filepath}** ({file_type})")
                    results.append(f"   Accessed: {access_count} times")
                    results.append(f"   Preview: {content_preview}{'...' if len(str(doc.get('content', ''))) > 150 else ''}")

                return "\n".join(results)
            except Exception as e:
                return f"Failed to search documents: {e}"

        @tool
        def get_document_summary() -> str:
            """Get summary of all stored documents."""
            if not self.session:
                return "Memory not available"

            try:
                summary = self.session.memory.get_document_summary()

                if summary.get('total_documents', 0) == 0:
                    return "No documents stored in memory yet."

                total_docs = summary.get('total_documents', 0)
                total_size = summary.get('total_content_size', 0)
                file_types = summary.get('file_types', {})
                has_semantic = summary.get('has_semantic_search', False)
                chunk_count = summary.get('total_chunks', 0)

                result = [f"Document Memory Summary:"]
                result.append(f"• Total documents: {total_docs}")
                result.append(f"• Total content: {total_size:,} characters")

                if file_types:
                    types_list = [f"{ftype}({count})" for ftype, count in file_types.items()]
                    result.append(f"• File types: {', '.join(types_list)}")

                result.append(f"• Semantic search: {'Enabled' if has_semantic else 'Disabled'}")
                if has_semantic:
                    result.append(f"• Searchable chunks: {chunk_count}")

                most_accessed = summary.get('most_accessed_document')
                if most_accessed:
                    filepath = most_accessed.get('filepath', 'unknown')
                    access_count = most_accessed.get('access_count', 0)
                    result.append(f"• Most accessed: {filepath} ({access_count} times)")

                return "\n".join(result)
            except Exception as e:
                return f"Failed to get document summary: {e}"

        memory_tools.extend([
            search_agent_memory,
            remember_important_fact,
            get_memory_context,
            interpret_fact_subjectively,
            get_agent_identity,
            search_documents,
            get_document_summary
        ])

        return memory_tools

    def _facts_are_similar(self, fact1: str, fact2: str, threshold: float = 0.75) -> bool:
        """Check if two facts are similar to prevent duplication using embeddings when available."""
        try:
            # Try semantic similarity first (if embeddings available)
            if (hasattr(self.session, 'memory') and
                hasattr(self.session.memory, 'semantic') and
                hasattr(self.session.memory.semantic, 'embedding_provider') and
                self.session.memory.semantic.embedding_provider):

                embedding_provider = self.session.memory.semantic.embedding_provider
                try:
                    embedding1 = embedding_provider.generate_embedding(fact1)
                    embedding2 = embedding_provider.generate_embedding(fact2)

                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(embedding1, embedding2)
                    return similarity >= threshold
                except Exception:
                    pass  # Fall back to word overlap

            # Fallback: Simple word overlap similarity (Jaccard index)
            words1 = set(fact1.lower().split())
            words2 = set(fact2.lower().split())

            if not words1 or not words2:
                return False

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            similarity = len(intersection) / len(union) if union else 0
            return similarity >= threshold
        except Exception:
            return False

    def _cosine_similarity(self, vec1: list, vec2: list) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import math
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            return dot_product / (magnitude1 * magnitude2)
        except Exception:
            return 0.0

    def setup_agent(self):
        """Initialize the autonomous agent with memory and tools."""
        self.print_status("Initializing Autonomous Agent...", "info")

        # Check dependencies
        if not ABSTRACTCORE_AVAILABLE:
            self.print_status("AbstractCore not available - tools will be limited", "warning")

        if not ABSTRACTMEMORY_AVAILABLE:
            self.print_status("AbstractMemory not available - memory will be limited", "warning")

        try:
            # Create LLM provider with extended timeout for long conversations
            self.print_status(f"Connecting to {self.config.provider} with {self.config.model}...", "info")
            provider = create_llm(self.config.provider, model=self.config.model, timeout=self.config.timeout)
            self.print_status("LLM connection established", "success")
            self.print_status(f"HTTP timeout set to {self.config.timeout:.0f}s ({self.config.timeout/3600:.1f}h) for long conversations", "info")

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
                memory_config={"path": self.config.memory_path, "semantic_threshold": 1},  # Immediate validation
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

            # Load previous chat history if available
            self.load_chat_history()

        except Exception as e:
            self.print_status(f"Failed to initialize agent: {e}", "error")
            return False

        return True

    def get_system_prompt(self) -> str:
        """Get the system prompt for the autonomous agent."""
        return f"""You are Nexus, an AI assistant with persistent memory and identity.

## CRITICAL: Iterative ReAct Format ##
You are part of an iterative ReAct loop. In each iteration, you should:

1. If you need to use a tool, respond with:
Thought: [what you're thinking]
Action: [exact tool name]
Action Input: {{"parameter": "value"}}

2. If you can answer directly, respond with:
Final Answer: [your complete response]

## Available Tools:
You have access to these tools (use exact names):
- list_files: List directory contents
- read_file: Read file contents
- search_agent_memory: Search your persistent memory
- remember_important_fact: Store important information
- get_memory_context: Get relevant context for a topic

## Important Notes:
- Use JSON format for Action Input: {{"parameter": "value"}}
- You will receive real tool results as "Observation:"
- Continue reasoning until you can provide a Final Answer
- Keep each iteration focused - don't try to do everything at once

## Example Flow:
Thought: I need to check what files are available first.
Action: list_files
Action Input: {{"directory_path": "/some/path"}}

[System will execute tool and provide real Observation]

Thought: Now I can read the specific file I found.
Action: read_file
Action Input: {{"file_path": "/some/path/file.txt"}}

[System will execute tool and provide real Observation]

Thought: Based on the file contents, I now have the information to answer the user's question.
Final Answer: [Write naturally and experientially about what you accomplished and learned. Reflect on the experience, insights gained, and how it changed your understanding. Use "I discovered...", "I realized...", "What struck me was...", "This experience taught me..." - be authentic and reflective, not mechanical.]

## CRITICAL: Final Answer Rules:
- Write in natural, experiential, self-reflective language
- Use phrases like "I discovered...", "I realized...", "What struck me was...", "This experience taught me..."
- Reflect authentically on what you learned and how it changed your understanding
- NEVER copy-paste raw tool results verbatim into Final Answer
- NEVER use mechanical bullet points or step-by-step lists
- Be comprehensive but natural - tell the story of your learning journey
- Show genuine insight and self-awareness about the experience"""

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
        """
        Process user input through ISOLATED ReAct loop with limited context.

        CRITICAL: ReAct operates as a BRANCH from main conversation:
        1. Enters with last 2000 tokens + user query (configurable)
        2. Reasoning scratchpad is separate from main conversation
        3. Only Final Answer merges back to main conversation
        """
        if not self.session:
            return "Agent not initialized"

        # Show user input
        self.print_panel(user_input, "User Input", "green")

        try:
            # === CRITICAL: ReAct Branch Configuration ===
            react_config = self.config.react_config
            REACT_CONTEXT_TOKENS = react_config.context_tokens
            max_iterations = react_config.max_iterations

            # Get LIMITED context from main conversation (not full history)
            main_context = self._get_recent_context(REACT_CONTEXT_TOKENS)
            self.print_status(f"🌿 ReAct branch: {len(main_context):,} chars from main conversation", "info")

            # Start ReAct with FIXED, LIMITED context
            react_initial_context = f"{main_context}\n\nQuestion: {user_input}\n" if main_context else f"Question: {user_input}\n"
            react_scratchpad = []  # Track ALL reasoning steps
            cycle_logs = {}  # For UI display

            # Track initial context and start total timing
            import time
            react_start_time = time.time()
            self.last_react_initial_tokens = self._estimate_tokens(react_initial_context)

            for iteration in range(max_iterations):
                import time
                iter_start_time = time.time()

                # We'll build the cycle status line as we go
                cycle_info = {
                    'cycle_num': iteration + 1,
                    'max_cycles': max_iterations,
                    'context_chars': len(react_initial_context),
                    'tool_name': None,
                    'tool_params': None,
                    'tool_status': None,
                    'generation_time': 0
                }

                # Track context size for monitoring
                self.last_context_size = len(react_initial_context)
                self.last_context_tokens = self._estimate_tokens(react_initial_context)

                # Show cycle start IMMEDIATELY before thinking
                cycle_start_line = f"🔄 Cycle {iteration + 1}/{max_iterations} | 📊 Context: {len(react_initial_context):,} chars"
                self.print_status(cycle_start_line, "info")

                # Generate with LIMITED, CONTROLLED context (with cool spinner!)
                with self.console.status("[bold blue]Agent is thinking...", spinner="dots") if self.console else None:
                    # CRITICAL: Use limited context, configurable memory injection
                    response = self.session.generate(
                        react_initial_context,  # Fixed base context
                        user_id="cli_user",
                        include_memory=react_config.include_memory_in_react  # Configurable memory injection
                    )

                # Get response content and measure timing
                if hasattr(response, 'content'):
                    agent_response = response.content.strip()
                else:
                    agent_response = str(response).strip()

                iter_time = time.time() - iter_start_time
                cycle_info['generation_time'] = iter_time

                # Add to scratchpad for saving
                react_scratchpad.append({
                    'cycle': iteration + 1,
                    'response': agent_response,
                    'timestamp': time.time(),
                    'generation_time': iter_time
                })

                # Check if this is a Final Answer
                if "Final Answer:" in agent_response:
                    # Extract the final answer
                    parts = agent_response.split("Final Answer:", 1)
                    if len(parts) > 1:
                        final_answer = parts[1].strip()

                        # Add any remaining thinking to logs
                        if parts[0].strip():
                            cycle_num = iteration + 1
                            if cycle_num not in cycle_logs:
                                cycle_logs[cycle_num] = []
                            cycle_logs[cycle_num].append(("final_thought", parts[0].strip()))

                        # === CRITICAL: Save scratchpad separately ===
                        if react_config.save_scratchpad:
                            self._save_react_scratchpad(react_scratchpad, user_input, final_answer, react_config)

                        # Calculate total ReAct time and context info
                        self.last_react_total_time = time.time() - react_start_time
                        self.last_final_answer_context = react_initial_context  # Store for /context command
                        final_answer_tokens = self._estimate_tokens(react_initial_context)

                        # Show reasoning process (for testing/debugging)
                        if cycle_logs:
                            formatted_thinking = self.format_cycle_logs(cycle_logs)
                            thoughts_title = f"Thoughts and Actions (Ctx: {self.last_react_initial_tokens} tk; {self.last_react_total_time:.0f}s)"
                            self.print_panel(formatted_thinking, thoughts_title, "yellow")

                        # Show final answer that merges back to main conversation
                        response_title = f"Agent Response (Ctx: {final_answer_tokens} tk; {self.last_react_total_time:.0f}s)"
                        self.print_panel(final_answer, response_title, "blue")
                        self.print_status(f"✅ ReAct branch completed in {iteration + 1} cycles", "success")

                        # === CRITICAL: Only Final Answer returns to main conversation ===
                        return final_answer

                # Parse for Action
                action_match = self.parse_action_from_response(agent_response)
                if action_match:
                    tool_name, tool_input = action_match

                    # Update cycle start line to show tool info
                    params_str = ", ".join([f"{k}={str(v)}" for k, v in tool_input.items()]) if tool_input else "no params"
                    tool_info_line = f"Tool: {tool_name}({params_str})"
                    self.print_status(tool_info_line, "action")

                    # Capture tool info for completion line
                    cycle_info['tool_name'] = tool_name
                    cycle_info['tool_params'] = params_str

                    # Store in cycle logs for display
                    cycle_num = iteration + 1
                    if cycle_num not in cycle_logs:
                        cycle_logs[cycle_num] = []
                    cycle_logs[cycle_num].append(("thought_action", agent_response))

                    # Execute the actual tool
                    tool_result = self.execute_tool(tool_name, tool_input)

                    # Calculate total cycle time (thinking + tool execution)
                    total_cycle_time = time.time() - iter_start_time

                    # Capture tool result status
                    if tool_result.startswith("Error:"):
                        cycle_info['tool_status'] = "❌"
                        # Fix icon duplication - don't include icon in message since print_status adds it
                        completion_line = f"Tool failed ({total_cycle_time:.1f}s)"
                        self.print_status(completion_line, "error")
                    else:
                        cycle_info['tool_status'] = "✅"
                        # Fix icon duplication - don't include icon in message since print_status adds it
                        completion_line = f"Tool executed ({total_cycle_time:.1f}s)"
                        self.print_status(completion_line, "success")

                    # Create observations
                    full_observation = f"Observation: {tool_result}"
                    if len(tool_result) > react_config.observation_display_limit:
                        truncated_result = tool_result[:react_config.observation_display_limit] + "(...)"
                        display_observation = f"Observation: {truncated_result}"
                    else:
                        display_observation = f"Observation: {tool_result}"

                    # Add to cycle logs for display
                    cycle_logs[cycle_num].append(("observation", display_observation))

                    # === CRITICAL: Build up ReAct scratchpad (append, don't replace) ===
                    react_initial_context += agent_response + "\n" + full_observation + "\n"

                else:
                    # No action found - just thinking
                    cycle_num = iteration + 1
                    if cycle_num not in cycle_logs:
                        cycle_logs[cycle_num] = []
                    cycle_logs[cycle_num].append(("thought", agent_response))

                    # Update context with thinking
                    react_initial_context += agent_response + "\n"

                    # Calculate total cycle time and show completion line for thinking-only cycle
                    total_cycle_time = time.time() - iter_start_time
                    completion_line = f"Thinking completed ({total_cycle_time:.1f}s)"
                    self.print_status(completion_line, "info")

                    # Check for completion without "Final Answer:" format
                    # BUT don't exit if response contains tool calls (still in reasoning)
                    if ("Thought:" not in agent_response and "Action:" not in agent_response and
                        "<|tool_call|>" not in agent_response and "tool_call" not in agent_response):
                        if len(agent_response) > 50:  # Substantial response without tool calls
                            self.print_status("✅ Treating substantial response as final answer", "success")

                            # Save scratchpad
                            if react_config.save_scratchpad:
                                self._save_react_scratchpad(react_scratchpad, user_input, agent_response, react_config)

                            # Calculate total ReAct time and context info
                            self.last_react_total_time = time.time() - react_start_time
                            self.last_final_answer_context = react_initial_context  # Store for /context command
                            final_answer_tokens = self._estimate_tokens(react_initial_context)

                            # Show reasoning
                            if cycle_logs:
                                formatted_thinking = self.format_cycle_logs(cycle_logs)
                                thoughts_title = f"Thoughts and Actions (Ctx: {self.last_react_initial_tokens} tk; {self.last_react_total_time:.0f}s)"
                                self.print_panel(formatted_thinking, thoughts_title, "yellow")

                            # Return answer to main conversation
                            response_title = f"Agent Response (Ctx: {final_answer_tokens} tk; {self.last_react_total_time:.0f}s)"
                            self.print_panel(agent_response, response_title, "blue")
                            return agent_response
                        else:
                            self.print_status("⚠️ Agent response doesn't follow ReAct format", "warning")
                            break

            # Loop incomplete
            self.print_status("⚠️ ReAct branch incomplete - max iterations reached", "warning")

            # Save incomplete scratchpad
            incomplete_answer = "ReAct reasoning incomplete - exceeded iteration limit"
            if react_config.save_scratchpad:
                self._save_react_scratchpad(react_scratchpad, user_input, incomplete_answer, react_config)

            # Show incomplete reasoning
            if cycle_logs:
                formatted_thinking = self.format_cycle_logs(cycle_logs)
                self.print_panel(formatted_thinking, "Thoughts and Actions (Incomplete)", "yellow")

            return "I apologize, I couldn't complete the reasoning within the allowed iterations."

        except Exception as e:
            self.print_status(f"Error in ReAct branch: {e}", "error")
            return f"Error: {e}"

    # === CRITICAL: ReAct Isolation Helper Methods ===

    def _get_recent_context(self, token_limit: int = 2000) -> str:
        """
        Get last N tokens from main conversation for ReAct context.

        ReAct operates as an ISOLATED BRANCH with limited context,
        not accumulating the full conversation history.
        """
        try:
            if not self.session or not hasattr(self.session, 'memory'):
                return ""

            # Get recent items from working memory (main conversation)
            recent_items = []
            if hasattr(self.session.memory, 'working'):
                recent_items = self.session.memory.working.retrieve("", limit=5)  # Get last 5 interactions

            if not recent_items:
                return ""

            # Format as conversation
            context_parts = []
            for item in recent_items[-3:]:  # Last 3 interactions
                if isinstance(item.content, dict):
                    user_input = item.content.get('user_input', '')
                    agent_response = item.content.get('agent_response', '')
                    if user_input and agent_response:
                        context_parts.append(f"User: {user_input}")
                        context_parts.append(f"Agent: {agent_response}")
                else:
                    # Simple content
                    content_str = str(item.content)
                    if len(content_str.strip()) > 0:
                        context_parts.append(content_str)

            context = "\n".join(context_parts)

            # Truncate to token limit (rough approximation: 4 chars = 1 token)
            if len(context) > token_limit * 4:
                context = context[-(token_limit * 4):]
                # Try to start at a complete sentence
                if '\n' in context:
                    context = context[context.find('\n') + 1:]

            return context

        except Exception as e:
            self.print_status(f"Warning: Failed to get recent context: {e}", "warning")
            return ""

    def _save_react_scratchpad(self, scratchpad: list, query: str, final_answer: str, react_config: ReActConfig = None):
        """
        Save ReAct reasoning scratchpad separately from main conversation.

        The scratchpad contains the full reasoning process but is NOT
        part of the main conversation context.
        """
        try:
            if not self.session or not hasattr(self.session, 'memory'):
                return

            from datetime import datetime
            from abstractmemory.core.interfaces import MemoryItem

            # Create scratchpad entry for episodic memory
            scratchpad_entry = {
                'type': 'react_reasoning',
                'query': query,
                'reasoning_steps': scratchpad,
                'final_answer': final_answer,
                'timestamp': datetime.now().isoformat(),
                'step_count': len(scratchpad)
            }

            # Store in episodic memory as a reasoning episode
            if hasattr(self.session.memory, 'episodic'):
                # Use configurable confidence, fallback to default
                confidence = react_config.scratchpad_confidence if react_config else 0.8

                memory_item = MemoryItem(
                    content=scratchpad_entry,
                    event_time=datetime.now(),
                    ingestion_time=datetime.now(),
                    confidence=confidence,  # Configurable reasoning confidence
                    metadata={
                        'type': 'react_scratchpad',
                        'query_hash': hash(query),
                        'answer_length': len(final_answer)
                    }
                )
                self.session.memory.episodic.add(memory_item)
                self.print_status(f"💾 Saved ReAct reasoning ({len(scratchpad)} steps) to episodic memory", "info")

        except Exception as e:
            self.print_status(f"Warning: Failed to save ReAct scratchpad: {e}", "warning")

    def format_cycle_logs(self, cycle_logs: dict) -> str:
        """Format cycle logs with color-coded keywords and visual separation."""
        formatted_lines = []

        for cycle_num in sorted(cycle_logs.keys()):
            entries = cycle_logs[cycle_num]

            # Cycle header with visual separator
            formatted_lines.append(f"[cyan]━━━ Cycle {cycle_num} ━━━[/cyan]")

            for entry_type, content in entries:
                if entry_type == "thought_action":
                    # Parse and color-code Thought: and Action: keywords
                    colored_content = content
                    colored_content = colored_content.replace("Thought:", "[bold yellow]Thought:[/bold yellow]")
                    colored_content = colored_content.replace("Action:", "[bold magenta]Action:[/bold magenta]")
                    colored_content = colored_content.replace("Action Input:", "[bold magenta]Action Input:[/bold magenta]")

                    # Truncate to 450 characters for display
                    if len(colored_content) > 450:
                        colored_content = colored_content[:450] + "[dim]...[/dim]"

                    formatted_lines.append(colored_content)

                elif entry_type == "observation":
                    # Color-code Observation: keyword
                    colored_content = content.replace("Observation:", "[bold green]Observation:[/bold green]")

                    # Truncate to 450 characters for display
                    if len(colored_content) > 450:
                        colored_content = colored_content[:450] + "[dim]...[/dim]"

                    formatted_lines.append(colored_content)

                elif entry_type == "thought":
                    # Color-code standalone thoughts
                    colored_content = content.replace("Thought:", "[bold yellow]Thought:[/bold yellow]")

                    # Truncate to 450 characters for display
                    if len(colored_content) > 450:
                        colored_content = colored_content[:450] + "[dim]...[/dim]"

                    formatted_lines.append(colored_content)

                elif entry_type == "final_thought":
                    # Color-code final thoughts before answer
                    colored_content = content
                    colored_content = colored_content.replace("Thought:", "[bold yellow]Thought:[/bold yellow]")
                    colored_content = colored_content.replace("Final Answer:", "[bold blue]Final Answer:[/bold blue]")

                    # Truncate to 450 characters for display
                    if len(colored_content) > 450:
                        colored_content = colored_content[:450] + "[dim]...[/dim]"

                    formatted_lines.append(colored_content)

            # Add visual separation between cycles (except for last cycle)
            if cycle_num != max(cycle_logs.keys()):
                formatted_lines.append("")  # Empty line between cycles

        return "\n".join(formatted_lines)

    def parse_action_from_response(self, response: str):
        """Parse action from LLM response. Returns (tool_name, tool_input) or None."""
        import re
        import json

        # First try to parse <|tool_call|> format (modern format)
        tool_call_pattern = r'<\|tool_call\|>\s*\n?\s*\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\s*\}'
        tool_call_match = re.search(tool_call_pattern, response, re.DOTALL)

        if tool_call_match:
            try:
                tool_name = tool_call_match.group(1)
                arguments_str = tool_call_match.group(2)
                tool_input = json.loads(arguments_str)
                return tool_name, tool_input
            except json.JSONDecodeError:
                pass

        # Also try alternative <|tool_call|> format
        alt_tool_pattern = r'\{"name":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\s*\}'
        alt_match = re.search(alt_tool_pattern, response, re.DOTALL)

        if alt_match:
            try:
                tool_name = alt_match.group(1)
                arguments_str = alt_match.group(2)
                tool_input = json.loads(arguments_str)
                return tool_name, tool_input
            except json.JSONDecodeError:
                pass

        # Fall back to traditional Action: pattern
        action_pattern = r'Action:\s*(\w+)'
        action_match = re.search(action_pattern, response, re.IGNORECASE)

        if not action_match:
            return None

        tool_name = action_match.group(1)

        # Look for Action Input: pattern
        input_pattern = r'Action Input:\s*({.*?})'
        input_match = re.search(input_pattern, response, re.DOTALL)

        if input_match:
            try:
                tool_input = json.loads(input_match.group(1))
                return tool_name, tool_input
            except json.JSONDecodeError:
                # Try to extract simple string input
                simple_pattern = r'Action Input:\s*"([^"]+)"'
                simple_match = re.search(simple_pattern, response)
                if simple_match:
                    return tool_name, {"input": simple_match.group(1)}

        # No valid input found
        return tool_name, {}

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool by name with given input."""
        try:
            # Get tools from session
            tools = getattr(self.session, 'tools', [])
            if not tools:
                return f"Error: No tools available"

            # Find the tool by name
            target_tool = None
            for tool in tools:
                if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                    target_tool = tool
                    break

            if not target_tool:
                available_tools = [getattr(t, '__name__', 'unknown') for t in tools]
                return f"Error: Tool '{tool_name}' not found. Available: {available_tools}"

            # Execute the tool with the input
            if isinstance(tool_input, dict):
                result = target_tool(**tool_input)
            else:
                result = target_tool(tool_input)

            return str(result)

        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def parse_react_response(self, response: str):
        """Parse ReAct response into thoughts/actions and final answer."""
        # First, try to find explicit "Final Answer:" section
        if "Final Answer:" in response:
            parts = response.split("Final Answer:", 1)
            thoughts_actions = parts[0].strip()
            final_answer = parts[1].strip()

            # Clean up thoughts/actions part
            if thoughts_actions:
                thoughts_actions = thoughts_actions.replace("Question:", "**Question:**")
                thoughts_actions = thoughts_actions.replace("Thought:", "**Thought:**")
                thoughts_actions = thoughts_actions.replace("Action:", "**Action:**")
                thoughts_actions = thoughts_actions.replace("Observation:", "**Observation:**")

            return thoughts_actions, final_answer

        # Fallback: Try to extract a reasonable final answer from the response
        lines = response.split('\n')
        thinking_parts = []
        potential_answer = ""

        for line in lines:
            line = line.strip()
            if any(line.startswith(prefix) for prefix in ["Question:", "Thought:", "Action:", "Observation:"]):
                thinking_parts.append(line)
            elif line and not line.startswith(("**", "Tool Results:", "<|", "{")):
                # This might be the final answer content
                potential_answer = line

        # If we found thinking parts, separate them from the potential answer
        if thinking_parts:
            thoughts_actions = '\n'.join(thinking_parts)
            # Use the last substantial line as the final answer
            if potential_answer:
                return thoughts_actions, potential_answer
            else:
                # Generate a basic final answer from the response
                return thoughts_actions, "I've processed your request. Please see the information above."
        else:
            # No clear structure - treat the whole response as a final answer
            return "", response if response.strip() else "I apologize, I couldn't generate a complete response."

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
                try:
                    if self.console and sys.stdin.isatty():
                        user_input = Prompt.ask("\n[bold green]You[/bold green]", default="")
                    else:
                        user_input = input("\nYou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.print_status("Session ended by user.", "info")
                    break
                except Exception:
                    # Fallback to basic input for non-TTY environments
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
                elif user_input.lower().startswith('/memory '):
                    # Handle /memory xxx command to set max_tokens
                    try:
                        parts = user_input.split()
                        if len(parts) == 2:
                            new_max_tokens = int(parts[1])
                            if new_max_tokens > 0:
                                self.set_model_max_tokens(new_max_tokens)
                            else:
                                self.print_status("Max tokens must be a positive number", "error")
                        else:
                            self.print_status("Usage: /memory <number> (e.g., /memory 8192)", "error")
                    except ValueError:
                        self.print_status("Invalid number. Usage: /memory <number>", "error")
                    continue
                elif user_input.lower() == '/tools':
                    self.show_tools_status()
                    continue
                elif user_input.lower() == '/debug':
                    self.show_debug_info()
                    continue
                elif user_input.lower() == '/context':
                    self.show_last_context()
                    continue
                elif user_input.lower().startswith('/compact'):
                    self.handle_compact_command(user_input)
                    continue

                # Process through agent
                self.process_user_input(user_input)

                # Auto-save chat history after each interaction
                self.save_chat_history()

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
- `/memory <number>` - Set model max_tokens (e.g., /memory 8192)
- `/context` - Show verbatim last context used for final answer generation
- `/tools` - Show available tools and their status
- `/debug` - Show debugging information
- `/compact [preserve_recent] [focus]` - Compact session history using AI summarization
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
        """Show comprehensive memory contents and status."""
        if not self.session or not hasattr(self.session, 'memory'):
            self.print_status("No memory session available", "error")
            return

        try:
            memory = self.session.memory
            memory_info = []

            # Memory system overview
            memory_info.append(f"**Memory System**: {type(memory).__name__}")
            memory_info.append(f"**Storage Path**: {self.config.memory_path}")

            # Model and context information
            memory_info.append(f"**Model**: {self.config.model}")
            memory_info.append(f"**Model Max Tokens**: {self.model_max_tokens:,}")
            if self.last_context_tokens > 0:
                usage_percent = (self.last_context_tokens / self.model_max_tokens) * 100
                memory_info.append(f"**Last Context**: {self.last_context_tokens:,} tokens / {self.last_context_size:,} chars ({usage_percent:.1f}% of max)")
            else:
                memory_info.append(f"**Last Context**: No context tracked yet")

            # Check what components are available
            components = []
            for component in ['working', 'semantic', 'core', 'episodic', 'document']:
                if hasattr(memory, component):
                    components.append(component)
            memory_info.append(f"**Available Components**: {', '.join(components)}")
            memory_info.append("")

            # Working memory - recent interactions
            if hasattr(memory, 'working'):
                if hasattr(memory.working, 'items'):
                    working_items = memory.working.items
                    working_count = len(working_items)
                    memory_info.append(f"**Working Memory**: {working_count} items (capacity: {getattr(memory.working, 'capacity', 'unknown')})")
                    if working_count > 0:
                        for i, (_, item) in enumerate(list(working_items)):
                            content = str(item.content)[:100]
                            event_time = getattr(item, 'event_time', 'Unknown')
                            memory_info.append(f"  {i+1}. [{event_time}] {content}{'...' if len(str(item.content)) > 100 else ''}")
                elif hasattr(memory.working, 'memories'):
                    working_memories = memory.working.memories
                    working_count = len(working_memories)
                    memory_info.append(f"**Working Memory**: {working_count} items")
                    if working_count > 0:
                        for i, (_, item) in enumerate(list(working_memories.items())):
                            content = str(item.get('content', ''))[:100]
                            timestamp = item.get('timestamp', 'Unknown')
                            memory_info.append(f"  {i+1}. [{timestamp}] {content}{'...' if len(str(item.get('content', ''))) > 100 else ''}")
                else:
                    memory_info.append("**Working Memory**: Structure unknown")
                memory_info.append("")

            # Semantic memory - validated facts
            if hasattr(memory, 'semantic'):
                if hasattr(memory.semantic, 'facts'):
                    semantic_facts = memory.semantic.facts
                    semantic_count = len(semantic_facts)
                    validation_threshold = getattr(memory.semantic, 'validation_threshold', 3)
                    memory_info.append(f"**Semantic Memory**: {semantic_count} validated facts (need {validation_threshold} repetitions)")
                    if semantic_count > 0:
                        for i, (_, fact_data) in enumerate(semantic_facts.items()):
                            content = str(fact_data.get('content', ''))[:80]
                            confidence = fact_data.get('confidence', 0)
                            occurrence_count = fact_data.get('occurrence_count', 1)
                            memory_info.append(f"  {i+1}. {content}{'...' if len(str(fact_data.get('content', ''))) > 80 else ''}")
                            memory_info.append(f"     Confidence: {confidence:.2f}, Occurrences: {occurrence_count}")

                # Show pending facts (facts being validated)
                if hasattr(memory.semantic, 'pending_facts'):
                    pending_count = len(memory.semantic.pending_facts)
                    if pending_count > 0:
                        memory_info.append(f"  **Pending Facts**: {pending_count} awaiting validation (need {validation_threshold} total)")
                        for fact, count in list(memory.semantic.pending_facts.items())[:5]:
                            remaining = validation_threshold - count
                            memory_info.append(f"    - \"{fact[:60]}{'...' if len(fact) > 60 else ''}\" ({count}/{validation_threshold}, need {remaining} more)")
                    else:
                        memory_info.append(f"  **Pending Facts**: 0 facts pending validation")
                memory_info.append("")

            # Core values and identity
            if hasattr(memory, 'core'):
                if hasattr(memory.core, 'values'):
                    core_values = memory.core.values
                    memory_info.append(f"**Core Values**: {len(core_values) if isinstance(core_values, dict) else 1} values")
                    if isinstance(core_values, dict):
                        for key, value in core_values.items():
                            memory_info.append(f"  - {key}: {value}")
                    else:
                        memory_info.append(f"  {core_values}")
                memory_info.append("")

            # Episodic memory - if available
            if hasattr(memory, 'episodic'):
                if hasattr(memory.episodic, 'episodes'):
                    episodes = getattr(memory.episodic, 'episodes', {})
                    episode_count = len(episodes)
                    memory_info.append(f"**Episodic Memory**: {episode_count} episodes")
                    if episode_count > 0:
                        for i, (_, episode) in enumerate(list(episodes.items())[:3]):
                            content = str(episode.get('content', ''))[:80]
                            memory_info.append(f"  {i+1}. {content}{'...' if len(str(episode.get('content', ''))) > 80 else ''}")
                memory_info.append("")

            # Document memory - stored files and documents
            if hasattr(memory, 'document'):
                doc_summary = memory.document.get_document_summary()
                doc_count = doc_summary.get('total_documents', 0)
                memory_info.append(f"**Document Memory**: {doc_count} stored documents")

                if doc_count > 0:
                    total_size = doc_summary.get('total_content_size', 0)
                    file_types = doc_summary.get('file_types', {})
                    memory_info.append(f"  Total content: {total_size:,} characters")

                    if file_types:
                        types_str = ", ".join([f"{ftype}({count})" for ftype, count in file_types.items()])
                        memory_info.append(f"  File types: {types_str}")

                    most_accessed = doc_summary.get('most_accessed_document')
                    if most_accessed:
                        filepath = most_accessed.get('filepath', 'unknown')[:50]
                        access_count = most_accessed.get('access_count', 0)
                        memory_info.append(f"  Most accessed: {filepath}{'...' if len(most_accessed.get('filepath', '')) > 50 else ''} ({access_count} times)")

                    has_semantic = doc_summary.get('has_semantic_search', False)
                    if has_semantic:
                        chunk_count = doc_summary.get('total_chunks', 0)
                        memory_info.append(f"  Semantic search: Enabled ({chunk_count} chunks)")
                    else:
                        memory_info.append(f"  Semantic search: Disabled (keyword search only)")

                memory_info.append("")

            # Storage information
            from pathlib import Path
            storage_path = Path(self.config.memory_path)
            if storage_path.exists():
                memory_info.append("**File Storage:**")
                try:
                    subdirs = [d.name for d in storage_path.iterdir() if d.is_dir()]
                    files = [f.name for f in storage_path.iterdir() if f.is_file()]
                    memory_info.append(f"  Directories: {subdirs}")
                    memory_info.append(f"  Files: {files}")

                    # Check for specific storage types
                    if (storage_path / "semantic").exists():
                        semantic_files = list((storage_path / "semantic").glob("*"))
                        memory_info.append(f"  Semantic storage: {len(semantic_files)} files")
                    if (storage_path / "verbatim").exists():
                        verbatim_files = list((storage_path / "verbatim").rglob("*"))
                        memory_info.append(f"  Verbatim storage: {len(verbatim_files)} files")
                except Exception as e:
                    memory_info.append(f"  Storage access error: {e}")
            else:
                memory_info.append("**File Storage**: Not created yet")

            memory_text = "\n".join(memory_info) if memory_info else "No memory information available"

            if self.console:
                self.console.print(Panel(memory_text, title="Comprehensive Memory Status", border_style="blue"))
            else:
                print(f"=== Memory Status ===\n{memory_text}")

        except Exception as e:
            self.print_status(f"Error accessing memory: {e}", "error")
            # Show fallback basic info
            basic_info = f"Memory session exists: {hasattr(self.session, 'memory')}\n"
            basic_info += f"Storage path: {self.config.memory_path}"
            self.print_panel(basic_info, "Basic Memory Info", "red")

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

    def show_last_context(self):
        """Show the verbatim last context used for final answer generation."""
        if not self.last_final_answer_context:
            self.print_status("No context available - no ReAct cycle completed yet", "warning")
            return

        context_info = []
        context_info.append(f"**Context Size**: {len(self.last_final_answer_context):,} characters")
        context_info.append(f"**Context Tokens**: {self._estimate_tokens(self.last_final_answer_context):,} tokens")
        context_info.append(f"**Total ReAct Time**: {self.last_react_total_time:.1f}s")
        context_info.append(f"**Model Max Tokens**: {self.model_max_tokens:,}")
        context_info.append("")
        context_info.append("**VERBATIM CONTEXT:**")
        context_info.append("=" * 60)
        context_info.append(self.last_final_answer_context)

        context_text = "\n".join(context_info)

        if self.console:
            self.console.print(Panel(context_text, title="Last Context Used", border_style="cyan"))
        else:
            print(f"=== Last Context Used ===\n{context_text}")

    def save_chat_history(self):
        """Save chat history to disk for persistence between sessions."""
        try:
            if self.session and self.session._basic_session and hasattr(self.session._basic_session, 'messages'):
                history_path = Path(self.config.memory_path) / "chat_history.json"
                history_path.parent.mkdir(parents=True, exist_ok=True)

                # Properly serialize Message objects using their to_dict() method
                messages_data = []
                for msg in self.session._basic_session.messages:
                    if hasattr(msg, 'to_dict'):
                        messages_data.append(msg.to_dict())
                    else:
                        # Fallback for non-Message objects
                        messages_data.append(msg)

                with open(history_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(messages_data, f, indent=2, default=str)

        except Exception as e:
            self.print_status(f"Warning: Failed to save chat history: {e}", "warning")

    def load_chat_history(self):
        """Load chat history from disk if available."""
        try:
            history_path = Path(self.config.memory_path) / "chat_history.json"
            if history_path.exists() and self.session and self.session._basic_session:
                with open(history_path, 'r', encoding='utf-8') as f:
                    import json
                    messages_data = json.load(f)

                    if messages_data and isinstance(messages_data, list):
                        # Properly reconstruct Message objects using from_dict()
                        try:
                            from abstractllm.session import Message
                        except ImportError:
                            # Alternative import path
                            from abstractllm import Message
                        reconstructed_messages = []

                        for msg_data in messages_data:
                            try:
                                if isinstance(msg_data, dict) and 'role' in msg_data:
                                    # Reconstruct Message object
                                    message = Message.from_dict(msg_data)
                                    reconstructed_messages.append(message)
                                else:
                                    # Keep as-is if not a proper message dict
                                    reconstructed_messages.append(msg_data)
                            except Exception as e:
                                self.print_status(f"Warning: Could not reconstruct message: {e}", "warning")
                                continue

                        self.session._basic_session.messages = reconstructed_messages
                        self.print_status(f"Loaded {len(reconstructed_messages)} previous messages from chat history", "info")

        except Exception as e:
            self.print_status(f"Warning: Failed to load chat history: {e}", "warning")

    def handle_compact_command(self, user_input: str):
        """Handle /compact command for session compaction."""
        # Parse command arguments
        parts = user_input.lower().split()
        preserve_recent = 6  # Default
        focus = None

        # Parse optional parameters: /compact [preserve_recent] [focus]
        if len(parts) >= 2:
            try:
                preserve_recent = int(parts[1])
                if preserve_recent < 0:
                    self.print_status("preserve_recent must be non-negative", "error")
                    return
            except ValueError:
                # Not a number, might be focus parameter
                focus = " ".join(parts[1:])

        if len(parts) >= 3:
            try:
                # If we parsed a number for preserve_recent, remaining parts are focus
                int(parts[1])  # Check if second arg was number
                focus = " ".join(parts[2:])
            except ValueError:
                # Second arg was focus, use default preserve_recent
                preserve_recent = 6
                focus = " ".join(parts[1:])

        # Check if session has compaction capabilities
        if not self.session:
            self.print_status("No session available for compaction", "error")
            return

        # Check if we have BasicSession compaction methods via MemorySession
        if hasattr(self.session, '_basic_session') and self.session._basic_session:
            try:
                # Get token estimate before compaction
                original_tokens = self.session._basic_session.get_token_estimate()
                original_messages = len(self.session._basic_session.messages)

                # Show compaction start info
                self.print_status(f"Starting compaction (current: {original_messages} messages, ~{original_tokens} tokens)", "info")
                if focus:
                    self.print_status(f"Focus: {focus}", "info")

                # Perform compaction
                self.session._basic_session.force_compact(
                    preserve_recent=preserve_recent,
                    focus=focus
                )

                # Show results
                final_tokens = self.session._basic_session.get_token_estimate()
                final_messages = len(self.session._basic_session.messages)
                compression_ratio = original_tokens / final_tokens if final_tokens > 0 else 1.0

                self.print_status(f"✅ Session compacted: {final_messages} messages (~{final_tokens} tokens)", "success")
                self.print_status(f"Compression ratio: {compression_ratio:.1f}x (saved {original_tokens - final_tokens} tokens)", "success")

            except Exception as e:
                self.print_status(f"Compaction failed: {e}", "error")
        else:
            self.print_status("Compaction not available (AbstractCore BasicSession not found)", "warning")
            self.print_status("This feature requires AbstractCore with BasicSession support", "info")


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
    parser.add_argument("--timeout", type=float, default=7200.0,
                       help="HTTP timeout in seconds (default: 7200 = 2 hours)")
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
        enable_memory_tools=not args.no_memory_tools,
        timeout=args.timeout
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