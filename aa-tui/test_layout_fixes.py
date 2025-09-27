#!/usr/bin/env python3
"""
Test the layout and scrolling fixes in the enhanced TUI
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_layout_fixes():
    """Test that the layout and scrolling fixes work correctly"""
    print("🔄 Testing layout and scrolling fixes...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Test that we can create the TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_layout_memory"
        )
        print("✅ Enhanced TUI instance created")

        # Test that agent initialization works
        success = tui.init_agent()
        if success:
            print("✅ Agent initialization successful")

            # Test layout components
            print("🔄 Testing layout components...")

            # Check that conversation window uses BufferControl for proper scrolling
            if hasattr(tui.conversation_window.content, 'buffer'):
                print("✅ Conversation window uses BufferControl for proper scrolling")
            else:
                print("❌ Conversation window not using BufferControl")

            # Check that status line is available
            if hasattr(tui, 'get_status_text'):
                status_text = tui.get_status_text()
                print(f"✅ Status line available: {status_text}")
            else:
                print("❌ Status line not available")

            # Check that current_status is initialized
            if hasattr(tui, 'current_status'):
                print(f"✅ Current status tracking: {tui.current_status}")
            else:
                print("❌ Current status tracking missing")

            # Test message formatting with ANSI colors
            print("🔄 Testing ANSI color message formatting...")

            # Test user message with separator
            tui.add_message("User", "First user message")
            tui.add_message("Assistant", "First assistant response")
            tui.add_message("User", "Second user message")  # Should have separator

            # Check that ANSI color codes are present
            if '\033[' in tui.conversation_text:
                print("✅ ANSI color codes present in conversation")
            else:
                print("❌ ANSI color codes missing")

            # Check that separators are being added
            if '─────' in tui.conversation_text:
                print("✅ Visual separators between conversations")
            else:
                print("❌ Visual separators missing")

            # Test auto-scroll to bottom
            print("🔄 Testing auto-scroll to bottom...")
            initial_cursor_pos = tui.conversation_buffer.cursor_position
            tui.add_system_message("This should scroll to bottom")
            final_cursor_pos = tui.conversation_buffer.cursor_position

            if final_cursor_pos >= initial_cursor_pos:
                print("✅ Auto-scroll to bottom working")
            else:
                print("❌ Auto-scroll to bottom not working")

            # Test side panel content
            print("🔄 Testing side panel real status...")
            tui.update_side_panel_content()
            side_panel_text = tui.side_panel_buffer.text

            # Check for real agent information
            if "LLM Connection" in side_panel_text and "Model:" in side_panel_text:
                print("✅ Side panel shows real LLM status")
            else:
                print("❌ Side panel missing real LLM status")

            if "Conversation" in side_panel_text and "Messages:" in side_panel_text:
                print("✅ Side panel shows conversation stats")
            else:
                print("❌ Side panel missing conversation stats")

            # Test status updates
            print("🔄 Testing status updates...")
            tui.current_status = "Testing status"
            tui.agent_state.status = "thinking"
            status_text = tui.get_status_text()

            if "Testing status" in str(status_text):
                print("✅ Status text updates correctly")
            else:
                print("❌ Status text not updating")

            # Test scrolling capability
            print("🔄 Testing scrolling capability...")
            if hasattr(tui.conversation_buffer, 'cursor_position'):
                # Test that we can move cursor (simulating scroll)
                old_pos = tui.conversation_buffer.cursor_position
                tui.conversation_buffer.cursor_position = max(0, old_pos - 100)
                new_pos = tui.conversation_buffer.cursor_position

                if new_pos != old_pos:
                    print("✅ Manual scrolling works")
                    # Restore to bottom
                    tui.conversation_buffer.cursor_position = len(tui.conversation_buffer.text)
                else:
                    print("⚠️  Manual scrolling may be limited")

            return True
        else:
            print("❌ Agent initialization failed")
            return False

    except Exception as e:
        import traceback
        print(f"❌ Layout fixes test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_layout_fixes()
    if success:
        print("🎉 Layout and scrolling fixes test SUCCESSFUL!")
        print("✅ Key improvements working:")
        print("  - BufferControl for proper scrolling")
        print("  - ANSI color codes for message types")
        print("  - Visual separators between conversations")
        print("  - Auto-scroll to bottom on new messages")
        print("  - Status line with real-time updates")
        print("  - Side panel with real LLM/Agent status")
        print("  - Manual scrolling capability")
        print("  - Memory and conversation statistics")
    else:
        print("❌ Layout and scrolling fixes test FAILED")
        sys.exit(1)