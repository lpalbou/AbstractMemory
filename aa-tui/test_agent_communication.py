#!/usr/bin/env python3
"""
Test script to verify agent communication works outside TUI
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from abstractllm import create_llm
    from abstractllm.tools.common_tools import list_files
    from abstractmemory import MemorySession, MemoryConfig
    ABSTRACTCORE_AVAILABLE = True
    print("✅ AbstractCore imports successful")
except ImportError as e:
    print(f"❌ AbstractCore imports failed: {e}")
    ABSTRACTCORE_AVAILABLE = False

def test_agent_session():
    """Test if we can create and use an agent session."""
    try:
        print("🔄 Creating LLM provider...")
        provider = create_llm(
            provider="ollama",
            model="qwen3-coder:30b",
            timeout=30.0  # Short timeout for testing
        )
        print("✅ LLM provider created")
        print(f"Provider type: {type(provider)}")

        print("🔄 Creating memory session with minimal parameters...")
        session = MemorySession(provider)
        print("✅ Memory session created")

        print("🔄 Testing generate method...")
        response = session.generate(
            "Hello, this is a test",
            user_id="test_user",
            include_memory=False
        )

        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)

        print(f"✅ Response received: {content[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(f"Full error: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Agent Communication")
    print("=" * 50)

    if not ABSTRACTCORE_AVAILABLE:
        print("❌ Cannot test - AbstractCore not available")
        sys.exit(1)

    success = test_agent_session()

    if success:
        print("\n🎉 SUCCESS: Agent communication is working!")
        print("The TUI should now be able to communicate with the agent in a real terminal.")
    else:
        print("\n💥 FAILURE: Agent communication is not working.")
        print("There may be an issue with the agent setup or dependencies.")