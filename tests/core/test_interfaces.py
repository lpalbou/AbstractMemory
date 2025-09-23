"""
Tests for core memory interfaces and data structures.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory.core.interfaces import MemoryItem, IMemoryComponent


class TestMemoryItem:
    """Test MemoryItem data structure"""

    def test_basic_creation(self):
        """Test basic MemoryItem creation"""
        now = datetime.now()
        item = MemoryItem(
            content="Test content",
            event_time=now,
            ingestion_time=now,
            confidence=0.8
        )

        assert item.content == "Test content"
        assert item.event_time == now
        assert item.ingestion_time == now
        assert item.confidence == 0.8
        assert item.metadata == {}

    def test_with_metadata(self):
        """Test MemoryItem with metadata"""
        now = datetime.now()
        metadata = {"source": "test", "type": "fact"}

        item = MemoryItem(
            content="Test with metadata",
            event_time=now,
            ingestion_time=now,
            metadata=metadata
        )

        assert item.metadata == metadata
        assert item.metadata["source"] == "test"
        assert item.metadata["type"] == "fact"

    def test_default_metadata(self):
        """Test default metadata initialization"""
        now = datetime.now()
        item = MemoryItem(
            content="Test",
            event_time=now,
            ingestion_time=now
        )

        assert item.metadata == {}
        assert isinstance(item.metadata, dict)

    def test_confidence_defaults(self):
        """Test confidence default value"""
        now = datetime.now()
        item = MemoryItem(
            content="Test",
            event_time=now,
            ingestion_time=now
        )

        assert item.confidence == 1.0

    def test_temporal_distinction(self):
        """Test temporal distinction between event_time and ingestion_time"""
        event_time = datetime.now() - timedelta(hours=1)
        ingestion_time = datetime.now()

        item = MemoryItem(
            content="Past event",
            event_time=event_time,
            ingestion_time=ingestion_time
        )

        assert item.event_time < item.ingestion_time
        assert (item.ingestion_time - item.event_time).total_seconds() > 3500

    def test_content_types(self):
        """Test different content types"""
        now = datetime.now()

        # String content
        string_item = MemoryItem("string", now, now)
        assert isinstance(string_item.content, str)

        # Dict content
        dict_content = {"type": "fact", "data": "value"}
        dict_item = MemoryItem(dict_content, now, now)
        assert isinstance(dict_item.content, dict)

        # List content
        list_content = ["item1", "item2", "item3"]
        list_item = MemoryItem(list_content, now, now)
        assert isinstance(list_item.content, list)


class MockMemoryComponent(IMemoryComponent):
    """Mock implementation for testing interface"""

    def __init__(self):
        self.items = []

    def add(self, item: MemoryItem) -> str:
        item_id = f"item_{len(self.items)}"
        self.items.append((item_id, item))
        return item_id

    def retrieve(self, query: str, limit: int = 10) -> list[MemoryItem]:
        results = []
        for _, item in self.items:
            if query.lower() in str(item.content).lower():
                results.append(item)
                if len(results) >= limit:
                    break
        return results

    def consolidate(self) -> int:
        return len(self.items)


class TestIMemoryComponent:
    """Test IMemoryComponent interface through mock implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.component = MockMemoryComponent()

    def test_add_and_retrieve(self):
        """Test basic add and retrieve functionality"""
        now = datetime.now()
        item = MemoryItem("Python is a programming language", now, now)

        # Test add
        item_id = self.component.add(item)
        assert item_id.startswith("item_")

        # Test retrieve
        results = self.component.retrieve("Python")
        assert len(results) == 1
        assert results[0].content == item.content

    def test_retrieve_with_limit(self):
        """Test retrieve with result limit"""
        now = datetime.now()

        # Add multiple items
        for i in range(5):
            item = MemoryItem(f"Python fact {i}", now, now)
            self.component.add(item)

        # Test limit enforcement
        results = self.component.retrieve("Python", limit=3)
        assert len(results) == 3

    def test_retrieve_no_matches(self):
        """Test retrieve with no matching items"""
        now = datetime.now()
        item = MemoryItem("Java is also a language", now, now)
        self.component.add(item)

        results = self.component.retrieve("Python")
        assert len(results) == 0

    def test_consolidate(self):
        """Test consolidate functionality"""
        now = datetime.now()

        # Add some items
        for i in range(3):
            item = MemoryItem(f"Item {i}", now, now)
            self.component.add(item)

        # Test consolidate
        consolidated_count = self.component.consolidate()
        assert consolidated_count == 3

    def test_case_insensitive_search(self):
        """Test case-insensitive retrieval"""
        now = datetime.now()
        item = MemoryItem("Python is Great", now, now)
        self.component.add(item)

        # Test different cases
        results_lower = self.component.retrieve("python")
        results_upper = self.component.retrieve("PYTHON")
        results_mixed = self.component.retrieve("PyThOn")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1