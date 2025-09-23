"""
Tests for MarkdownStorage backend.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from abstractmemory.storage.markdown_storage import MarkdownStorage


class TestMarkdownStorage:
    """Test MarkdownStorage implementation"""

    def setup_method(self):
        """Setup test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = MarkdownStorage(self.temp_dir)

    def teardown_method(self):
        """Cleanup temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test storage initialization"""
        storage_path = Path(self.temp_dir)

        # Check directory structure was created
        assert (storage_path / "verbatim").exists()
        assert (storage_path / "experiential").exists()
        assert (storage_path / "links").exists()
        assert (storage_path / "core").exists()
        assert (storage_path / "semantic").exists()
        assert (storage_path / "index.json").exists()

    def test_save_interaction(self):
        """Test saving verbatim interaction"""
        now = datetime.now()

        interaction_id = self.storage.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="Hello, I love Python programming!",
            agent_response="That's great! Python is an excellent language for many applications.",
            topic="python",
            metadata={"session": "test_session"}
        )

        assert interaction_id.startswith("int_")
        assert interaction_id in self.storage.index["interactions"]

        # Check file was created
        interaction_data = self.storage.index["interactions"][interaction_id]
        file_path = Path(self.temp_dir) / interaction_data["file_path"]
        assert file_path.exists()

        # Check file content
        with open(file_path, 'r') as f:
            content = f.read()
            assert "Hello, I love Python programming!" in content
            assert "That's great! Python is an excellent language" in content
            assert "python" in content
            assert "alice" in content

    def test_save_experiential_note(self):
        """Test saving AI experiential note"""
        now = datetime.now()

        # First create an interaction
        interaction_id = self.storage.save_interaction(
            user_id="bob",
            timestamp=now,
            user_input="I need help with coding",
            agent_response="I'd be happy to help you with coding!",
            topic="assistance"
        )

        # Create experiential note
        note_id = self.storage.save_experiential_note(
            timestamp=now,
            reflection="User is seeking coding assistance. This is a learning opportunity to understand their skill level and provide appropriate guidance.",
            interaction_id=interaction_id,
            note_type="learning_reflection",
            metadata={"trigger": "assistance_request"}
        )

        assert note_id.startswith("note_")
        assert note_id in self.storage.index["experiential_notes"]

        # Check file was created
        note_data = self.storage.index["experiential_notes"][note_id]
        file_path = Path(self.temp_dir) / note_data["file_path"]
        assert file_path.exists()

        # Check file content
        with open(file_path, 'r') as f:
            content = f.read()
            assert "learning opportunity" in content
            assert "assistance_request" in content
            assert interaction_id in content

    def test_link_interaction_to_note(self):
        """Test creating bidirectional links"""
        now = datetime.now()

        # Create interaction and note
        interaction_id = self.storage.save_interaction(
            user_id="charlie",
            timestamp=now,
            user_input="What is machine learning?",
            agent_response="Machine learning is a subset of artificial intelligence...",
            topic="learning"
        )

        note_id = self.storage.save_experiential_note(
            timestamp=now,
            reflection="User is learning about ML concepts. Good opportunity to gauge their technical background.",
            interaction_id=interaction_id,
            note_type="learning_assessment"
        )

        # Create link
        self.storage.link_interaction_to_note(interaction_id, note_id)

        # Check link was created in index
        link_key = f"{interaction_id}_{note_id}"
        assert link_key in self.storage.index["links"]

        # Check interaction has linked note
        interaction_data = self.storage.index["interactions"][interaction_id]
        assert note_id in interaction_data["linked_notes"]

    def test_search_interactions(self):
        """Test searching interactions"""
        now = datetime.now()

        # Create multiple interactions
        id1 = self.storage.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="I love Python",
            agent_response="Python is great!",
            topic="python"
        )

        id2 = self.storage.save_interaction(
            user_id="bob",
            timestamp=now,
            user_input="What about JavaScript?",
            agent_response="JavaScript is also excellent!",
            topic="javascript"
        )

        id3 = self.storage.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="Python machine learning",
            agent_response="Python has great ML libraries!",
            topic="python"
        )

        # Search by topic
        python_results = self.storage.search_interactions("python")
        assert len(python_results) == 2
        assert any(r["id"] == id1 for r in python_results)
        assert any(r["id"] == id3 for r in python_results)

        # Search by user
        alice_results = self.storage.search_interactions("python", user_id="alice")
        assert len(alice_results) == 2
        assert all(r["user_id"] == "alice" for r in alice_results)

        # Search by content
        ml_results = self.storage.search_interactions("machine learning")
        assert len(ml_results) == 1
        assert ml_results[0]["id"] == id3

    def test_save_memory_component(self):
        """Test saving memory component snapshots"""
        test_component = {
            "type": "test_component",
            "data": ["item1", "item2", "item3"],
            "metadata": {"version": 1}
        }

        self.storage.save_memory_component("test_component", test_component)

        # Check file was created
        component_file = Path(self.temp_dir) / "core" / "test_component_latest.json"
        assert component_file.exists()

        # Check content
        loaded_component = self.storage.load_memory_component("test_component")
        assert loaded_component == test_component

    def test_get_stats(self):
        """Test getting storage statistics"""
        now = datetime.now()

        # Add some data
        self.storage.save_interaction(
            user_id="alice",
            timestamp=now,
            user_input="Test input",
            agent_response="Test response",
            topic="test"
        )

        note_id = self.storage.save_experiential_note(
            timestamp=now,
            reflection="Test reflection",
            interaction_id="test_id",
            note_type="test"
        )

        stats = self.storage.get_stats()

        assert stats["total_interactions"] == 1
        assert stats["total_notes"] == 1
        assert stats["unique_users"] == 1
        assert stats["unique_topics"] == 1
        assert "base_path" in stats
        assert "storage_size_mb" in stats

    def test_topic_extraction(self):
        """Test automatic topic extraction"""
        now = datetime.now()

        # Test Python detection
        id1 = self.storage.save_interaction(
            user_id="test",
            timestamp=now,
            user_input="I want to learn Python programming",
            agent_response="Python is great for beginners!",
            topic=""  # Let it auto-extract
        )

        interaction_data = self.storage.index["interactions"][id1]
        assert interaction_data["topic"] == "python"

        # Test fallback to first words
        id2 = self.storage.save_interaction(
            user_id="test",
            timestamp=now,
            user_input="Random unusual topic here",
            agent_response="Interesting question!",
            topic=""
        )

        interaction_data = self.storage.index["interactions"][id2]
        assert interaction_data["topic"] == "random_unusual_topic"  # Uses first 3 words