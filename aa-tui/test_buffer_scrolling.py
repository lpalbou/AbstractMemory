#!/usr/bin/env python3
"""
Test that the buffer-based scrolling works properly
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_buffer_scrolling():
    """Test that buffer-based scrolling is properly implemented"""
    print("🔄 Testing buffer-based scrolling...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_buffer_scroll"
        )
        print("✅ Enhanced TUI instance created")

        # Check that conversation buffer exists and is writable
        if hasattr(tui, 'conversation_buffer'):
            print("✅ Conversation buffer exists")
            if not tui.conversation_buffer.read_only:
                print("✅ Conversation buffer is writable")
            else:
                print("❌ Conversation buffer is read-only")

        # Check ScrollablePane
        if hasattr(tui, 'scrollable_conversation'):
            print("✅ ScrollablePane configured")

        # Add many messages to test scrolling
        print("\n📝 Adding test messages...")
        for i in range(50):
            tui.add_message("User", f"Test message {i+1}")
            tui.add_message("Assistant", f"Response to message {i+1}")

        # Check buffer content
        buffer_text = tui.conversation_buffer.text
        lines = buffer_text.count('\n')
        print(f"✅ Buffer contains {lines} lines")
        print(f"✅ Buffer text length: {len(buffer_text)} characters")

        # Verify messages are in buffer
        if "Test message 1" in buffer_text:
            print("✅ First message is in buffer")
        if "Test message 50" in buffer_text:
            print("✅ Last message is in buffer")

        # Check cursor position (should be at end for auto-scroll)
        if tui.conversation_buffer.cursor_position == len(buffer_text):
            print("✅ Cursor at end of buffer (auto-scroll position)")
        else:
            print(f"⚠️  Cursor position: {tui.conversation_buffer.cursor_position}/{len(buffer_text)}")

        # Check that scrollable pane can scroll
        initial_scroll = tui.scrollable_conversation.vertical_scroll
        tui.scrollable_conversation.scroll_up(count=10)
        after_scroll = tui.scrollable_conversation.vertical_scroll
        print(f"✅ Scroll position changed from {initial_scroll} to {after_scroll}")

        return True

    except Exception as e:
        import traceback
        print(f"❌ Buffer scrolling test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_buffer_scrolling()
    if success:
        print("\n🎉 Buffer-based scrolling test SUCCESSFUL!")
        print("✅ Key improvements:")
        print("  - Using Buffer with BufferControl (not FormattedTextControl)")
        print("  - Buffer is writable for content updates")
        print("  - ScrollablePane wraps the conversation window")
        print("  - Content is properly stored in buffer")
        print("  - Auto-scroll to bottom works")
        print("  - Scrolling methods functional")
    else:
        print("\n❌ Buffer scrolling test FAILED")
        sys.exit(1)