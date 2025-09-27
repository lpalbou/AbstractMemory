#!/usr/bin/env python3
"""
Test enhanced TUI agent connection (without the TUI part)
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from enhanced_tui import EnhancedTUI
    print("✅ Enhanced TUI import successful")
except ImportError as e:
    print(f"❌ Enhanced TUI import failed: {e}")
    sys.exit(1)

def test_enhanced_tui_agent():
    """Test the enhanced TUI agent initialization without the UI"""
    print("🔄 Testing Enhanced TUI agent initialization...")

    try:
        # Create TUI instance (without running the UI)
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_memory_enhanced"
        )
        print("✅ Enhanced TUI instance created")

        # Test agent initialization
        success = tui.init_agent()
        print(f"Agent initialization result: {success}")

        if success and hasattr(tui, 'agent_session') and tui.agent_session:
            print("✅ Agent session created successfully!")
            print(f"🔧 Tools available: {len(tui.agent_session.tools)}")

            # List the tools
            for i, tool in enumerate(tui.agent_session.tools):
                tool_name = getattr(tool, '__name__', f'tool_{i}')
                print(f"  - {tool_name}")

            # Test agent state
            print(f"⚡ Agent status: {tui.agent_state.status}")
            print(f"📊 Tools in state: {len(tui.agent_state.tools_available)}")

            return True
        else:
            print("❌ Agent session not created properly")
            return False

    except Exception as e:
        import traceback
        print(f"❌ Enhanced TUI agent test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_enhanced_tui_agent()
    if success:
        print("🎉 Enhanced TUI agent connection test SUCCESSFUL!")
        print("✅ The enhanced TUI is now properly connected to AbstractMemory and AbstractCore!")
    else:
        print("❌ Enhanced TUI agent connection test FAILED")
        sys.exit(1)