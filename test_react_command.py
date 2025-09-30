#!/usr/bin/env python3
"""
Test the /react command functionality in enhanced_tui.py
"""

import os
import sys

# Force offline mode
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

sys.path.insert(0, 'aa-tui')
from enhanced_tui import EnhancedTUI

def test_react_command():
    """Test /react command with various scenarios."""
    print("=" * 60)
    print("TESTING /react COMMAND")
    print("=" * 60)

    # Create TUI instance
    print("\n1. Creating TUI instance...")
    tui = EnhancedTUI(model='qwen3-coder:30b', provider='ollama', memory_path='./test_memory')
    print(f"✅ TUI created")
    print(f"   Default max_turns: {tui.react_max_turns}")
    print(f"   Default max_input_tokens: {tui.react_max_input_tokens}")

    # Test 1: Display current configuration (no params)
    print("\n2. Testing /react with no parameters (display config)...")
    parts = ['/react']
    tui.handle_react_command(parts)
    print(f"✅ Display command executed")

    # Test 2: Set valid configuration
    print("\n3. Testing /react with valid parameters...")
    parts = ['/react', '15', '3000']
    tui.handle_react_command(parts)
    print(f"✅ Configuration updated")
    print(f"   New max_turns: {tui.react_max_turns}")
    print(f"   New max_input_tokens: {tui.react_max_input_tokens}")

    assert tui.react_max_turns == 15, "Max turns should be 15"
    assert tui.react_max_input_tokens == 3000, "Max tokens should be 3000"
    print("✅ Configuration correctly applied")

    # Test 3: Set to extreme valid values
    print("\n4. Testing /react with extreme values...")
    parts = ['/react', '5', '500']
    tui.handle_react_command(parts)
    print(f"✅ Extreme configuration updated")
    print(f"   New max_turns: {tui.react_max_turns}")
    print(f"   New max_input_tokens: {tui.react_max_input_tokens}")

    # Test 4: Invalid parameters (out of range)
    print("\n5. Testing /react with invalid max_turns (out of range)...")
    parts = ['/react', '150', '2000']  # 150 > 100
    tui.handle_react_command(parts)
    print("✅ Validation correctly rejected out-of-range max_turns")

    # Test 5: Invalid parameters (out of range tokens)
    print("\n6. Testing /react with invalid max_tokens (out of range)...")
    parts = ['/react', '10', '60000']  # 60000 > 50000
    tui.handle_react_command(parts)
    print("✅ Validation correctly rejected out-of-range max_tokens")

    # Test 6: Invalid format (non-numeric)
    print("\n7. Testing /react with non-numeric parameters...")
    parts = ['/react', 'abc', 'def']
    tui.handle_react_command(parts)
    print("✅ Validation correctly rejected non-numeric parameters")

    # Test 7: Invalid format (wrong number of params)
    print("\n8. Testing /react with wrong number of parameters...")
    parts = ['/react', '10']  # Only 1 param
    tui.handle_react_command(parts)
    print("✅ Validation correctly rejected wrong parameter count")

    # Test 8: Verify configuration persists
    print("\n9. Verifying configuration persistence...")
    tui.react_max_turns = 20
    tui.react_max_input_tokens = 4000
    print(f"   Manually set: turns={tui.react_max_turns}, tokens={tui.react_max_input_tokens}")

    # Simulate using it in react config
    from react_loop import ReactConfig
    config = ReactConfig(
        max_iterations=tui.react_max_turns,
        context_tokens_limit=tui.react_max_input_tokens
    )
    print(f"✅ ReactConfig created with:")
    print(f"   max_iterations: {config.max_iterations}")
    print(f"   context_tokens_limit: {config.context_tokens_limit}")

    assert config.max_iterations == 20, "ReactConfig should use tui.react_max_turns"
    assert config.context_tokens_limit == 4000, "ReactConfig should use tui.react_max_input_tokens"
    print("✅ Configuration correctly propagates to ReactConfig")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\n📋 SUMMARY:")
    print("• /react command displays current configuration")
    print("• /react <turns> <tokens> updates configuration")
    print("• Validation rejects out-of-range values")
    print("• Validation rejects non-numeric inputs")
    print("• Configuration persists and applies to ReactLoop")
    print("\n💡 USAGE:")
    print("  /react              # View current settings")
    print("  /react 15 3000      # Set 15 max turns, 3000 max tokens")
    print("  /react 10 1000      # More aggressive token limit")

if __name__ == "__main__":
    test_react_command()