"""
Diagnostic test to identify the exact issue with embeddings integration
"""

import sys
import tempfile
import shutil

# Add AbstractCore path
sys.path.insert(0, '/Users/albou/projects/abstractllm_core')

from abstractmemory.storage.lancedb_storage import LanceDBStorage
from abstractmemory.embeddings import create_embedding_adapter

try:
    from abstractllm.embeddings import EmbeddingManager
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False


def test_diagnostic():
    if not ABSTRACTCORE_AVAILABLE:
        print("❌ AbstractCore not available")
        return

    temp_dir = tempfile.mkdtemp()

    try:
        print("🔍 DIAGNOSTIC TEST")
        print("=" * 30)

        # 1. Test EmbeddingManager directly
        print("1. Testing EmbeddingManager directly...")
        em = EmbeddingManager()
        embedding = em.embed("test text")
        print(f"   ✅ Direct embed() works: {len(embedding)} dimensions")

        # 2. Test adapter
        print("2. Testing EmbeddingAdapter...")
        adapter = create_embedding_adapter(em)
        adapter_embedding = adapter.generate_embedding("test text")
        print(f"   ✅ Adapter works: {len(adapter_embedding)} dimensions")

        # 3. Test LanceDB storage creation
        print("3. Testing LanceDB storage...")
        storage = LanceDBStorage(f"{temp_dir}/diag.db", embedding_provider=em)
        print(f"   ✅ LanceDB storage created")
        print(f"   ✅ Adapter type: {storage.embedding_adapter.provider_type}")

        # 4. Test direct embedding generation in storage
        print("4. Testing storage embedding generation...")
        try:
            storage_embedding = storage._generate_embedding("test text")
            print(f"   ✅ Storage embedding works: {len(storage_embedding)} dimensions")
        except Exception as e:
            print(f"   ❌ Storage embedding failed: {e}")
            import traceback
            traceback.print_exc()

        # 5. Test interaction save
        print("5. Testing interaction save...")
        try:
            from datetime import datetime
            int_id = storage.save_interaction(
                "test_user",
                datetime.now(),
                "test input",
                "test response",
                "test",
                {}
            )
            print(f"   ✅ Interaction saved: {int_id}")
        except Exception as e:
            print(f"   ❌ Interaction save failed: {e}")
            import traceback
            traceback.print_exc()

        # 6. Test search
        print("6. Testing search...")
        try:
            results = storage.search_interactions("test")
            print(f"   ✅ Search works: {len(results)} results")
        except Exception as e:
            print(f"   ❌ Search failed: {e}")
            import traceback
            traceback.print_exc()

    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_diagnostic()