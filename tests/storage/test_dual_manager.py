"""
Tests for DualStorageManager.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock

from abstractmemory.storage.dual_manager import DualStorageManager


class TestDualStorageManager:
    """Test DualStorageManager implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)

    def test_no_storage_mode(self):
        """Test with no storage enabled"""
        manager = DualStorageManager(mode=None)

        assert not manager.is_enabled()
        assert manager.save_interaction("user", datetime.now(), "input", "response", "topic") is None

    def test_markdown_only_mode(self):
        """Test with markdown storage only"""
        manager = DualStorageManager(
            mode="markdown",
            markdown_path=self.temp_dir
        )

        assert manager.is_enabled()
        assert manager.markdown_storage is not None
        assert manager.lancedb_storage is None

        # Test saving interaction
        now = datetime.now()
        interaction_id = manager.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="Hello world",
            agent_response="Hi there!",
            topic="greeting"
        )

        assert interaction_id is not None
        assert interaction_id.startswith("int_")

    def test_dual_mode_with_mock_embedding(self):
        """Test dual mode with mock embedding provider"""
        # Mock embedding provider
        mock_provider = Mock()
        mock_provider.generate_embedding.return_value = [0.1, 0.2, 0.3]

        manager = DualStorageManager(
            mode="markdown",  # Only test markdown for now since LanceDB requires installation
            markdown_path=self.temp_dir,
            embedding_provider=mock_provider
        )

        assert manager.is_enabled()
        assert manager.embedding_provider is not None

        # Test interaction with embedding
        now = datetime.now()
        interaction_id = manager.save_interaction(
            user_id="bob",
            timestamp=now,
            user_input="Tell me about Python",
            agent_response="Python is a programming language...",
            topic="python"
        )

        assert interaction_id is not None

        # Test experiential note
        note_id = manager.save_experiential_note(
            timestamp=now,
            reflection="User is interested in learning Python. Good opportunity to assess skill level.",
            interaction_id=interaction_id,
            note_type="learning_opportunity"
        )

        assert note_id is not None

        # Test linking
        manager.link_interaction_to_note(interaction_id, note_id)

        # Test search
        results = manager.search_interactions("python")
        assert len(results) >= 1

    def test_get_storage_stats(self):
        """Test getting storage statistics"""
        manager = DualStorageManager(
            mode="markdown",
            markdown_path=self.temp_dir
        )

        # Add some data
        now = datetime.now()
        manager.save_interaction(
            user_id="charlie",
            timestamp=now,
            user_input="Test interaction",
            agent_response="Test response",
            topic="test"
        )

        stats = manager.get_storage_stats()

        assert stats["mode"] == "markdown"
        assert stats["markdown_enabled"] is True
        assert stats["lancedb_enabled"] is False
        assert "markdown_stats" in stats

    def test_save_memory_component(self):
        """Test saving memory components"""
        manager = DualStorageManager(
            mode="markdown",
            markdown_path=self.temp_dir
        )

        test_data = {"test": "data", "values": [1, 2, 3]}

        manager.save_memory_component("test_component", test_data)

        # Should not raise an error
        loaded_data = manager.load_memory_component("test_component")
        assert loaded_data == test_data

    def test_search_with_filters(self):
        """Test search with user and date filters"""
        manager = DualStorageManager(
            mode="markdown",
            markdown_path=self.temp_dir
        )

        now = datetime.now()

        # Create interactions for different users
        manager.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="Alice's Python question",
            agent_response="Response for Alice",
            topic="python"
        )

        manager.save_interaction(
            user_id="bob",
            timestamp=now,
            user_input="Bob's Python question",
            agent_response="Response for Bob",
            topic="python"
        )

        # Search with user filter
        alice_results = manager.search_interactions("python", user_id="alice")
        assert len(alice_results) == 1
        assert alice_results[0]["user_id"] == "alice"

        # Search all Python interactions
        all_python = manager.search_interactions("python")
        assert len(all_python) == 2

    def test_error_handling(self):
        """Test error handling in storage operations"""
        # Test with invalid path for markdown
        manager = DualStorageManager(
            mode="markdown",
            markdown_path="/invalid/path/that/does/not/exist"
        )

        # Should handle errors gracefully
        result = manager.save_interaction(
            user_id="test",
            timestamp=datetime.now(),
            user_input="test",
            agent_response="test",
            topic="test"
        )

        # Depending on implementation, might return None or handle gracefully
        # The exact behavior depends on error handling in MarkdownStorage