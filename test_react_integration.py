#!/usr/bin/env python3
"""
Integration test showing how /react command controls the ReAct loop behavior.
"""

import os
import sys

os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

sys.path.insert(0, 'aa-tui')
from enhanced_tui import EnhancedTUI
from react_loop import ReactConfig

def test_react_integration():
    """Test that /react command properly configures the ReAct loop."""
    print("=" * 60)
    print("REACT COMMAND INTEGRATION TEST")
    print("=" * 60)

    tui = EnhancedTUI(model='qwen3-coder:30b', provider='ollama', memory_path='./test_memory')

    print("\n📊 SCENARIO 1: Default Configuration")
    print("-" * 40)
    print(f"Max Turns: {tui.react_max_turns}")
    print(f"Max Input Tokens: {tui.react_max_input_tokens}")

    # Simulate creating ReactConfig as done in _process_agent_response
    config1 = ReactConfig(
        max_iterations=tui.react_max_turns,
        observation_display_limit=500,
        include_memory=True,
        context_tokens_limit=tui.react_max_input_tokens
    )

    print("\nReactConfig created:")
    print(f"  max_iterations: {config1.max_iterations}")
    print(f"  context_tokens_limit: {config1.context_tokens_limit}")
    print("\n💡 With default settings:")
    print("   • Agent can take up to 25 reasoning turns")
    print("   • Initial context limited to last 2000 tokens")

    print("\n" + "=" * 60)
    print("📊 SCENARIO 2: Aggressive Configuration")
    print("-" * 40)
    print("User types: /react 10 1000")

    # Simulate the /react command
    tui.handle_react_command(['/react', '10', '1000'])

    print(f"\nUpdated configuration:")
    print(f"Max Turns: {tui.react_max_turns}")
    print(f"Max Input Tokens: {tui.react_max_input_tokens}")

    config2 = ReactConfig(
        max_iterations=tui.react_max_turns,
        observation_display_limit=500,
        include_memory=True,
        context_tokens_limit=tui.react_max_input_tokens
    )

    print("\nReactConfig created:")
    print(f"  max_iterations: {config2.max_iterations}")
    print(f"  context_tokens_limit: {config2.context_tokens_limit}")
    print("\n💡 With aggressive settings:")
    print("   • Agent limited to 10 reasoning turns")
    print("   • Only last 1000 tokens used for context")
    print("   • Faster responses, less context retention")

    print("\n" + "=" * 60)
    print("📊 SCENARIO 3: Extended Configuration")
    print("-" * 40)
    print("User types: /react 50 8000")

    tui.handle_react_command(['/react', '50', '8000'])

    print(f"\nUpdated configuration:")
    print(f"Max Turns: {tui.react_max_turns}")
    print(f"Max Input Tokens: {tui.react_max_input_tokens}")

    config3 = ReactConfig(
        max_iterations=tui.react_max_turns,
        observation_display_limit=500,
        include_memory=True,
        context_tokens_limit=tui.react_max_input_tokens
    )

    print("\nReactConfig created:")
    print(f"  max_iterations: {config3.max_iterations}")
    print(f"  context_tokens_limit: {config3.context_tokens_limit}")
    print("\n💡 With extended settings:")
    print("   • Agent can take up to 50 reasoning turns")
    print("   • Uses last 8000 tokens for rich context")
    print("   • Better for complex multi-step tasks")

    print("\n" + "=" * 60)
    print("📊 SCENARIO 4: Minimal Configuration")
    print("-" * 40)
    print("User types: /react 3 500")

    tui.handle_react_command(['/react', '3', '500'])

    print(f"\nUpdated configuration:")
    print(f"Max Turns: {tui.react_max_turns}")
    print(f"Max Input Tokens: {tui.react_max_input_tokens}")

    config4 = ReactConfig(
        max_iterations=tui.react_max_turns,
        observation_display_limit=500,
        include_memory=True,
        context_tokens_limit=tui.react_max_input_tokens
    )

    print("\nReactConfig created:")
    print(f"  max_iterations: {config4.max_iterations}")
    print(f"  context_tokens_limit: {config4.context_tokens_limit}")
    print("\n💡 With minimal settings:")
    print("   • Agent limited to just 3 turns")
    print("   • Only last 500 tokens (very recent context)")
    print("   • Ultra-fast, focused responses")

    print("\n" + "=" * 60)
    print("✅ INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print("\n📚 KEY INSIGHTS:")
    print("\n1. Context Window Control:")
    print("   • max_input_tokens controls how much conversation history")
    print("     is provided to the agent at the START of ReAct loop")
    print("   • Lower values = faster, more focused")
    print("   • Higher values = more context-aware")
    print("\n2. Turn Limit Control:")
    print("   • max_turns limits reasoning iterations")
    print("   • Lower values = faster responses")
    print("   • Higher values = more thorough reasoning")
    print("\n3. Practical Use Cases:")
    print("   • Quick questions: /react 5 1000")
    print("   • Normal usage: /react 25 2000 (default)")
    print("   • Complex tasks: /react 50 5000")
    print("   • Long conversations: /react 30 8000")

if __name__ == "__main__":
    test_react_integration()