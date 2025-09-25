#!/bin/bash
# Launcher for Autonomous Agent CLI with virtual environment

echo "🤖 Starting Autonomous Agent CLI with virtual environment..."

# Check if .venv exists
if [ -d ".venv" ]; then
    echo "✅ Activating virtual environment..."
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  No .venv found - using system Python"
fi

echo "Model: qwen3-coder:30b"
echo "Memory: ./agent_memory"
echo ""

python autonomous_agent_cli.py "$@"