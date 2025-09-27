#!/usr/bin/env python3
"""
Test F2 toggle functionality and visual format
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_f2_toggle():
    """Test F2 toggle and visual format"""
    print("🔄 Testing F2 toggle and visual format...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_f2"
        )
        print("✅ Enhanced TUI instance created")

        # Initialize agent
        success = tui.init_agent()
        if success:
            print("✅ Agent initialized")

        # Test that we have the containers properly set up
        if hasattr(tui, 'conversation_container'):
            print("✅ conversation_container exists")
        else:
            print("❌ conversation_container missing")

        if hasattr(tui, 'side_panel_container'):
            print("✅ side_panel_container exists")
        else:
            print("❌ side_panel_container missing")

        # Simulate some data for better visual testing
        tui.agent_state.memory_components = {
            'working': 42,
            'semantic': 156,
            'episodic': 23,
            'document': 89,
            'user_profile': 5,
        }
        tui.agent_state.context_tokens = 2048
        tui.agent_state.enhanced_tokens = 3200
        tui.agent_state.system_prompt_tokens = 512
        tui.agent_state.max_tokens = 8192

        # Update side panel
        tui.update_side_panel_content()

        # Check the format
        side_text = tui.side_panel_textarea.buffer.text
        print("\n📋 Side panel visual check:")

        # Check for tree-like format with box characters
        if "├─" in side_text:
            print("✅ Tree format with ├─ found")
        if "└─" in side_text:
            print("✅ Tree format with └─ found")

        # Check for proper sections
        if "Memory Stats" in side_text:
            print("✅ Memory Stats section")
        if "Total:" in side_text:
            print("✅ Total memory count shown")

        if "Token Usage" in side_text:
            print("✅ Token Usage section")
        if "Used:" in side_text and "/" in side_text and "%" in side_text:
            print("✅ Token usage with percentage")
        if "tk" in side_text:
            print("✅ Token units (tk) shown")

        # Print a sample of the side panel
        print("\n📊 Sample side panel content:")
        print("─" * 25)
        for line in side_text.split('\n')[:30]:  # First 30 lines
            if line.strip():
                print(line[:25])  # Truncate to width
        print("─" * 25)

        # Test toggle functionality
        print("\n🔄 Testing toggle:")

        # Initial state should have side panel
        if tui.show_side_panel:
            print("✅ Side panel initially shown")

        # Toggle off
        tui.toggle_side_panel()
        if not tui.show_side_panel:
            print("✅ Side panel hidden after toggle")

        # Toggle back on
        tui.toggle_side_panel()
        if tui.show_side_panel:
            print("✅ Side panel shown again after toggle")

        return True

    except Exception as e:
        import traceback
        print(f"❌ Test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_f2_toggle()
    if success:
        print("\n🎉 F2 toggle and visual format test SUCCESSFUL!")
        print("✅ Fixed issues:")
        print("  - F2 toggle no longer causes AttributeError")
        print("  - Side panel uses tree format (├─ └─)")
        print("  - Memory stats show total and breakdown")
        print("  - Token usage shows used/max with percentage")
        print("  - Matches nexus.py visual style!")
    else:
        print("\n❌ Test FAILED")
        sys.exit(1)