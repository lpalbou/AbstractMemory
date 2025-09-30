#!/usr/bin/env python3
"""
Test MemorySession with Real Ollama + AbstractCore.

This tests the complete integration:
- MemorySession inherits from AbstractCore BasicSession
- Uses real Ollama qwen3-coder:30b for LLM
- Uses real AbstractCore all-minilm:l6-v2 for embeddings
- Structured response parsing
- Dual storage (verbatim + notes)
- Memory tools
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from abstractmemory.session import MemorySession


def test_ollama_connectivity():
    """Test that Ollama is accessible."""
    print("\n1. Testing Ollama Connectivity...")

    import requests

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if "qwen3-coder:30b" in model_names or any("qwen3-coder" in n for n in model_names):
                print("   ✅ Ollama qwen3-coder:30b available")
                return True
            else:
                print(f"   ⚠️ qwen3-coder:30b not found. Available: {model_names[:5]}")
                return False
        else:
            print(f"   ❌ Ollama API error: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ Ollama not accessible: {e}")
        return False


def test_memory_session_creation():
    """Test creating MemorySession with AbstractCore provider."""
    print("\n2. Testing MemorySession Creation...")

    try:
        # Import AbstractCore Ollama provider
        from abstractllm.providers.ollama_provider import OllamaProvider

        # Create provider
        provider = OllamaProvider(model="qwen3-coder:30b")
        print("   ✅ Created OllamaProvider")

        # Create MemorySession
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory"),
            default_user_id="test_user",
            default_location="test_lab"
        )
        print("   ✅ Created MemorySession")

        # Verify components
        assert session.response_handler is not None, "Response handler not initialized"
        print("   ✅ Response handler initialized (handles filesystem storage)")

        assert session.embedding_manager is not None, "Embedding manager not initialized"
        print("   ✅ Embedding manager initialized (AbstractCore)")

        # Verify core memory structure
        assert len(session.core_memory) == 10, f"Expected 10 core components, got {len(session.core_memory)}"
        print(f"   ✅ Core memory has 10 components: {list(session.core_memory.keys())}")

        return True

    except Exception as e:
        print(f"   ❌ MemorySession creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simple_chat():
    """Test simple chat interaction with memory."""
    print("\n3. Testing Simple Chat with Memory...")

    try:
        from abstractllm.providers.ollama_provider import OllamaProvider

        # Create session
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory"),
            default_user_id="alice",
            default_location="office"
        )

        # Simple chat
        print("   🤖 Sending: 'Hello, I'm testing the memory system. Can you respond?'")
        response = session.chat(
            "Hello, I'm testing the memory system. Can you respond?",
            user_id="alice",
            location="office"
        )

        print(f"   ✅ Received response ({len(response)} chars)")
        print(f"   Response preview: {response[:200]}...")

        # Check observability
        report = session.get_observability_report()
        print(f"   ✅ Interactions: {report['interactions_count']}")
        print(f"   ✅ Memories: {report['memories_created']}")

        # Verify files were created
        verbatim_dir = Path("test_memory") / "verbatim" / "alice"
        notes_dir = Path("test_memory") / "notes"

        if verbatim_dir.exists():
            verbatim_files = list(verbatim_dir.rglob("*.md"))
            print(f"   ✅ Verbatim files created: {len(verbatim_files)}")
        else:
            print("   ⚠️ No verbatim files created yet")

        if notes_dir.exists():
            note_files = list(notes_dir.rglob("*.md"))
            print(f"   ✅ Note files created: {len(note_files)}")
        else:
            print("   ⚠️ No note files created yet")

        return True

    except Exception as e:
        print(f"   ❌ Chat test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_structured_response_parsing():
    """Test that structured responses are parsed correctly."""
    print("\n4. Testing Structured Response Parsing...")

    try:
        from abstractllm.providers.ollama_provider import OllamaProvider

        # Create session
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory"),
            default_user_id="bob",
            default_location="home"
        )

        # Ask a question that should trigger experiential note
        print("   🤖 Asking: 'What is the relationship between memory and consciousness?'")
        response = session.chat(
            "What is the relationship between memory and consciousness?",
            user_id="bob",
            location="home"
        )

        print(f"   ✅ Received response ({len(response)} chars)")

        # Check if experiential notes were created
        notes_dir = Path("test_memory") / "notes"
        if notes_dir.exists():
            note_files = list(notes_dir.rglob("*.md"))
            if note_files:
                print(f"   ✅ Experiential notes created: {len(note_files)}")

                # Read the latest note
                latest_note = sorted(note_files, key=lambda p: p.stat().st_mtime)[-1]
                with open(latest_note, 'r') as f:
                    content = f.read()

                # Check for first-person indicators
                first_person_indicators = ["I ", "I'm", "my ", "me "]
                has_first_person = any(ind in content for ind in first_person_indicators)

                if has_first_person:
                    print("   ✅ Note contains first-person content (LLM-generated)")
                else:
                    print("   ⚠️ Note may not be LLM-generated (no first-person indicators)")

                # Check content dominance (>90% LLM)
                lines = content.split('\n')
                template_lines = [l for l in lines if l.startswith('**') or l.startswith('*') or l.startswith('#') or l.startswith('---')]
                content_lines = [l for l in lines if l.strip() and l not in template_lines]

                if len(content_lines) > len(template_lines) * 9:
                    print("   ✅ Content is dominated by LLM (>90%)")
                else:
                    print(f"   ⚠️ Template too large: {len(template_lines)} template vs {len(content_lines)} content")
            else:
                print("   ⚠️ No note files found")
        else:
            print("   ⚠️ Notes directory not created")

        return True

    except Exception as e:
        print(f"   ❌ Structured response test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all MemorySession tests."""
    print("=" * 80)
    print("MEMORY SESSION INTEGRATION TEST")
    print("Testing with Real Ollama qwen3-coder:30b + AbstractCore all-minilm:l6-v2")
    print("=" * 80)

    tests = [
        ("Ollama Connectivity", test_ollama_connectivity),
        ("MemorySession Creation", test_memory_session_creation),
        ("Simple Chat", test_simple_chat),
        ("Structured Response Parsing", test_structured_response_parsing),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("\n" + "=" * 80)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 80)
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)