#!/usr/bin/env python3
"""
Test agent initialization without TUI dependencies
"""

import sys
import os
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from abstractllm import create_llm
    from abstractllm.tools.common_tools import list_files
    from abstractllm.tools import tool
    from abstractmemory import MemorySession, MemoryConfig
    ABSTRACTCORE_AVAILABLE = True
    print("✅ AbstractCore and AbstractMemory imports successful")
except ImportError as e:
    ABSTRACTCORE_AVAILABLE = False
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_agent_init():
    """Test the agent initialization logic from enhanced_tui.py"""
    print("🔄 Testing agent initialization...")

    model = "qwen3-coder:30b"
    provider = "ollama"
    memory_path = "./test_memory"

    try:
        # Create memory path if it doesn't exist
        Path(memory_path).mkdir(parents=True, exist_ok=True)

        print(f"📡 Connecting to {provider} with {model}...")
        # Create LLM provider with extended timeout - exactly like nexus.py
        provider_instance = create_llm(provider, model=model, timeout=7200.0)
        print("✅ LLM connection established")

        # Configure memory - using working pattern from nexus.py
        memory_config = MemoryConfig.agent_mode()
        memory_config.enable_memory_tools = True
        memory_config.enable_self_editing = True
        print("✅ Memory config created")

        # Create tools list
        tools = []

        # Add basic file system tools
        if list_files:
            tools.append(list_files)
        print(f"✅ Tools configured: {len(tools)} tools")

        # Create the memory session - using EXACT pattern from nexus.py
        agent_session = MemorySession(
            provider_instance,  # Pass the LLM provider instance like nexus.py does
            tools=tools,
            memory_config={"path": memory_path, "semantic_threshold": 1},  # Immediate validation
            default_memory_config=memory_config,
            system_prompt="You are Nexus, an AI assistant with persistent memory and identity."
        )
        print("✅ MemorySession created successfully")

        # Set agent identity and values - using pattern from nexus.py
        if hasattr(agent_session, 'memory') and hasattr(agent_session.memory, 'set_core_values'):
            agent_values = {
                'purpose': 'serve as enhanced TUI assistant with memory',
                'approach': 'interactive and helpful',
                'lens': 'ui_focused_thinking',
                'domain': 'tui_agent'
            }
            agent_session.memory.set_core_values(agent_values)
            print("✅ Agent identity and values configured")

        print(f"✅ Total tools: {len(agent_session.tools)}")
        for i, tool in enumerate(agent_session.tools):
            tool_name = getattr(tool, '__name__', f'tool_{i}')
            print(f"  - {tool_name}")

        print("🎉 Agent initialization test SUCCESSFUL!")
        return True

    except Exception as e:
        import traceback
        print(f"❌ Agent initialization FAILED: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_agent_init()
    if success:
        print("✅ Test completed successfully")
    else:
        print("❌ Test failed")
        sys.exit(1)