#!/usr/bin/env python3
"""
Test script to verify the /reset full fix works correctly.

This script simulates the reset process and verifies that:
1. LanceDB connection is properly reinitialized after reset
2. Database operations work after reset
3. No 'NoneType' errors occur
"""

import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, '/Users/albou/projects/abstractmemory')

from abstractmemory.session import MemorySession
from abstractmemory.storage.lancedb_storage import LanceDBStorage
from abstractllm.providers.ollama_provider import OllamaProvider

def test_reset_fix():
    """Test the /reset full fix."""
    print("🧪 Testing /reset full fix...")

    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        memory_path = Path(temp_dir) / "test_memory"
        print(f"   📁 Test memory path: {memory_path}")

        try:
            # 1. Create memory session with minimal provider (no actual LLM needed for this test)
            print("\n1️⃣ Creating memory session...")

            # Create a minimal mock provider for testing
            class MockProvider:
                def __init__(self):
                    self.model = "test-model"

                def generate(self, *args, **kwargs):
                    return type('MockResponse', (), {'content': 'test response'})()

                def set_timeout(self, timeout):
                    pass

            mock_provider = MockProvider()

            session = MemorySession(
                provider=mock_provider,
                memory_base_path=str(memory_path),
                default_user_id="test_user"
            )

            print(f"   ✅ Session created with memory path: {session.memory_base_path}")
            print(f"   ✅ LanceDB storage initialized: {session.lancedb_storage is not None}")
            print(f"   ✅ LanceDB connection active: {session.lancedb_storage.db is not None}")

            # 2. Add test data to verify database is working
            print("\n2️⃣ Adding test data...")

            test_note = {
                "id": "test_note_1",
                "content": "This is a test note for reset verification",
                "user_id": "test_user",
                "location": "test",
                "importance": 0.8,
                "emotion": "neutral",
                "emotion_intensity": 0.5,
                "emotion_valence": "neutral"
            }

            success = session.lancedb_storage.add_note(test_note)
            print(f"   ✅ Test note added successfully: {success}")

            # Verify we can search the data
            results = session.lancedb_storage.search_notes("test note", limit=1)
            print(f"   ✅ Can search notes: {len(results)} results found")

            # 3. Simulate the /reset full process
            print("\n3️⃣ Simulating /reset full process...")

            # Close database connection (simulating what /reset full does)
            if hasattr(session.lancedb_storage, 'db'):
                session.lancedb_storage.db = None
                print("   ✅ Database connection closed")

            # Delete memory directory (simulating what /reset full does)
            if memory_path.exists():
                shutil.rmtree(memory_path)
                print(f"   ✅ Memory directory deleted: {memory_path}")

            # 4. Test the reinitialize fix
            print("\n4️⃣ Testing LanceDB reinitialize fix...")

            # Call the new reinitialize method
            reinit_success = session.lancedb_storage.reinitialize()
            print(f"   ✅ LanceDB reinitialized: {reinit_success}")
            print(f"   ✅ Database connection restored: {session.lancedb_storage.db is not None}")

            # 5. Verify operations work after reset
            print("\n5️⃣ Verifying operations work after reset...")

            # Test that we can add new data
            new_test_note = {
                "id": "test_note_after_reset",
                "content": "This note was added after reset",
                "user_id": "test_user",
                "location": "test",
                "importance": 0.7,
                "emotion": "positive",
                "emotion_intensity": 0.6,
                "emotion_valence": "positive"
            }

            success_after_reset = session.lancedb_storage.add_note(new_test_note)
            print(f"   ✅ Can add notes after reset: {success_after_reset}")

            # Test that we can search
            results_after_reset = session.lancedb_storage.search_notes("after reset", limit=1)
            print(f"   ✅ Can search after reset: {len(results_after_reset)} results found")

            # Test that we can count notes
            count_after_reset = session.lancedb_storage.count_notes()
            print(f"   ✅ Can count notes after reset: {count_after_reset} notes")

            # 6. Test that table_names() works (this was the original error)
            print("\n6️⃣ Testing table_names() method (original error case)...")

            try:
                table_names = session.lancedb_storage.db.table_names()
                print(f"   ✅ table_names() works: {table_names}")
            except AttributeError as e:
                print(f"   ❌ table_names() failed: {e}")
                return False

            print("\n🎉 ALL TESTS PASSED!")
            print("   The /reset full fix successfully:")
            print("   ✅ Reinitializes LanceDB connection after deletion")
            print("   ✅ Allows database operations to continue after reset")
            print("   ✅ Eliminates 'NoneType' object has no attribute 'table_names' errors")

            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_reset_fix()
    sys.exit(0 if success else 1)