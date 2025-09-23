"""
Tests for ScratchpadMemory - ReAct agent memory.
"""

import pytest
from datetime import datetime
from abstractmemory.simple import ScratchpadMemory


class TestScratchpadMemory:
    """Test ScratchpadMemory for ReAct agents and task tools"""

    def setup_method(self):
        """Setup test environment"""
        self.scratchpad = ScratchpadMemory(max_entries=10)

    def test_initialization(self):
        """Test proper initialization"""
        assert len(self.scratchpad) == 0
        assert len(self.scratchpad.thoughts) == 0
        assert len(self.scratchpad.actions) == 0
        assert len(self.scratchpad.observations) == 0

    def test_add_thought(self):
        """Test adding thoughts for ReAct pattern"""
        thought = "I need to search for Python tutorials"
        self.scratchpad.add_thought(thought)

        assert len(self.scratchpad.thoughts) == 1
        assert self.scratchpad.thoughts[0] == thought
        assert len(self.scratchpad) == 1

    def test_add_action(self):
        """Test adding actions with parameters"""
        action = "search"
        params = {"query": "Python basics", "limit": 10}
        self.scratchpad.add_action(action, params)

        assert len(self.scratchpad.actions) == 1
        assert self.scratchpad.actions[0]["action"] == action
        assert self.scratchpad.actions[0]["params"] == params
        assert len(self.scratchpad) == 1

    def test_add_observation(self):
        """Test adding observations"""
        observation = "Found 10 Python tutorials"
        self.scratchpad.add_observation(observation)

        assert len(self.scratchpad.observations) == 1
        assert self.scratchpad.observations[0] == observation
        assert len(self.scratchpad) == 1

    def test_react_cycle(self):
        """Test complete ReAct thought-action-observation cycle"""
        # Simulate a ReAct cycle
        self.scratchpad.add_thought("User wants to learn Python")
        self.scratchpad.add_action("search", {"query": "Python tutorials"})
        self.scratchpad.add_observation("Found tutorials on w3schools and official docs")
        self.scratchpad.add_thought("Should recommend official docs first")

        # Verify cycle recorded correctly
        assert len(self.scratchpad.thoughts) == 2
        assert len(self.scratchpad.actions) == 1
        assert len(self.scratchpad.observations) == 1
        assert len(self.scratchpad) == 4

    def test_get_context_formatting(self):
        """Test context formatting for LLM consumption"""
        self.scratchpad.add_thought("Need to find Python info")
        self.scratchpad.add_action("search", {"query": "Python"})
        self.scratchpad.add_observation("Found Python documentation")

        context = self.scratchpad.get_context()
        lines = context.split('\n')

        assert "Thought: Need to find Python info" in lines
        assert any("Action:" in line for line in lines)
        assert "Observation: Found Python documentation" in lines

    def test_get_context_with_limit(self):
        """Test context retrieval with entry limit"""
        # Add more entries than limit
        for i in range(5):
            self.scratchpad.add_thought(f"Thought {i}")

        context = self.scratchpad.get_context(last_n=2)
        lines = context.split('\n')

        # Should only have last 2 entries
        assert len(lines) == 2
        assert "Thought 3" in context
        assert "Thought 4" in context
        assert "Thought 0" not in context

    def test_react_history_structure(self):
        """Test structured ReAct history retrieval"""
        self.scratchpad.add_thought("Think about task")
        self.scratchpad.add_action("execute", {"param": "value"})
        self.scratchpad.add_observation("Got result")

        history = self.scratchpad.get_react_history()

        assert "thoughts" in history
        assert "actions" in history
        assert "observations" in history
        assert len(history["thoughts"]) == 1
        assert len(history["actions"]) == 1
        assert len(history["observations"]) == 1

    def test_clear_functionality(self):
        """Test clearing scratchpad memory"""
        self.scratchpad.add_thought("Test thought")
        self.scratchpad.add_action("test", {})
        self.scratchpad.add_observation("Test observation")

        assert len(self.scratchpad) == 3

        self.scratchpad.clear()

        assert len(self.scratchpad) == 0
        assert len(self.scratchpad.thoughts) == 0
        assert len(self.scratchpad.actions) == 0
        assert len(self.scratchpad.observations) == 0

    def test_bounded_memory_overflow(self):
        """Test memory stays within bounds"""
        scratchpad = ScratchpadMemory(max_entries=3)

        # Add more entries than capacity
        for i in range(5):
            scratchpad.add_thought(f"Thought {i}")

        # Should only keep last 3 entries
        assert len(scratchpad) == 3
        context = scratchpad.get_context()
        assert "Thought 2" in context
        assert "Thought 3" in context
        assert "Thought 4" in context
        assert "Thought 0" not in context
        assert "Thought 1" not in context

    def test_add_generic_entry(self):
        """Test adding generic entries with custom types"""
        self.scratchpad.add("This is a note", "note")
        self.scratchpad.add("This is a warning", "warning")

        assert len(self.scratchpad) == 2
        context = self.scratchpad.get_context()
        assert "This is a note" in context
        assert "This is a warning" in context

    def test_string_representation(self):
        """Test string representation"""
        self.scratchpad.add_thought("Test")
        repr_str = str(self.scratchpad)
        assert "ScratchpadMemory" in repr_str
        assert "1 entries" in repr_str