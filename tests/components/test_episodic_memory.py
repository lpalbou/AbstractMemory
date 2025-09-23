"""
Tests for EpisodicMemory - Event archive with temporal organization.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory.components.episodic import EpisodicMemory
from abstractmemory.core.interfaces import MemoryItem
from abstractmemory.core.temporal import RelationalContext


class TestEpisodicMemory:
    """Test EpisodicMemory implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.episodic_memory = EpisodicMemory()

    def test_initialization(self):
        """Test proper initialization"""
        assert len(self.episodic_memory.episodes) == 0
        assert len(self.episodic_memory.temporal_index) == 0

    def test_add_episode(self):
        """Test adding episodes to memory"""
        now = datetime.now()
        item = MemoryItem(
            content="User asked about Python",
            event_time=now,
            ingestion_time=now,
            confidence=0.9
        )

        episode_id = self.episodic_memory.add(item)

        assert episode_id.startswith("ep_")
        assert len(self.episodic_memory.episodes) == 1
        assert episode_id in self.episodic_memory.episodes

        # Check episode structure
        episode = self.episodic_memory.episodes[episode_id]
        assert 'item' in episode
        assert 'anchor' in episode
        assert 'related' in episode
        assert episode['item'] == item

    def test_episode_grounding_anchor(self):
        """Test that episodes have proper grounding anchors"""
        now = datetime.now()
        item = MemoryItem("Test episode", now, now)

        episode_id = self.episodic_memory.add(item)
        episode = self.episodic_memory.episodes[episode_id]

        anchor = episode['anchor']
        assert anchor.event_time == now
        assert anchor.ingestion_time == now
        assert anchor.confidence == item.confidence
        assert anchor.relational.user_id == "default"  # Default relational context

    def test_temporal_index_updated(self):
        """Test that temporal index is updated when adding episodes"""
        now = datetime.now()
        item = MemoryItem("Test episode", now, now)

        episode_id = self.episodic_memory.add(item)

        assert episode_id in self.episodic_memory.temporal_index
        anchor = self.episodic_memory.temporal_index[episode_id]
        assert anchor.event_time == now

    def test_retrieve_episodes_by_content(self):
        """Test retrieving episodes by content query"""
        now = datetime.now()

        # Add different episodes
        episodes_data = [
            "User asked about Python programming",
            "Discussed JavaScript frameworks",
            "Explained Python libraries",
            "Talked about database design"
        ]

        for content in episodes_data:
            item = MemoryItem(content, now, now)
            self.episodic_memory.add(item)

        # Search for Python episodes
        results = self.episodic_memory.retrieve("Python")

        assert len(results) == 2
        python_contents = [item.content for item in results]
        assert "User asked about Python programming" in python_contents
        assert "Explained Python libraries" in python_contents

    def test_retrieve_with_limit(self):
        """Test retrieve with result limit"""
        now = datetime.now()

        # Add multiple Python episodes
        for i in range(5):
            item = MemoryItem(f"Python episode {i}", now, now)
            self.episodic_memory.add(item)

        results = self.episodic_memory.retrieve("Python", limit=3)
        assert len(results) == 3

    def test_retrieve_no_matches(self):
        """Test retrieve with no matching episodes"""
        now = datetime.now()
        item = MemoryItem("JavaScript tutorial", now, now)
        self.episodic_memory.add(item)

        results = self.episodic_memory.retrieve("Python")
        assert len(results) == 0

    def test_retrieve_case_insensitive(self):
        """Test case-insensitive episode retrieval"""
        now = datetime.now()
        item = MemoryItem("Python Programming Tutorial", now, now)
        self.episodic_memory.add(item)

        results_lower = self.episodic_memory.retrieve("python")
        results_upper = self.episodic_memory.retrieve("PYTHON")
        results_mixed = self.episodic_memory.retrieve("PyThOn")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    def test_get_episodes_between_times(self):
        """Test retrieving episodes within time range"""
        base_time = datetime.now()

        # Add episodes at different times
        episodes_data = [
            (base_time - timedelta(hours=3), "Old episode"),
            (base_time - timedelta(hours=1), "Recent episode 1"),
            (base_time - timedelta(minutes=30), "Recent episode 2"),
            (base_time, "Current episode")
        ]

        for event_time, content in episodes_data:
            item = MemoryItem(content, event_time, base_time)
            self.episodic_memory.add(item)

        # Get episodes from last 2 hours
        start_time = base_time - timedelta(hours=2)
        end_time = base_time

        results = self.episodic_memory.get_episodes_between(start_time, end_time)

        assert len(results) == 3  # Should exclude the 3-hour-old episode
        contents = [item.content for item in results]
        assert "Old episode" not in contents
        assert "Recent episode 1" in contents
        assert "Recent episode 2" in contents
        assert "Current episode" in contents

    def test_episodes_sorted_by_time(self):
        """Test that episodes between times are sorted chronologically"""
        base_time = datetime.now()

        # Add episodes in random order
        episodes_data = [
            (base_time - timedelta(hours=2), "Episode A"),
            (base_time, "Episode C"),
            (base_time - timedelta(hours=1), "Episode B")
        ]

        for event_time, content in episodes_data:
            item = MemoryItem(content, event_time, base_time)
            self.episodic_memory.add(item)

        # Get all episodes
        start_time = base_time - timedelta(hours=3)
        end_time = base_time + timedelta(hours=1)

        results = self.episodic_memory.get_episodes_between(start_time, end_time)

        # Should be sorted by event time
        contents = [item.content for item in results]
        assert contents == ["Episode A", "Episode B", "Episode C"]

    def test_consolidate_placeholder(self):
        """Test consolidate method (placeholder implementation)"""
        now = datetime.now()
        item = MemoryItem("Test episode", now, now)
        self.episodic_memory.add(item)

        # Current implementation is placeholder
        result = self.episodic_memory.consolidate()
        assert result == 0  # Placeholder returns 0

    def test_episode_relationships_structure(self):
        """Test episode relationship structure"""
        now = datetime.now()
        item = MemoryItem("Test episode", now, now)

        episode_id = self.episodic_memory.add(item)
        episode = self.episodic_memory.episodes[episode_id]

        # Should have related episodes list (initially empty)
        assert 'related' in episode
        assert isinstance(episode['related'], list)
        assert len(episode['related']) == 0

    def test_multiple_episodes_distinct_ids(self):
        """Test that multiple episodes get distinct IDs"""
        now = datetime.now()

        episode_ids = []
        for i in range(3):
            item = MemoryItem(f"Episode {i}", now, now)
            episode_id = self.episodic_memory.add(item)
            episode_ids.append(episode_id)

        # All IDs should be unique
        assert len(set(episode_ids)) == 3
        assert all(eid.startswith("ep_") for eid in episode_ids)

    def test_episode_temporal_distinction(self):
        """Test temporal distinction between event and ingestion times"""
        event_time = datetime.now() - timedelta(hours=1)
        ingestion_time = datetime.now()

        item = MemoryItem("Past event", event_time, ingestion_time)
        episode_id = self.episodic_memory.add(item)

        episode = self.episodic_memory.episodes[episode_id]
        anchor = episode['anchor']

        assert anchor.event_time == event_time
        assert anchor.ingestion_time == ingestion_time
        assert anchor.event_time < anchor.ingestion_time

    def test_episode_validity_span(self):
        """Test episode validity span initialization"""
        now = datetime.now()
        item = MemoryItem("Test episode", now, now)

        episode_id = self.episodic_memory.add(item)
        episode = self.episodic_memory.episodes[episode_id]

        anchor = episode['anchor']
        validity_span = anchor.validity_span

        assert validity_span.start == now
        assert validity_span.end is None  # Open-ended validity
        assert validity_span.valid is True

    def test_complex_content_types(self):
        """Test episodes with complex content types"""
        now = datetime.now()

        # Dictionary content (conversation interaction)
        dict_content = {
            "user": "What is Python?",
            "assistant": "Python is a programming language",
            "context": "programming_help"
        }
        dict_item = MemoryItem(dict_content, now, now)
        episode_id_1 = self.episodic_memory.add(dict_item)

        # List content
        list_content = ["action_taken", "search", {"query": "Python"}]
        list_item = MemoryItem(list_content, now, now)
        episode_id_2 = self.episodic_memory.add(list_item)

        assert len(self.episodic_memory.episodes) == 2
        assert episode_id_1 in self.episodic_memory.episodes
        assert episode_id_2 in self.episodic_memory.episodes

        # Should be able to retrieve by string search in complex content
        results = self.episodic_memory.retrieve("Python")
        assert len(results) >= 1  # Should find at least the dict content