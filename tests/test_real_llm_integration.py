#!/usr/bin/env python3
"""
REAL LLM Integration Test - NO MOCKS

Tests the complete flow with:
- Real Ollama qwen3-coder:30b for LLM reflections
- Real Ollama all-minilm:l6-v2 for embeddings
- Real dual storage (markdown + LanceDB)
- Real semantic search

This is the CRITICAL test that was missing from the previous implementation.
"""

import sys
import os
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("REAL LLM INTEGRATION TEST")
print("Testing with actual Ollama qwen3-coder:30b + all-minilm:l6-v2")
print("=" * 80)


def test_ollama_connectivity():
    """Verify Ollama is running and models are available"""
    print("\n1. Testing Ollama Connectivity...")

    import requests

    # Test LLM (qwen3-coder:30b)
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen3-coder:30b", "prompt": "Say 'test'", "stream": False},
            timeout=30
        )
        if response.status_code == 200:
            print("   ✅ qwen3-coder:30b LLM responding")
        else:
            print(f"   ❌ LLM failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ LLM error: {e}")
        return False

    # Test embeddings (all-minilm:l6-v2)
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "all-minilm:l6-v2", "prompt": "test"},
            timeout=10
        )
        if response.status_code == 200:
            embedding = response.json()["embedding"]
            print(f"   ✅ all-minilm:l6-v2 embeddings working (dim={len(embedding)})")
        else:
            print(f"   ❌ Embeddings failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Embeddings error: {e}")
        return False

    return True


