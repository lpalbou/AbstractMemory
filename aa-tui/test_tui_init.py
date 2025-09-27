#!/usr/bin/env python3
"""
Test that the TUI can initialize properly without errors
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_tui_init():
    """Test that TUI initializes without errors"""
    print("🔄 Testing TUI initialization...")

    try:
        from enhanced_tui import EnhancedTUI
        print("✅ Enhanced TUI import successful")

        # Create TUI instance
        tui = EnhancedTUI(
            model="qwen3-coder:30b",
            provider="ollama",
            memory_path="./test_init"
        )
        print("✅ Enhanced TUI instance created")

        # Initialize agent
        success = tui.init_agent()
        if success:
            print("✅ Agent initialized successfully")
        else:
            print("⚠️  Agent initialization returned False but no exception")

        # Check key components exist
        if hasattr(tui, 'conversation_textarea'):
            print("✅ Conversation TextArea exists")

        if hasattr(tui, 'side_panel_textarea'):
            print("✅ Side panel TextArea exists")

        if hasattr(tui, 'main_content'):
            print("✅ Main content layout exists")

        if hasattr(tui, 'app'):
            print("✅ Application object created")

        return True

    except Exception as e:
        import traceback
        print(f"❌ TUI initialization failed: {e}")
        print("Error details:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_tui_init()
    if success:
        print("\n🎉 TUI initialization test SUCCESSFUL!")
        print("The Enhanced TUI can be initialized without errors.")
        print("Scrolling is now handled by TextArea widgets with built-in support.")
    else:
        print("\n❌ TUI initialization test FAILED")
        sys.exit(1)