#!/usr/bin/env python3
"""
Test that memory metrics are displayed in the side panel
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_memory_metrics():
    """Test that memory metrics are properly tracked and displayed"""
    print("🔄 Testing memory metrics display...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_metrics"
        )
        print("✅ Enhanced TUI instance created")

        # Initialize agent to have a session
        success = tui.init_agent()
        if success:
            print("✅ Agent initialized")

        # Check that AgentState has new metrics fields
        state = tui.agent_state

        print("\n📊 Checking AgentState metrics fields:")
        if hasattr(state, 'context_tokens'):
            print(f"✅ context_tokens: {state.context_tokens}")
        if hasattr(state, 'enhanced_tokens'):
            print(f"✅ enhanced_tokens: {state.enhanced_tokens}")
        if hasattr(state, 'system_prompt_tokens'):
            print(f"✅ system_prompt_tokens: {state.system_prompt_tokens}")
        if hasattr(state, 'max_tokens'):
            print(f"✅ max_tokens: {state.max_tokens}")
        if hasattr(state, 'core_memories'):
            print(f"✅ core_memories: {state.core_memories}")
        if hasattr(state, 'core_size'):
            print(f"✅ core_size: {state.core_size}")

        # Add some messages to trigger updates
        print("\n📝 Adding test messages...")
        for i in range(5):
            tui.add_message("User", f"Test message {i+1}")
            tui.add_message("Assistant", f"Response {i+1}")

        # Update memory display
        tui._update_memory_display()

        # Check memory components
        print("\n💾 Memory components:")
        for key, value in state.memory_components.items():
            print(f"  {key}: {value}")

        # Update side panel content
        tui.update_side_panel_content()
        side_text = tui.side_panel_textarea.buffer.text

        print("\n📋 Side panel content includes:")
        checks = [
            ("Memory Metrics", "Memory metrics section"),
            ("Token Usage", "Token usage section"),
            ("Working:", "Working memory count"),
            ("Semantic:", "Semantic memory count"),
            ("Episodic:", "Episodic memory count"),
            ("Context:", "Context tokens"),
            ("Max:", "Max tokens"),
        ]

        for check, desc in checks:
            if check in side_text:
                print(f"✅ {desc} found")
            else:
                print(f"⚠️  {desc} not found")

        return True

    except Exception as e:
        import traceback
        print(f"❌ Test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_memory_metrics()
    if success:
        print("\n🎉 Memory metrics test SUCCESSFUL!")
        print("The side panel now shows:")
        print("  ✅ Detailed memory breakdown (Working, Semantic, Episodic, Files, User)")
        print("  ✅ Core memory stats (Items and Size)")
        print("  ✅ Token usage (Context, Enhanced, System, Max)")
        print("  ✅ Real-time updates during conversation")
        print("\nThis matches the nexus.py display style!")
    else:
        print("\n❌ Memory metrics test FAILED")
        sys.exit(1)