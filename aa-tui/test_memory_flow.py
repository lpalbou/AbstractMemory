#!/usr/bin/env python3
"""
Test the memory flow to ensure proper conversation tracking
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

async def test_memory_flow():
    """Test that conversation history is tracked properly"""
    print("🔄 Testing memory flow...")

    try:
        from enhanced_tui import EnhancedTUI
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_flow_memory"
        )
        print("✅ Enhanced TUI instance created")

        # Test that agent initialization works
        success = tui.init_agent()
        if not success:
            print("❌ Agent initialization failed")
            return False

        print("✅ Agent initialization successful")

        # Test conversation history tracking
        print("🔄 Testing conversation tracking...")

        # Add a user message
        tui.add_message("User", "Hello, who are you?")
        print(f"User message added. History length: {len(tui.actual_conversation_history)}")

        # Add an assistant response
        tui.add_message("Assistant", "I'm an AI assistant with memory capabilities.")
        print(f"Assistant message added. History length: {len(tui.actual_conversation_history)}")

        # Check conversation history
        if len(tui.actual_conversation_history) == 2:
            print("✅ Conversation history tracking works correctly")
            print(f"First entry: {tui.actual_conversation_history[0]}")
            print(f"Second entry: {tui.actual_conversation_history[1]}")
        else:
            print(f"❌ Expected 2 entries, got {len(tui.actual_conversation_history)}")
            return False

        # Test context generation
        context = tui._get_recent_context(1000)
        print(f"Generated context: {context}")

        if "Hello, who are you?" in context and "I'm an AI assistant" in context:
            print("✅ Context generation works correctly")
        else:
            print("❌ Context generation failed")
            print(f"Context: {context}")
            return False

        # Test that system messages don't pollute conversation history
        tui.add_system_message("This is a system message")
        if len(tui.actual_conversation_history) == 2:
            print("✅ System messages don't pollute conversation history")
        else:
            print(f"❌ System message polluted history. Length: {len(tui.actual_conversation_history)}")
            return False

        # Test clear conversation
        tui.clear_conversation()
        if len(tui.actual_conversation_history) == 0:
            print("✅ Clear conversation works correctly")
        else:
            print(f"❌ Clear conversation failed. Length: {len(tui.actual_conversation_history)}")
            return False

        return True

    except Exception as e:
        import traceback
        print(f"❌ Memory flow test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_memory_flow())
    if success:
        print("🎉 Memory flow test SUCCESSFUL!")
        print("✅ Key fixes:")
        print("  - Conversation history tracking separated from UI text")
        print("  - System messages don't pollute agent context")
        print("  - Context generation uses actual conversation only")
        print("  - Clear conversation resets history properly")
    else:
        print("❌ Memory flow test FAILED")
        sys.exit(1)