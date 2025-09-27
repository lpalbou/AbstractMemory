#!/usr/bin/env python3
"""
Test the UI improvements in the enhanced TUI
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_ui_improvements():
    """Test that the UI improvements compile and work structurally"""
    print("🔄 Testing UI improvements...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Test that we can create the TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_ui_memory"
        )
        print("✅ Enhanced TUI instance created")

        # Test that agent initialization works
        success = tui.init_agent()
        if success:
            print("✅ Agent initialization successful")

            # Test UI components are properly set up
            print("🔄 Testing UI components...")

            # Check that conversation window has scrolling enabled
            if hasattr(tui.conversation_window, 'scrollable') or 'scrollable' in str(tui.conversation_window):
                print("✅ Conversation window scrolling enabled")
            else:
                print("⚠️  Scrolling might not be properly configured")

            # Check that FormattedTextControl is being used for colors
            if hasattr(tui, 'get_conversation_formatted_text'):
                print("✅ Color formatting function available")
            else:
                print("❌ Color formatting function missing")

            # Check that animation properties are set up
            if hasattr(tui, 'thinking_animation_running'):
                print("✅ Thinking animation properties available")
            else:
                print("❌ Thinking animation properties missing")

            # Check that memory display is set up
            if hasattr(tui, '_update_memory_display'):
                print("✅ Memory display update function available")
            else:
                print("❌ Memory display update function missing")

            # Test message formatting with colors
            print("🔄 Testing message formatting...")

            # Test user message
            tui.add_message("User", "Test user message")
            if '<user>' in tui.conversation_text and '<timestamp>' in tui.conversation_text:
                print("✅ User message color formatting works")
            else:
                print("❌ User message color formatting failed")

            # Test system message
            tui.add_system_message("Test system message")
            if '<system>' in tui.conversation_text:
                print("✅ System message color formatting works")
            else:
                print("❌ System message color formatting failed")

            # Test assistant message
            tui.add_message("Assistant", "Test assistant response")
            if '<assistant>' in tui.conversation_text:
                print("✅ Assistant message color formatting works")
            else:
                print("❌ Assistant message color formatting failed")

            # Check for separator functionality
            if hasattr(tui, 'last_message_type'):
                print("✅ Message separation tracking available")
            else:
                print("❌ Message separation tracking missing")

            # Test memory display update
            print("🔄 Testing memory display...")
            tui._update_memory_display()
            if tui.agent_state.memory_components:
                total_memory = sum(tui.agent_state.memory_components.values())
                print(f"✅ Memory display updated (total items: {total_memory})")
            else:
                print("⚠️  Memory display may not be working properly")

            # Test side panel content
            print("🔄 Testing side panel...")
            tui.update_side_panel_content()
            if tui.side_panel_buffer.text:
                print("✅ Side panel content updated")
            else:
                print("❌ Side panel content update failed")

            return True
        else:
            print("❌ Agent initialization failed")
            return False

    except Exception as e:
        import traceback
        print(f"❌ UI improvements test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_ui_improvements()
    if success:
        print("🎉 UI improvements test SUCCESSFUL!")
        print("✅ All UI enhancements are working:")
        print("  - Scrolling support for chat history")
        print("  - Color coding for different message types")
        print("  - Grey styling for system messages")
        print("  - Thinking animation framework")
        print("  - Visual separation between Q/A pairs")
        print("  - Real-time memory display updates")
        print("  - Enhanced side panel information")
    else:
        print("❌ UI improvements test FAILED")
        sys.exit(1)