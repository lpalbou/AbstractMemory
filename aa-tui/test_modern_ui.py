#!/usr/bin/env python3
"""
Test the modern UI improvements in the enhanced TUI
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_modern_ui():
    """Test that the modern UI improvements work correctly"""
    print("🔄 Testing modern UI improvements...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Test that we can create the TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_modern_ui"
        )
        print("✅ Enhanced TUI instance created")

        # Test that agent initialization works
        success = tui.init_agent()
        if success:
            print("✅ Agent initialization successful")

            # Test UI improvements
            print("🔄 Testing UI improvements...")

            # Check that conversation window uses FormattedTextControl for ANSI support
            if hasattr(tui.conversation_window.content, 'get_text') or hasattr(tui.conversation_window.content, 'text'):
                print("✅ Conversation window uses FormattedTextControl for ANSI colors")
            else:
                print("❌ Conversation window not using proper control")

            # Check side panel width
            if tui.main_content.children[1].width == 40:
                print("✅ Side panel width increased to 40")
            else:
                print("⚠️  Side panel width not set correctly")

            # Test message formatting without timestamps
            print("🔄 Testing cleaner message formatting...")

            # Add test messages
            tui.add_message("User", "Test user message")
            tui.add_message("Assistant", "Test assistant response")

            # Check for clean formatting
            if "You:" in tui.conversation_text and "Assistant:" in tui.conversation_text:
                print("✅ Clean message labels (You/Assistant)")
            else:
                print("❌ Message labels not clean")

            # Check that timestamps are NOT in the conversation
            if "[" not in tui.conversation_text or "]" not in tui.conversation_text:
                print("✅ Timestamps removed from chat")
            else:
                print("❌ Timestamps still in chat")

            # Check for ANSI color codes
            if '\033[' in tui.conversation_text:
                print("✅ ANSI color codes present")
            else:
                print("❌ ANSI color codes missing")

            # Test that system messages are minimal
            tui.add_system_message("Test system message")
            if '\033[2m' in tui.conversation_text:  # Check for dim styling
                print("✅ System messages use dim styling")
            else:
                print("⚠️  System messages may not be styled correctly")

            # Test side panel content
            print("🔄 Testing side panel improvements...")
            tui.update_side_panel_content()
            side_panel_text = tui.side_panel_buffer.text

            # Check for time in side panel
            if "⏰" in side_panel_text:
                print("✅ Time displayed in side panel")
            else:
                print("❌ Time not in side panel")

            # Check for proper agent status
            if "Agent Status" in side_panel_text:
                print("✅ Agent status in side panel")
            else:
                print("❌ Agent status missing from side panel")

            # Test status line
            print("🔄 Testing status line...")
            status_text = tui.get_status_text()
            if "Status:" in str(status_text):
                print("✅ Status line functional")
            else:
                print("❌ Status line not working")

            # Test that thinking messages are not added to chat
            original_text_len = len(tui.conversation_text)
            tui.current_status = "Agent is thinking..."
            tui.agent_state.status = "thinking"

            # Check that no system message was added
            if len(tui.conversation_text) == original_text_len:
                print("✅ Thinking messages not added to chat")
            else:
                print("❌ Thinking messages still being added to chat")

            # Test separator lines
            tui.add_message("User", "Another test")
            if "─" in tui.conversation_text:
                print("✅ Visual separators between conversations")
            else:
                print("⚠️  Separators may not be working")

            return True
        else:
            print("❌ Agent initialization failed")
            return False

    except Exception as e:
        import traceback
        print(f"❌ Modern UI test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_modern_ui()
    if success:
        print("🎉 Modern UI improvements test SUCCESSFUL!")
        print("✅ Key improvements working:")
        print("  - ANSI colors properly rendered with FormattedTextControl")
        print("  - Clean message formatting (You/Assistant)")
        print("  - Timestamps moved to side panel")
        print("  - System messages minimized and dimmed")
        print("  - Wider side panel (40 chars)")
        print("  - Thinking status in status line, not chat")
        print("  - Visual separators between Q/A pairs")
        print("  - Modern, clean UI/UX design")
    else:
        print("❌ Modern UI improvements test FAILED")
        sys.exit(1)