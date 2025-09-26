#!/bin/bash

# Script to run the AbstractMemory TUI demo

echo "🚀 AbstractMemory TUI Demo"
echo "=========================="
echo ""
echo "This script will launch the TUI demo in your terminal."
echo "Make sure you have a terminal that supports:"
echo "- ANSI colors"
echo "- Mouse support (optional)"
echo "- Unicode characters"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read

echo "📦 Checking dependencies..."

# Check if we're in the right directory
if [ ! -f "test_tui.py" ]; then
    echo "❌ Error: Must run from aa-tui directory"
    echo "Usage: cd aa-tui && bash run_demo.sh"
    exit 1
fi

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python not found"
    exit 1
fi

echo "✅ Dependencies OK"
echo ""

echo "🎯 Starting TUI Demo..."
echo "• Use F1 for help"
echo "• Use F2 to toggle side panel"
echo "• Use Ctrl+Q to quit"
echo "• Try typing: hello, files, memory, or code"
echo ""

# Run the demo
python test_tui.py

echo ""
echo "👋 Demo ended. Thanks for trying AbstractMemory TUI!"