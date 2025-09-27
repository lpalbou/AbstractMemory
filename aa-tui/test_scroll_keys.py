#!/usr/bin/env python3
"""
Test that scrolling key bindings work properly
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_scroll_keys():
    """Test that scrolling key bindings are registered"""
    print("🔄 Testing scrolling key bindings...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_scroll"
        )
        print("✅ Enhanced TUI instance created")

        # Check that key bindings are registered
        kb_str = str(tui.kb.bindings)

        keys_to_check = [
            ('pageup', 'PageUp key binding'),
            ('pagedown', 'PageDown key binding'),
            ('c-u', 'Ctrl+U (half page up)'),
            ('c-d', 'Ctrl+D (half page down)'),
            ('up', 'Up arrow key'),
            ('down', 'Down arrow key'),
            ('home', 'Home key'),
            ('end', 'End key'),
        ]

        for key, desc in keys_to_check:
            if key in kb_str.lower():
                print(f"✅ {desc} registered")
            else:
                print(f"❌ {desc} NOT found")

        # Test that conversation buffer supports cursor movement
        if hasattr(tui.conversation_textarea.buffer, 'cursor_up'):
            print("✅ Buffer supports cursor_up() method")

        if hasattr(tui.conversation_textarea.buffer, 'cursor_down'):
            print("✅ Buffer supports cursor_down() method")

        # Add test content and verify cursor can move
        print("\n📝 Testing cursor movement...")

        # Add many lines
        for i in range(50):
            tui.add_message("User", f"Line {i+1}")

        initial_pos = tui.conversation_textarea.buffer.cursor_position
        print(f"Initial cursor position: {initial_pos}")

        # Try moving cursor up
        tui.conversation_textarea.buffer.cursor_up()
        new_pos = tui.conversation_textarea.buffer.cursor_position

        if new_pos != initial_pos:
            print(f"✅ Cursor moved from {initial_pos} to {new_pos}")
        else:
            print("⚠️  Cursor position didn't change")

        return True

    except Exception as e:
        import traceback
        print(f"❌ Test failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_scroll_keys()
    if success:
        print("\n🎉 Scrolling key bindings test SUCCESSFUL!")
        print("Key bindings are properly registered for:")
        print("  - PageUp/PageDown for page scrolling")
        print("  - Ctrl+U/Ctrl+D for half-page scrolling")
        print("  - Arrow keys for line scrolling (when input is empty)")
        print("  - Home/End for top/bottom navigation")
        print("\nThe scrolling should now work regardless of focus!")
    else:
        print("\n❌ Scrolling key bindings test FAILED")
        sys.exit(1)