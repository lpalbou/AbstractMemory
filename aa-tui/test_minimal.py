#!/usr/bin/env python3
"""
Minimal test to isolate the exact issue
"""

import sys
from pathlib import Path

# Add the project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from abstractllm import create_llm
    from abstractmemory import MemorySession, MemoryConfig
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_step_by_step():
    """Test each step individually"""

    print("🔄 Testing step by step...")

    # Step 1: Test create_llm
    try:
        print("1. Testing create_llm...")
        provider = create_llm("ollama", model="qwen3-coder:30b", timeout=7200.0)
        print(f"✅ create_llm successful: {type(provider)}")
        print(f"   Provider attributes: {dir(provider)}")
    except Exception as e:
        print(f"❌ create_llm failed: {e}")
        return False

    # Step 2: Test MemoryConfig
    try:
        print("2. Testing MemoryConfig...")
        memory_config = MemoryConfig.agent_mode()
        memory_config.enable_memory_tools = True
        memory_config.enable_self_editing = True
        print(f"✅ MemoryConfig successful: {type(memory_config)}")
    except Exception as e:
        print(f"❌ MemoryConfig failed: {e}")
        return False

    # Step 3: Test MemorySession with minimal params
    try:
        print("3. Testing MemorySession with minimal params...")
        session = MemorySession(provider)
        print(f"✅ Minimal MemorySession successful: {type(session)}")
    except Exception as e:
        print(f"❌ Minimal MemorySession failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Test MemorySession with full params
    try:
        print("4. Testing MemorySession with full params...")
        session_full = MemorySession(
            provider,
            tools=[],
            memory_config={"path": "./test_memory", "semantic_threshold": 1},
            default_memory_config=memory_config,
            system_prompt="Test prompt"
        )
        print(f"✅ Full MemorySession successful: {type(session_full)}")
        return True
    except Exception as e:
        print(f"❌ Full MemorySession failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_step_by_step()
    if success:
        print("🎉 All tests passed!")
    else:
        print("❌ Tests failed")
        sys.exit(1)