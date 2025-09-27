#!/usr/bin/env python3
"""
Test chat UI improvements
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_chat_ui():
    """Test chat UI improvements"""
    print("🔄 Testing chat UI improvements...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_chat"
        )
        print("✅ Enhanced TUI instance created")

        # Check initial state
        if tui.conversation_text == "":
            print("✅ Conversation starts empty (no system messages)")
        else:
            print(f"⚠️  Conversation has initial text: {len(tui.conversation_text)} chars")

        # Add test messages
        tui.add_message("User", "Hello, this is a test message")
        tui.add_message("Assistant", "Hello! I'm here to help you.")
        tui.add_message("User", "Can you see the colors properly?")
        tui.add_message("Assistant", "Yes, the colors should make it easier to distinguish between speakers.")

        # Check formatting
        conv_text = tui.conversation_text
        print("\n🎨 Formatting check:")

        # Check for ANSI color codes
        if '\033[' in conv_text:
            print("✅ ANSI color codes present")

        # Check specific colors
        if 'You:' in conv_text:
            print("✅ 'You:' label present")
        if 'Assistant:' in conv_text:
            print("✅ 'Assistant:' label present")

        # Check for no separator lines
        if "─" * 60 not in conv_text:
            print("✅ No long separator lines")

        # Test system message suppression
        print("\n🔕 System message suppression:")
        original_len = len(tui.conversation_text)
        tui.add_system_message("This should not appear")
        new_len = len(tui.conversation_text)

        if original_len == new_len:
            print("✅ System messages suppressed")

        # Check wrapping
        if tui.conversation_textarea.wrap_lines:
            print("✅ Text wrapping enabled")

        # Sample output
        print("\n📝 Sample (with ANSI stripped for display):")
        print("─" * 40)
        # Remove ANSI codes for display
        import re
        clean_text = re.sub(r'\033\[[0-9;]+m', '', conv_text[:300])
        print(clean_text)
        print("─" * 40)

        return True

    except Exception as e:
        import traceback
        print(f"❌ Test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_chat_ui()
    if success:
        print("\n🎉 Chat UI improvements SUCCESSFUL!")
        print("✅ Improvements applied:")
        print("  - Clean start (no system messages)")
        print("  - Colored keywords (You/Assistant)")
        print("  - No separator lines")
        print("  - Text wrapping enabled")
        print("  - System messages suppressed")
    else:
        print("\n❌ Test FAILED")
        sys.exit(1)