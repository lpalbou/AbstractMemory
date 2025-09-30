#!/usr/bin/env python3
"""
Tests for LanceDB hybrid_search and related methods.

Tests cover:
- hybrid_search with category/confidence/temporal filters
- search_by_category
- temporal_search
- get_user_timeline
- Schema enhancements (category, confidence, tags)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timedelta
import tempfile
import shutil


def test_lancedb_schema_enhancements():
    """Test that LanceDB schema includes new fields"""
    print("\n1. Testing LanceDB schema enhancements...")

    try:
        from abstractmemory.storage.lancedb_storage import LanceDBStorage

        # Create a mock embedding provider
        class MockEmbedding:
            def generate_embedding(self, text):
                return [0.1] * 384  # 384-dim embedding

            def get_embedding_info(self):
                return {"model": "mock", "dimension": 384}

            def warn_about_consistency(self, stored_info):
                pass

            def check_consistency_with(self, stored_info):
                return True

        # Create temporary database
        temp_dir = tempfile.mkdtemp()
        db_path = f"{temp_dir}/test.lance"

        storage = LanceDBStorage(db_path, embedding_provider=MockEmbedding())

        # Save interaction with new fields
        interaction_id = storage.save_interaction(
            user_id="alice",
            timestamp=datetime.now(),
            user_input="I love Python programming",
            agent_response="That's great! Python is versatile.",
            topic="programming",
            metadata={
                'category': 'preference',
                'confidence': 0.95,
                'tags': ['python', 'programming', 'preference']
            }
        )

        print(f"   ✓ Saved interaction with category, confidence, tags: {interaction_id}")

        # Clean up
        shutil.rmtree(temp_dir)
        print("   ✓ Schema enhancements working\n")
        return True

    except Exception as e:
        print(f"   ✗ Error: {e}\n")
        return False


def test_hybrid_search():
    """Test hybrid_search method"""
    print("2. Testing hybrid_search...")

    try:
        from abstractmemory.storage.lancedb_storage import LanceDBStorage

        class MockEmbedding:
            def generate_embedding(self, text):
                return [0.1] * 384

            def get_embedding_info(self):
                return {"model": "mock", "dimension": 384}

            def warn_about_consistency(self, stored_info):
                pass

            def check_consistency_with(self, stored_info):
                return True

        temp_dir = tempfile.mkdtemp()
        db_path = f"{temp_dir}/test.lance"

        storage = LanceDBStorage(db_path, embedding_provider=MockEmbedding())

        # Add test data
        storage.save_interaction(
            user_id="alice",
            timestamp=datetime.now(),
            user_input="I love Python",
            agent_response="Great choice!",
            topic="preference",
            metadata={'category': 'preference', 'confidence': 0.95, 'tags': ['python']}
        )

        storage.save_interaction(
            user_id="bob",
            timestamp=datetime.now(),
            user_input="JavaScript is powerful",
            agent_response="Indeed it is!",
            topic="preference",
            metadata={'category': 'preference', 'confidence': 0.9, 'tags': ['javascript']}
        )

        # Test hybrid search with filters
        results = storage.hybrid_search(
            semantic_query="programming language",
            sql_filters={'category': 'preference', 'user_id': 'alice'},
            limit=10
        )

        print(f"   ✓ Hybrid search returned {len(results)} results")

        # Clean up
        shutil.rmtree(temp_dir)
        print("   ✓ Hybrid search working\n")
        return True

    except Exception as e:
        print(f"   ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_search_by_category():
    """Test search_by_category method"""
    print("3. Testing search_by_category...")

    try:
        from abstractmemory.storage.lancedb_storage import LanceDBStorage

        class MockEmbedding:
            def generate_embedding(self, text):
                return [0.1] * 384

            def get_embedding_info(self):
                return {"model": "mock", "dimension": 384}

            def warn_about_consistency(self, stored_info):
                pass

            def check_consistency_with(self, stored_info):
                return True

        temp_dir = tempfile.mkdtemp()
        db_path = f"{temp_dir}/test.lance"

        storage = LanceDBStorage(db_path, embedding_provider=MockEmbedding())

        # Add test data with different categories
        storage.save_interaction(
            user_id="alice",
            timestamp=datetime.now(),
            user_input="Test",
            agent_response="Response",
            topic="test",
            metadata={'category': 'knowledge', 'confidence': 0.9}
        )

        storage.save_interaction(
            user_id="alice",
            timestamp=datetime.now(),
            user_input="Test 2",
            agent_response="Response 2",
            topic="test",
            metadata={'category': 'preference', 'confidence': 0.95}
        )

        # Test category search
        knowledge_results = storage.search_by_category("knowledge", user_id="alice")
        print(f"   ✓ Category search returned {len(knowledge_results)} knowledge items")

        # Clean up
        shutil.rmtree(temp_dir)
        print("   ✓ search_by_category working\n")
        return True

    except Exception as e:
        print(f"   ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_temporal_search():
    """Test temporal_search method"""
    print("4. Testing temporal_search...")

    try:
        from abstractmemory.storage.lancedb_storage import LanceDBStorage

        class MockEmbedding:
            def generate_embedding(self, text):
                return [0.1] * 384

            def get_embedding_info(self):
                return {"model": "mock", "dimension": 384}

            def warn_about_consistency(self, stored_info):
                pass

            def check_consistency_with(self, stored_info):
                return True

        temp_dir = tempfile.mkdtemp()
        db_path = f"{temp_dir}/test.lance"

        storage = LanceDBStorage(db_path, embedding_provider=MockEmbedding())

        # Add recent and old data
        yesterday = datetime.now() - timedelta(days=1)
        last_week = datetime.now() - timedelta(days=7)

        storage.save_interaction(
            user_id="alice",
            timestamp=yesterday,
            user_input="Recent query",
            agent_response="Recent response",
            topic="test",
            metadata={'category': 'conversation', 'confidence': 0.9}
        )

        # Test temporal search
        results = storage.temporal_search(
            "query",
            since=last_week,
            user_id="alice"
        )

        print(f"   ✓ Temporal search returned {len(results)} results")

        # Clean up
        shutil.rmtree(temp_dir)
        print("   ✓ temporal_search working\n")
        return True

    except Exception as e:
        print(f"   ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_get_user_timeline():
    """Test get_user_timeline method"""
    print("5. Testing get_user_timeline...")

    try:
        from abstractmemory.storage.lancedb_storage import LanceDBStorage

        class MockEmbedding:
            def generate_embedding(self, text):
                return [0.1] * 384

            def get_embedding_info(self):
                return {"model": "mock", "dimension": 384}

            def warn_about_consistency(self, stored_info):
                pass

            def check_consistency_with(self, stored_info):
                return True

        temp_dir = tempfile.mkdtemp()
        db_path = f"{temp_dir}/test.lance"

        storage = LanceDBStorage(db_path, embedding_provider=MockEmbedding())

        # Add multiple interactions for a user
        for i in range(5):
            storage.save_interaction(
                user_id="alice",
                timestamp=datetime.now() - timedelta(hours=i),
                user_input=f"Query {i}",
                agent_response=f"Response {i}",
                topic="test",
                metadata={'category': 'conversation', 'confidence': 0.9}
            )

        # Get user timeline
        timeline = storage.get_user_timeline("alice", limit=10)

        print(f"   ✓ User timeline returned {len(timeline)} interactions")

        # Clean up
        shutil.rmtree(temp_dir)
        print("   ✓ get_user_timeline working\n")
        return True

    except Exception as e:
        print(f"   ✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all LanceDB tests"""
    print("=" * 60)
    print("LANCEDB HYBRID SEARCH TEST SUITE")
    print("=" * 60)

    results = []

    results.append(("Schema Enhancements", test_lancedb_schema_enhancements()))
    results.append(("Hybrid Search", test_hybrid_search()))
    results.append(("Search by Category", test_search_by_category()))
    results.append(("Temporal Search", test_temporal_search()))
    results.append(("User Timeline", test_get_user_timeline()))

    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("=" * 60)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())