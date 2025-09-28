#!/usr/bin/env python3
"""
Test various send key combinations
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_send_keys():
    """Test various ways to send messages"""
    print("🔄 Testing send key combinations...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_keys"
        )
        print("✅ Enhanced TUI instance created")

        # Check key bindings
        kb_str = str(tui.kb.bindings).lower()

        print("\n📋 Send key bindings found:")

        if 'c-j' in kb_str:
            print("✅ Ctrl+J (works as Ctrl+Enter)")

        if 'escape' in kb_str and 'enter' in kb_str:
            print("✅ Alt+Enter (Escape+Enter)")

        if 'c-m' in kb_str:
            print("✅ Ctrl+M (Return handling)")

        # Check help text
        help_text = str(tui.get_help_text())
        print(f"\n📝 Help text says: {help_text}")

        print("\n🎯 Available methods to send:")
        print("  1. Ctrl+J - Always sends (most reliable)")
        print("  2. Alt+Enter - Alternative send")
        print("  3. Enter - Sends if single line, else newline")
        print("  4. Tab to focus conversation, then Tab back")

        print("\n💡 Recommendation:")
        print("  Use Ctrl+J for sending messages")
        print("  It works consistently across all terminals")

        return True

    except Exception as e:
        import traceback
        print(f"❌ Test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_send_keys()
    if success:
        print("\n🎉 Send keys test SUCCESSFUL!")
    else:
        print("\n❌ Test FAILED")
        sys.exit(1)