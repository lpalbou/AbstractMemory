"""
Tests for WorkingMemory - Short-term sliding window memory.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory.components.working import WorkingMemory
from abstractmemory.core.interfaces import MemoryItem


class TestWorkingMemory:
    """Test WorkingMemory implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.working_memory = WorkingMemory(capacity=5)

    def test_initialization(self):
        """Test proper initialization"""
        assert self.working_memory.capacity == 5
        assert len(self.working_memory.items) == 0

    def test_add_item(self):
        """Test adding items to working memory"""
        now = datetime.now()
        item = MemoryItem(
            content="Test memory item",
            event_time=now,
            ingestion_time=now
        )

        item_id = self.working_memory.add(item)

        assert item_id.startswith("wm_")
        assert len(self.working_memory.items) == 1

        # Verify item is stored correctly
        stored_id, stored_item = list(self.working_memory.items)[0]
        assert stored_id == item_id
        assert stored_item == item

    def test_capacity_limit(self):
        """Test that working memory respects capacity limit"""
        now = datetime.now()

        # Add exactly capacity number of items
        for i in range(5):
            item = MemoryItem(f"Item {i}", now, now)
            self.working_memory.add(item)

        assert len(self.working_memory.items) == 5

        # Add one more - should trigger consolidation
        item = MemoryItem("Item 5", now, now)
        self.working_memory.add(item)

        # Should have consolidated (removed half)
        assert len(self.working_memory.items) <= 5

    def test_retrieve_matching_items(self):
        """Test retrieving items by query"""
        now = datetime.now()

        # Add different items
        items_data = [
            "Python is a programming language",
            "JavaScript is used for web development",
            "Python has great libraries",
            "Databases store information"
        ]

        for content in items_data:
            item = MemoryItem(content, now, now)
            self.working_memory.add(item)

        # Search for Python-related items
        results = self.working_memory.retrieve("Python")

        assert len(results) == 2
        python_contents = [item.content for item in results]
        assert "Python is a programming language" in python_contents
        assert "Python has great libraries" in python_contents

    def test_retrieve_with_limit(self):
        """Test retrieve with result limit"""
        now = datetime.now()

        # Add multiple Python-related items
        for i in range(4):
            item = MemoryItem(f"Python fact {i}", now, now)
            self.working_memory.add(item)

        # Retrieve with limit
        results = self.working_memory.retrieve("Python", limit=2)

        assert len(results) == 2

    def test_retrieve_no_matches(self):
        """Test retrieve with no matching items"""
        now = datetime.now()
        item = MemoryItem("JavaScript tutorial", now, now)
        self.working_memory.add(item)

        results = self.working_memory.retrieve("Python")
        assert len(results) == 0

    def test_retrieve_case_insensitive(self):
        """Test case-insensitive retrieval"""
        now = datetime.now()
        item = MemoryItem("Python Programming", now, now)
        self.working_memory.add(item)

        # Test different cases
        results_lower = self.working_memory.retrieve("python")
        results_upper = self.working_memory.retrieve("PYTHON")
        results_mixed = self.working_memory.retrieve("PyThOn")

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    def test_consolidate(self):
        """Test memory consolidation"""
        now = datetime.now()

        # Fill working memory
        for i in range(4):
            item = MemoryItem(f"Item {i}", now, now)
            self.working_memory.add(item)

        assert len(self.working_memory.items) == 4

        # Manually trigger consolidation
        consolidated_count = self.working_memory.consolidate()

        # Should remove half the items
        assert consolidated_count == 2
        assert len(self.working_memory.items) == 2

    def test_get_context_window(self):
        """Test getting current context window"""
        now = datetime.now()

        # Add items
        items_data = ["Item 1", "Item 2", "Item 3"]
        for content in items_data:
            item = MemoryItem(content, now, now)
            self.working_memory.add(item)

        context_window = self.working_memory.get_context_window()

        assert len(context_window) == 3
        contents = [item.content for item in context_window]
        assert "Item 1" in contents
        assert "Item 2" in contents
        assert "Item 3" in contents

    def test_fifo_behavior_on_overflow(self):
        """Test FIFO behavior when capacity is exceeded"""
        working_memory = WorkingMemory(capacity=3)
        now = datetime.now()

        # Add items up to capacity
        for i in range(3):
            item = MemoryItem(f"Item {i}", now, now)
            working_memory.add(item)

        # Check initial state
        context = working_memory.get_context_window()
        assert len(context) == 3

        # Add one more item - should trigger consolidation
        item = MemoryItem("Item 3", now, now)
        working_memory.add(item)

        # Should have fewer items after consolidation
        context_after = working_memory.get_context_window()
        assert len(context_after) <= 3

    def test_auto_consolidation_on_capacity(self):
        """Test automatic consolidation when reaching capacity"""
        now = datetime.now()

        # Add items one by one until capacity
        for i in range(self.working_memory.capacity):
            item = MemoryItem(f"Item {i}", now, now)
            self.working_memory.add(item)

        # Should be at capacity
        assert len(self.working_memory.items) == self.working_memory.capacity

        # Add one more - deque will auto-remove oldest due to maxlen
        item = MemoryItem("Overflow item", now, now)
        self.working_memory.add(item)

        # Should still be at capacity (deque auto-manages with maxlen)
        assert len(self.working_memory.items) == self.working_memory.capacity

        # Verify the oldest item was removed and newest is present
        items = [item for _, item in self.working_memory.items]
        contents = [item.content for item in items]
        assert "Item 0" not in contents  # First item should be gone
        assert "Overflow item" in contents  # New item should be present

    def test_different_content_types(self):
        """Test working memory with different content types"""
        now = datetime.now()

        # String content
        string_item = MemoryItem("String content", now, now)
        self.working_memory.add(string_item)

        # Dict content
        dict_item = MemoryItem({"type": "dict", "value": "test"}, now, now)
        self.working_memory.add(dict_item)

        # List content
        list_item = MemoryItem(["item1", "item2"], now, now)
        self.working_memory.add(list_item)

        assert len(self.working_memory.items) == 3

        # Test retrieval works with different types
        results = self.working_memory.retrieve("String")
        assert len(results) == 1

        results_dict = self.working_memory.retrieve("dict")
        assert len(results_dict) == 1

    def test_temporal_ordering(self):
        """Test that items are processed in temporal order"""
        base_time = datetime.now()

        # Add items with different timestamps
        for i in range(3):
            # Each item added a second apart
            event_time = base_time + timedelta(seconds=i)
            item = MemoryItem(f"Item {i}", event_time, event_time)
            self.working_memory.add(item)

        context_window = self.working_memory.get_context_window()

        # Items should be in the order they were added (FIFO in deque)
        contents = [item.content for item in context_window]
        assert contents == ["Item 0", "Item 1", "Item 2"]