#!/bin/bash
# Quick launcher for the Autonomous Agent CLI

echo "🤖 Starting Autonomous Agent CLI..."
echo "Model: qwen3-coder:30b"
echo "Memory: ./agent_memory"
echo ""

python autonomous_agent_cli.py "$@"