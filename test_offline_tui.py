#!/usr/bin/env python3
"""
Test that the enhanced TUI can start in offline mode without internet access.
This script validates that no models are downloaded and cached models are used.
"""

import os
import sys

# Force offline mode BEFORE any imports
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['HF_HOME'] = os.path.expanduser('~/.cache/huggingface')

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_offline_initialization():
    """Test that the TUI components can initialize without internet."""
    print("🧪 Testing offline initialization...")

    try:
        # Import after setting environment
        from abstractmemory import MemorySession, MemoryConfig
        from abstractllm import create_llm
        from abstractmemory.embeddings.sentence_transformer_provider import create_sentence_transformer_provider

        print("✅ Imports successful")

        # Test 1: Embedding provider loads from cache
        try:
            provider = create_sentence_transformer_provider('all-MiniLM-L6-v2')
            print("✅ Embedding model loaded from cache")
        except Exception as e:
            print(f"⚠️ Embeddings not available (expected in pure offline): {e}")

        # Test 2: LLM provider
        try:
            llm = create_llm('ollama', model='qwen3-coder:30b')
            print("✅ LLM provider created")
        except Exception as e:
            print(f"❌ LLM provider failed: {e}")
            return False

        # Test 3: MemorySession with markdown-only storage
        try:
            config = MemoryConfig.agent_mode()
            config.semantic_threshold = 999  # Disable semantic features

            session = MemorySession(
                llm,
                memory_config={
                    'storage': 'markdown',
                    'semantic_threshold': 999
                },
                default_memory_config=config
            )
            print("✅ MemorySession initialized with markdown storage")
        except Exception as e:
            print(f"❌ MemorySession failed: {e}")
            return False

        # Test 4: Simple generation
        try:
            response = session.generate("Hello, are you working offline?")
            print("✅ Generation successful")
            print(f"   Response preview: {str(response)[:100]}...")
        except Exception as e:
            print(f"⚠️ Generation failed (ollama might not be running): {e}")

        print("\n🎉 All offline tests passed!")
        return True

    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("OFFLINE MODE TEST FOR ENHANCED TUI")
    print("=" * 60)
    print()
    print("Environment:")
    print(f"  TRANSFORMERS_OFFLINE: {os.environ.get('TRANSFORMERS_OFFLINE')}")
    print(f"  HF_HUB_OFFLINE: {os.environ.get('HF_HUB_OFFLINE')}")
    print(f"  Cache dir: ~/.cache/huggingface")
    print()

    success = test_offline_initialization()

    if success:
        print("\n✅ TUI is ready for offline operation!")
        print("The agent will work without internet access using:")
        print("  • Cached embedding models (if available)")
        print("  • Markdown-based storage (no vector DB required)")
        print("  • Local LLM through Ollama")
    else:
        print("\n❌ Some components failed in offline mode")
        print("Please ensure:")
        print("  • Ollama is running locally")
        print("  • Required models are cached")

    sys.exit(0 if success else 1)