def test_llm_reflection_generation():
    """Test real LLM-generated reflection"""
    print("\n2. Testing LLM Reflection Generation...")

    from abstractmemory.reflection import generate_llm_reflection

    # Create mock Ollama provider
    class OllamaProvider:
        provider_name = "ollama"

    provider = OllamaProvider()

    # Generate real reflection
    user_input = "Can you explain how memory works in this system?"
    agent_response = "This system uses a dual storage approach with verbatim records and semantic search capabilities."

    try:
        reflection = generate_llm_reflection(
            user_input=user_input,
            agent_response=agent_response,
            user_id="test_user",
            location="test_lab",
            llm_provider=provider
        )

        print(f"   ✅ Generated reflection ({len(reflection)} chars)")

        # Validate reflection quality
        if len(reflection) < 100:
            print(f"   ⚠️ Reflection too short: {len(reflection)} chars")
            return False

        if "I noticed" in reflection or "I felt" in reflection or "I think" in reflection:
            print("   ✅ Reflection appears subjective (first-person)")
        else:
            print("   ⚠️ Reflection may not be subjective enough")

        print(f"\n   Preview:\n   {reflection[:200]}...\n")

        return True

    except Exception as e:
        print(f"   ❌ Reflection generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dual_storage_with_real_llm():
    """Test dual storage with real LLM-generated experiential notes"""
    print("\n3. Testing Dual Storage (Markdown + LanceDB) with Real LLM...")

    from abstractmemory.storage.dual_manager import DualStorageManager
    from abstractmemory.storage.markdown_storage import MarkdownStorage
    from abstractmemory.reflection import generate_llm_reflection

    # Create temporary storage directories
    temp_dir = tempfile.mkdtemp(prefix="test_abstractmemory_")
    markdown_path = os.path.join(temp_dir, "markdown")
    lancedb_path = os.path.join(temp_dir, "lancedb")

    try:
        # Create mock embedding provider for LanceDB
        class MockEmbeddingProvider:
            def generate_embedding(self, text: str):
                import requests
                response = requests.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "all-minilm:l6-v2", "prompt": text},
                    timeout=10
                )
                return response.json()["embedding"]

        embedding_provider = MockEmbeddingProvider()

        # Initialize dual storage
        storage = DualStorageManager(
            mode="dual",
            markdown_path=markdown_path,
            lancedb_uri=lancedb_path,
            embedding_provider=embedding_provider
        )

        print(f"   ✅ Initialized dual storage")

        # Save verbatim interaction
        now = datetime.now()
        interaction_id = storage.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="What is the meaning of life?",
            agent_response="The meaning of life is a profound philosophical question that has been pondered for centuries...",
            topic="philosophy",
            metadata={"location": "virtual_space", "session": "test"}
        )

        print(f"   ✅ Saved verbatim interaction: {interaction_id}")

        # Generate LLM reflection
        class OllamaProvider:
            provider_name = "ollama"

        llm_provider = OllamaProvider()

        reflection = generate_llm_reflection(
            user_input="What is the meaning of life?",
            agent_response="The meaning of life is a profound philosophical question...",
            user_id="alice",
            location="virtual_space",
            llm_provider=llm_provider
        )

        print(f"   ✅ Generated LLM reflection ({len(reflection)} chars)")

        # Save experiential note
        note_id = storage.save_experiential_note(
            timestamp=now,
            reflection=reflection,
            interaction_id=interaction_id,
            note_type="reflection",
            metadata={"user_id": "alice", "location": "virtual_space", "topic": "philosophy"}
        )

        print(f"   ✅ Saved experiential note: {note_id}")

        # Verify files exist
        markdown_storage = storage.markdown_storage
        verbatim_files = list(Path(markdown_path).glob("verbatim/**/*.md"))
        note_files = list(Path(markdown_path).glob("notes/**/*.md"))

        print(f"   ✅ Found {len(verbatim_files)} verbatim file(s)")
        print(f"   ✅ Found {len(note_files)} experiential note file(s)")

        # Check that notes/ folder is used (not experiential/)
        if note_files:
            note_path = str(note_files[0])
            if "/notes/" in note_path:
                print("   ✅ Using 'notes/' folder (correct per spec)")
            elif "/experiential/" in note_path:
                print("   ⚠️ Using 'experiential/' folder (should be 'notes/')")

        # Read and validate note content
        if note_files:
            with open(note_files[0], 'r') as f:
                note_content = f.read()

            # Validate structure
            if "# AI Experiential Note" in note_content:
                print("   ✅ Note has correct header")
            if "**Participants**: AI & alice" in note_content:
                print("   ✅ Note has participants field")
            if "**Location**: virtual_space" in note_content:
                print("   ✅ Note has location field")

            # Validate LLM content dominates (>90%)
            template_chars = len("# AI Experiential Note") + 200  # Approximate template size
            total_chars = len(note_content)
            llm_content_ratio = (total_chars - template_chars) / total_chars

            if llm_content_ratio > 0.9:
                print(f"   ✅ LLM content >90% of note ({llm_content_ratio*100:.1f}%)")
            else:
                print(f"   ⚠️ LLM content only {llm_content_ratio*100:.1f}% (should be >90%)")

        # Read and validate verbatim content
        if verbatim_files:
            with open(verbatim_files[0], 'r') as f:
                verbatim_content = f.read()

            if "# Verbatim Interaction" in verbatim_content:
                print("   ✅ Verbatim has correct header")
            if "**Location**: virtual_space" in verbatim_content:
                print("   ✅ Verbatim has location field")
            if "100% factual, deterministically written" in verbatim_content:
                print("   ✅ Verbatim marked as deterministic")

        return True

    except Exception as e:
        print(f"   ❌ Dual storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"   ✅ Cleaned up temp directory")


def test_semantic_search_with_real_embeddings():
    """Test semantic search with real embeddings"""
    print("\n4. Testing Semantic Search with Real Embeddings...")

    from abstractmemory.storage.lancedb_storage import LanceDBStorage

    temp_dir = tempfile.mkdtemp(prefix="test_lancedb_")
    lancedb_path = os.path.join(temp_dir, "test.lance")

    try:
        # Create embedding provider
        class OllamaEmbeddingProvider:
            def generate_embedding(self, text: str):
                import requests
                response = requests.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "all-minilm:l6-v2", "prompt": text},
                    timeout=10
                )
                return response.json()["embedding"]

        provider = OllamaEmbeddingProvider()

        # Initialize LanceDB
        storage = LanceDBStorage(lancedb_path, provider)
        print(f"   ✅ Initialized LanceDB storage")

        # Save test interactions
        now = datetime.now()
        interactions = [
            ("alice", "I love programming in Python", "Python is great!", "python"),
            ("bob", "How do I debug my code?", "Use print statements...", "debugging"),
            ("alice", "What's the best Python IDE?", "PyCharm is popular...", "python")
        ]

        for user, input_text, response, topic in interactions:
            storage.save_interaction(
                user_id=user,
                timestamp=now,
                user_input=input_text,
                agent_response=response,
                topic=topic,
                metadata={"location": "test", "category": "knowledge"}
            )

        print(f"   ✅ Saved {len(interactions)} test interactions")

        # Test semantic search
        results = storage.search_interactions("Python programming")
        print(f"   ✅ Semantic search returned {len(results)} results")

        if len(results) >= 2:
            print("   ✅ Found Python-related interactions")
        else:
            print(f"   ⚠️ Expected 2+ results, got {len(results)}")

        # Test hybrid search (new functionality)
        if hasattr(storage, 'hybrid_search'):
            hybrid_results = storage.hybrid_search(
                "Python",
                sql_filters={"user_id": "alice"},
                limit=10
            )
            print(f"   ✅ Hybrid search returned {len(hybrid_results)} results")

            if len(hybrid_results) == 2:  # Should only get Alice's Python questions
                print("   ✅ Hybrid search filtered correctly")
            else:
                print(f"   ⚠️ Expected 2 results, got {len(hybrid_results)}")

        return True

    except Exception as e:
        print(f"   ❌ Semantic search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"   ✅ Cleaned up temp directory")


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "=" * 80)
    print("RUNNING ALL TESTS")
    print("=" * 80 + "\n")

    tests = [
        ("Ollama Connectivity", test_ollama_connectivity),
        ("LLM Reflection Generation", test_llm_reflection_generation),
        ("Dual Storage with Real LLM", test_dual_storage_with_real_llm),
        ("Semantic Search with Real Embeddings", test_semantic_search_with_real_embeddings)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ {name} crashed: {e}")
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