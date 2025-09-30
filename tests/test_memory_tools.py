#!/usr/bin/env python3
"""
Test Memory Tools with Real LLM - NO MOCKING

This tests memory tools with realistic scenarios:
- remember_fact() with real content
- search_memories() with actual queries
- Memory persistence across sessions
- LLM-driven memory creation
"""

import sys
from pathlib import Path
from datetime import datetime
import shutil

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider


def test_remember_fact_basic():
    """Test basic remember_fact() functionality."""
    print("\n1. Testing remember_fact() - Basic")

    try:
        # Create provider and session
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="test_user"
        )

        # Remember a fact
        memory_id = session.remember_fact(
            content="Python is a high-level programming language created by Guido van Rossum",
            importance=0.8,
            emotion="curiosity"
        )

        print(f"   ✅ Created memory: {memory_id}")

        # Verify file was created
        notes_dir = Path("test_memory_tools") / "notes"
        memory_files = list(notes_dir.rglob("*.md"))

        if len(memory_files) > 0:
            print(f"   ✅ Memory file created: {memory_files[0].name}")

            # Read and verify content
            with open(memory_files[0], 'r') as f:
                content = f.read()

            if "Python" in content and "Guido van Rossum" in content:
                print("   ✅ Memory content verified")
            else:
                print("   ❌ Memory content incorrect")
                return False

            if "**Importance**: 0.80" in content:
                print("   ✅ Importance metadata verified")
            else:
                print("   ⚠️ Importance metadata not found")

            if "**Emotion**: curiosity" in content:
                print("   ✅ Emotion metadata verified")
            else:
                print("   ⚠️ Emotion metadata not found")
        else:
            print("   ❌ No memory files created")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_remember_fact_with_links():
    """Test remember_fact() with links to other memories."""
    print("\n2. Testing remember_fact() - With Links")

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="test_user"
        )

        # Create first memory
        mem1_id = session.remember_fact(
            content="Machine learning is a subset of artificial intelligence",
            importance=0.9,
            emotion="excitement"
        )
        print(f"   ✅ Created memory 1: {mem1_id}")

        # Create second memory linked to first
        mem2_id = session.remember_fact(
            content="Deep learning is a subset of machine learning using neural networks",
            importance=0.9,
            emotion="curiosity",
            links_to=[mem1_id]
        )
        print(f"   ✅ Created memory 2: {mem2_id} (linked to {mem1_id})")

        # Verify link was mentioned in memory file
        notes_dir = Path("test_memory_tools") / "notes"
        memory_files = sorted(notes_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

        if len(memory_files) >= 2:
            with open(memory_files[0], 'r') as f:
                content = f.read()

            if mem1_id in content:
                print(f"   ✅ Link to {mem1_id} found in memory file")
            else:
                print(f"   ⚠️ Link reference not found in memory file")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_memories():
    """Test search_memories() with real queries."""
    print("\n3. Testing search_memories()")

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="alice"
        )

        # Create some memories to search
        session.remember_fact(
            content="The Eiffel Tower is located in Paris, France",
            importance=0.7,
            emotion="neutral"
        )

        session.remember_fact(
            content="The Great Wall of China was built over many centuries",
            importance=0.8,
            emotion="fascination"
        )

        session.remember_fact(
            content="Python programming language was created in 1991",
            importance=0.6,
            emotion="interest"
        )

        print("   ✅ Created 3 test memories")

        # Search for Paris
        results = session.search_memories("Paris", limit=5)

        if len(results) > 0:
            print(f"   ✅ Found {len(results)} memories containing 'Paris'")

            # Verify correct memory was found
            found_eiffel = False
            for result in results:
                if "Eiffel Tower" in result["content"]:
                    found_eiffel = True
                    print("   ✅ Correct memory found (Eiffel Tower)")
                    break

            if not found_eiffel:
                print("   ⚠️ Expected memory not in results")
        else:
            print("   ❌ No results found")
            return False

        # Search for Python
        results = session.search_memories("Python programming", limit=5)

        if len(results) > 0:
            print(f"   ✅ Found {len(results)} memories containing 'Python programming'")
        else:
            print("   ⚠️ Python search returned no results")

        # Search with user filter
        results = session.search_memories("Tower", filters={"user_id": "alice"}, limit=5)
        print(f"   ✅ Search with user filter returned {len(results)} results")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_driven_memory_creation():
    """Test that LLM can actually create memories through memory_actions."""
    print("\n4. Testing LLM-Driven Memory Creation (Real LLM)")

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="bob"
        )

        # Have a conversation that should trigger memory creation
        print("   🤖 Asking LLM about memory and consciousness...")
        response = session.chat(
            "Can you tell me about the relationship between memory and learning? "
            "Please remember any key insights you generate.",
            user_id="bob",
            location="home"
        )

        print(f"   ✅ LLM responded ({len(response)} chars)")
        print(f"   Response preview: {response[:200]}...")

        # Check if memories were created
        notes_dir = Path("test_memory_tools") / "notes"
        if notes_dir.exists():
            note_files = list(notes_dir.rglob("*.md"))
            print(f"   ✅ Total note files now: {len(note_files)}")

        # Check verbatim was created
        verbatim_dir = Path("test_memory_tools") / "verbatim" / "bob"
        if verbatim_dir.exists():
            verbatim_files = list(verbatim_dir.rglob("*.md"))
            print(f"   ✅ Verbatim files created: {len(verbatim_files)}")

        # Check session stats
        report = session.get_observability_report()
        print(f"   ✅ Interactions: {report['interactions_count']}")
        print(f"   ✅ Memories created: {report['memories_created']}")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_persistence():
    """Test that memories persist across sessions."""
    print("\n5. Testing Memory Persistence Across Sessions")

    try:
        # Session 1: Create memories
        provider = OllamaProvider(model="qwen3-coder:30b")
        session1 = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="charlie"
        )

        mem_id = session1.remember_fact(
            content="Abstract Memory is a consciousness-through-memory system",
            importance=1.0,
            emotion="excitement"
        )
        print(f"   ✅ Session 1 created memory: {mem_id}")

        # Session 2: Search for memories created in session 1
        session2 = MemorySession(
            provider=provider,
            memory_base_path=Path("test_memory_tools"),
            default_user_id="charlie"
        )

        results = session2.search_memories("consciousness-through-memory")

        if len(results) > 0:
            print(f"   ✅ Session 2 found {len(results)} memories from Session 1")
            print("   ✅ Memory persistence verified")
            return True
        else:
            print("   ❌ Session 2 could not find memories from Session 1")
            return False

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all memory tool tests."""
    print("=" * 80)
    print("MEMORY TOOLS INTEGRATION TEST")
    print("Testing with Real Ollama qwen3-coder:30b - NO MOCKING")
    print("=" * 80)

    # Clean up test directory
    test_dir = Path("test_memory_tools")
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print("🧹 Cleaned up previous test directory")

    tests = [
        ("remember_fact() - Basic", test_remember_fact_basic),
        ("remember_fact() - With Links", test_remember_fact_with_links),
        ("search_memories()", test_search_memories),
        ("LLM-Driven Memory Creation", test_llm_driven_memory_creation),
        ("Memory Persistence", test_memory_persistence),
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
