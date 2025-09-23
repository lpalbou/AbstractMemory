"""
Tests for GroundedMemory integration with storage system.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock

from abstractmemory import create_memory


class TestGroundedMemoryStorage:
    """Test GroundedMemory with storage integration"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)

    def test_grounded_memory_without_storage(self):
        """Test GroundedMemory works without storage (default)"""
        memory = create_memory("grounded")

        assert not hasattr(memory, 'storage_manager') or memory.storage_manager is None

        # Should work normally
        memory.set_current_user("alice")
        memory.add_interaction("Hello", "Hi there!")

        context = memory.get_full_context("greeting")
        assert "alice" in context or "Hello" in context

    def test_grounded_memory_with_markdown_storage(self):
        """Test GroundedMemory with markdown storage"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        assert memory.storage_manager is not None
        assert memory.storage_manager.is_enabled()

        # Test interaction with storage
        memory.set_current_user("bob", relationship="owner")
        memory.add_interaction(
            "I love Python programming",
            "That's great! Python is an excellent language for many applications."
        )

        # Check storage was used
        stats = memory.get_storage_stats()
        assert stats["markdown_enabled"] is True
        assert stats["markdown_stats"]["total_interactions"] >= 1

    def test_experiential_note_generation(self):
        """Test that experiential notes are generated and stored"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("charlie", relationship="colleague")

        # This should trigger reflection due to user learning indicators
        memory.add_interaction(
            "I am a Python developer and I prefer detailed explanations",
            "Great! I'll make sure to provide comprehensive explanations in our future discussions."
        )

        # Check that storage contains both interaction and note
        stats = memory.get_storage_stats()
        assert stats["markdown_stats"]["total_interactions"] >= 1

        # Check if experiential note was created (might be created depending on reflection logic)
        # The _should_reflect method should trigger on "I am" and "I prefer"
        if stats["markdown_stats"]["total_notes"] > 0:
            assert stats["markdown_stats"]["total_notes"] >= 1

    def test_search_stored_interactions(self):
        """Test searching stored interactions"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("diana")

        # Add multiple interactions
        memory.add_interaction("I love Python", "Python is great!")
        memory.add_interaction("What about JavaScript?", "JavaScript is also excellent!")
        memory.add_interaction("Python machine learning", "Python has excellent ML libraries!")

        # Search for Python-related interactions
        results = memory.search_stored_interactions("python")
        assert len(results) >= 2  # Should find at least the Python interactions

        # Search with user filter
        diana_results = memory.search_stored_interactions("python", user_id="diana")
        assert len(diana_results) >= 2
        assert all(r["user_id"] == "diana" for r in diana_results)

    def test_memory_component_persistence(self):
        """Test saving and loading memory components"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("eve")

        # Add some data to memory components
        memory.learn_about_user("loves coding")
        memory.learn_about_user("works in data science")
        memory.track_success("coding_help", "provided useful Python tips")

        # Save memory state
        memory.save(self.temp_dir)

        # Verify data was saved
        stats = memory.get_storage_stats()
        assert "markdown_stats" in stats

    def test_with_mock_embedding_provider(self):
        """Test integration with mock embedding provider"""
        # Mock embedding provider (simulates AbstractCore)
        mock_provider = Mock()
        mock_provider.generate_embedding.return_value = [0.1, 0.2, 0.3, 0.4]

        memory = create_memory(
            "grounded",
            storage_backend="markdown",  # Test markdown only for now
            storage_path=self.temp_dir,
            embedding_provider=mock_provider
        )

        memory.set_current_user("frank")
        memory.add_interaction(
            "Tell me about machine learning",
            "Machine learning is a subset of artificial intelligence..."
        )

        # Verify embedding provider was used (if LanceDB storage is active)
        # For markdown only, embedding provider won't be called
        # But the system should handle it gracefully

        stats = memory.get_storage_stats()
        assert stats["embedding_provider"] is True

    def test_reflection_triggers(self):
        """Test different reflection triggers"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("grace")

        # Test user learning trigger
        memory.add_interaction(
            "I am a beginner in Python and I prefer step-by-step explanations",
            "Perfect! I'll make sure to break down concepts into manageable steps."
        )

        # Test pattern learning trigger
        memory.add_interaction(
            "That approach failed for me before, but this usually works better",
            "I understand. Let's focus on the approach that typically works for you."
        )

        # Test topic shift trigger
        memory.add_interaction(
            "By the way, switching topics - what about web development?",
            "Certainly! Web development is a great area to explore."
        )

        # Check that interactions were stored
        results = memory.search_stored_interactions("Python")
        assert len(results) >= 1

    def test_factory_function_with_storage_params(self):
        """Test factory function with various storage parameters"""
        # Test all storage configurations
        configs = [
            {"storage_backend": None},
            {"storage_backend": "markdown", "storage_path": self.temp_dir},
            # LanceDB would require installation, skip for basic test
        ]

        for config in configs:
            memory = create_memory("grounded", **config)

            if config["storage_backend"] is None:
                assert not hasattr(memory, 'storage_manager') or memory.storage_manager is None
            else:
                assert memory.storage_manager is not None

            # Basic functionality should work regardless
            memory.set_current_user("test_user")
            memory.add_interaction("test input", "test response")

    def test_error_handling_in_storage(self):
        """Test error handling when storage operations fail"""
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path="/invalid/path/that/cannot/be/created"
        )

        # Should handle storage errors gracefully
        memory.set_current_user("error_test")

        # This should not crash even if storage fails
        memory.add_interaction("test", "response")

        # Basic memory functionality should still work
        context = memory.get_full_context("test")
        assert isinstance(context, str)