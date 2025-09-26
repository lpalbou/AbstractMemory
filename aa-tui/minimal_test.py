#!/usr/bin/env python3
"""
Minimal test to isolate the color format issue.
"""

import asyncio
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

# Test different style approaches
def test_styles():
    print("Testing style definitions...")

    # Test 1: Very basic style
    try:
        basic_style = Style.from_dict({
            '': '#ffffff',
            'title': '#00ff00',
        })
        print("✅ Basic style OK")
    except Exception as e:
        print(f"❌ Basic style failed: {e}")

    # Test 2: Style with bold
    try:
        bold_style = Style.from_dict({
            '': '#ffffff',
            'title': 'bold #00ff00',
        })
        print("✅ Bold style OK")
    except Exception as e:
        print(f"❌ Bold style failed: {e}")

    # Test 3: FormattedText with style
    try:
        formatted_text = FormattedText([
            ('title', 'Test Title'),
        ])
        print("✅ FormattedText OK")
    except Exception as e:
        print(f"❌ FormattedText failed: {e}")

async def minimal_app():
    """Minimal app to test styling."""
    test_styles()

    # Simplest possible style
    style = Style.from_dict({
        '': '#ffffff',
        'title': '#00ff00',
    })

    # Simple content
    content = Window(
        content=FormattedTextControl(
            text=FormattedText([('title', 'Test Title')])
        ),
        height=1
    )

    layout = Layout(HSplit([content]))

    app = Application(
        layout=layout,
        style=style,
        full_screen=False  # Try without full screen first
    )

    print("🎯 Starting minimal app...")
    try:
        # Don't actually run, just test creation
        print("✅ App created successfully!")
        return True
    except Exception as e:
        print(f"❌ App creation failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(minimal_app())