"""
Tests for CoreMemory - Agent identity and persona (MemGPT/Letta pattern).
"""

import pytest
from datetime import datetime
from abstractmemory.components.core import CoreMemory, CoreMemoryBlock
from abstractmemory.core.interfaces import MemoryItem


class TestCoreMemoryBlock:
    """Test CoreMemoryBlock data structure"""

    def test_creation(self):
        """Test block creation"""
        now = datetime.now()
        block = CoreMemoryBlock(
            block_id="test_block",
            label="test",
            content="Test content",
            last_updated=now
        )

        assert block.block_id == "test_block"
        assert block.label == "test"
        assert block.content == "Test content"
        assert block.last_updated == now
        assert block.edit_count == 0

    def test_update(self):
        """Test block update functionality"""
        now = datetime.now()
        block = CoreMemoryBlock(
            block_id="test",
            label="test",
            content="Original content",
            last_updated=now
        )

        # Update the block
        block.update("New content", "Test reasoning")

        assert block.content == "New content"
        assert block.edit_count == 1
        assert block.last_updated > now

    def test_multiple_updates(self):
        """Test multiple updates increment count"""
        block = CoreMemoryBlock("test", "test", "content", datetime.now())

        for i in range(3):
            block.update(f"Content {i}", f"Update {i}")

        assert block.edit_count == 3
        assert block.content == "Content 2"


class TestCoreMemory:
    """Test CoreMemory implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.core_memory = CoreMemory()

    def test_initialization(self):
        """Test proper initialization with default blocks"""
        assert len(self.core_memory.blocks) == 2
        assert "persona" in self.core_memory.blocks
        assert "user_info" in self.core_memory.blocks

        # Check default content
        persona_block = self.core_memory.blocks["persona"]
        assert "AI assistant" in persona_block.content
        assert "persistent memory" in persona_block.content

        user_block = self.core_memory.blocks["user_info"]
        assert "User information will be learned" in user_block.content

    def test_get_context(self):
        """Test context string generation"""
        context = self.core_memory.get_context()

        assert "[persona]" in context
        assert "[user_info]" in context
        assert "AI assistant" in context
        assert "User information" in context

    def test_update_block(self):
        """Test updating existing blocks"""
        new_persona = "I am a specialized Python programming assistant."
        success = self.core_memory.update_block("persona", new_persona, "Specialization update")

        assert success is True
        assert self.core_memory.blocks["persona"].content == new_persona
        assert self.core_memory.blocks["persona"].edit_count == 1

    def test_update_nonexistent_block(self):
        """Test updating non-existent block"""
        success = self.core_memory.update_block("nonexistent", "content", "reasoning")
        assert success is False

    def test_update_block_too_long(self):
        """Test updating block with content too long"""
        # Create very long content (exceeding token limit)
        long_content = "x" * 1000  # Much longer than 200 tokens * 4
        success = self.core_memory.update_block("persona", long_content, "test")

        assert success is False
        # Original content should be unchanged
        assert "AI assistant" in self.core_memory.blocks["persona"].content

    def test_add_block(self):
        """Test adding new memory blocks"""
        block_id = self.core_memory.add_block("preferences", "User prefers concise answers")

        assert block_id is not None
        assert block_id in self.core_memory.blocks
        assert self.core_memory.blocks[block_id].label == "preferences"
        assert self.core_memory.blocks[block_id].content == "User prefers concise answers"

    def test_add_block_when_full(self):
        """Test adding blocks when at capacity"""
        # Fill up to capacity
        for i in range(8):  # Already have 2, max is 10
            self.core_memory.add_block(f"block_{i}", f"Content {i}")

        # This should still work
        assert len(self.core_memory.blocks) == 10

        # This should fail
        block_id = self.core_memory.add_block("overflow", "Too many blocks")
        assert block_id is None
        assert len(self.core_memory.blocks) == 10

    def test_add_memory_item_user_content(self):
        """Test adding MemoryItem with user-related content"""
        now = datetime.now()
        item = MemoryItem(
            content="User Alice loves Python programming",
            event_time=now,
            ingestion_time=now
        )

        result = self.core_memory.add(item)
        assert result == "user_info"

        # Check that user_info block was updated
        user_block = self.core_memory.blocks["user_info"]
        assert "Alice loves Python" in user_block.content

    def test_add_memory_item_persona_content(self):
        """Test adding MemoryItem with persona-related content"""
        now = datetime.now()
        item = MemoryItem(
            content="Agent persona: I am helpful and friendly",
            event_time=now,
            ingestion_time=now
        )

        result = self.core_memory.add(item)
        assert result == "persona"

        # Check that persona block was updated
        persona_block = self.core_memory.blocks["persona"]
        assert "helpful and friendly" in persona_block.content

    def test_add_memory_item_general_content(self):
        """Test adding MemoryItem with general content"""
        now = datetime.now()
        item = MemoryItem(
            content="Python is a programming language",
            event_time=now,
            ingestion_time=now
        )

        result = self.core_memory.add(item)
        # Should create new general block
        assert result != ""
        assert result in self.core_memory.blocks

    def test_retrieve_matching_content(self):
        """Test retrieving core memory blocks by query"""
        # Add some content
        self.core_memory.update_block("persona", "I am a Python expert assistant", "test")
        self.core_memory.add_block("languages", "Python, JavaScript, Go")

        # Search for Python
        results = self.core_memory.retrieve("Python")

        assert len(results) >= 1
        # Should find the persona block
        found_persona = any(
            "Python expert" in str(item.content) for item in results
        )
        assert found_persona

    def test_retrieve_by_label(self):
        """Test retrieving by block label"""
        results = self.core_memory.retrieve("persona")

        assert len(results) >= 1
        # Should find block with persona label
        found = any(
            item.metadata.get("block_id") == "persona" for item in results
        )
        assert found

    def test_retrieve_with_limit(self):
        """Test retrieve with result limit"""
        # Add several blocks
        for i in range(5):
            self.core_memory.add_block(f"test_{i}", f"test content {i}")

        results = self.core_memory.retrieve("test", limit=3)
        assert len(results) <= 3

    def test_retrieve_no_matches(self):
        """Test retrieve with no matching content"""
        results = self.core_memory.retrieve("nonexistent_term")
        assert len(results) == 0

    def test_consolidate_does_nothing(self):
        """Test that core memory doesn't consolidate"""
        # Core memory is manually curated, not consolidated
        result = self.core_memory.consolidate()
        assert result == 0

    def test_memory_item_structure(self):
        """Test structure of returned MemoryItem objects"""
        self.core_memory.update_block("persona", "Updated persona", "test")
        results = self.core_memory.retrieve("persona")

        assert len(results) > 0
        item = results[0]

        # Check MemoryItem structure
        assert hasattr(item, 'content')
        assert hasattr(item, 'event_time')
        assert hasattr(item, 'ingestion_time')
        assert hasattr(item, 'confidence')
        assert hasattr(item, 'metadata')

        # Core memory should always be high confidence
        assert item.confidence == 1.0

        # Should have metadata about the block
        assert 'block_id' in item.metadata
        assert 'edit_count' in item.metadata

    def test_context_after_updates(self):
        """Test context reflects updates"""
        # Update persona
        self.core_memory.update_block("persona", "I am a specialized coding assistant", "test")

        # Update user info
        self.core_memory.update_block("user_info", "User prefers detailed explanations", "test")

        context = self.core_memory.get_context()

        assert "specialized coding assistant" in context
        assert "detailed explanations" in context
        assert "[persona]" in context
        assert "[user_info]" in context