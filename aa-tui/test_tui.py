#!/usr/bin/env python3
"""
Test script for the AbstractMemory TUI.

This script runs the TUI in demo mode without requiring a full agent setup.
"""

import asyncio
from core.config import TUIConfig
from core.app import AbstractMemoryTUI


class MockAgentCLI:
    """Mock agent CLI for testing."""

    def __init__(self):
        self.config = TUIConfig()
        self.session = None
        self.interaction_counter = 0

    def process_user_input(self, user_input: str) -> str:
        """Mock process user input."""
        self.interaction_counter += 1

        # Simple mock responses based on input
        if "hello" in user_input.lower():
            return "Hello! I'm a mock agent running in the TUI. Try asking me about files or memory!"

        elif "files" in user_input.lower():
            return f"I can help with files! You asked: '{user_input}'. In a real setup, I'd use file tools."

        elif "memory" in user_input.lower():
            return f"Memory is working! You asked: '{user_input}'. I would search and use my persistent memory."

        elif "code" in user_input.lower():
            return f"""Here's some example code:

```python
def hello_world():
    print("Hello from the TUI!")
    return "Success"

# This would be syntax highlighted
result = hello_world()
```

The TUI supports syntax highlighting and foldable sections!"""

        else:
            return f"Mock response to: '{user_input}'\n\nThis is a demonstration of the TUI interface. The real agent would process your request using ReAct reasoning, tools, and memory."


async def demo_tui():
    """Run TUI in demo mode."""
    print("🚀 Starting AbstractMemory TUI Demo...")
    print("📝 Running in mock mode - no real agent required")

    # Create configuration
    config = TUIConfig(
        model="mock-model",
        provider="demo",
        memory_path="./demo_memory",
        theme="dark",
        show_side_panel=True
    )

    # Create TUI application
    tui_app = AbstractMemoryTUI(config)

    # Create mock agent
    mock_agent = MockAgentCLI()

    # Set the mock agent
    tui_app.set_agent(mock_agent)

    # Add demo system message
    tui_app.add_system_message(
        "🎭 Demo Mode: This is a mock TUI demonstration. "
        "Try typing 'hello', 'files', 'memory', or 'code' to see different responses!",
        "info"
    )

    # Update status with demo info
    tui_app.main_layout.update_agent_status({
        'model': 'Mock Demo Model',
        'provider': 'Demo',
        'connected': True,
        'memory_enabled': True,
        'tools_count': 5,
        'last_update': 'Demo mode'
    })

    # Update memory info
    tui_app.main_layout.update_memory_info({
        'memory_path': './demo_memory',
        'working_count': 3,
        'semantic_count': 7,
        'pending_count': 2,
        'document_count': 5,
        'episode_count': 12
    })

    # Update tools info
    tui_app.main_layout.update_tools_info([
        'list_files', 'read_file', 'search_memory',
        'remember_fact', 'get_context'
    ])

    print("🎯 TUI Demo started! Press F1 for help, Ctrl+Q to quit")

    try:
        # Run the application
        await tui_app.run_async()
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    finally:
        print("👋 Demo ended!")


if __name__ == "__main__":
    asyncio.run(demo_tui())