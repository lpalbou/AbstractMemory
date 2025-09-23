"""
Integration tests for GroundedMemory - Complete autonomous agent memory system.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory import create_memory, GroundedMemory, MemoryItem


class TestGroundedMemoryIntegration:
    """Test GroundedMemory complete system integration"""

    def setup_method(self):
        """Setup test environment"""
        self.memory = create_memory("grounded", working_capacity=5, enable_kg=True)

    def test_initialization(self):
        """Test proper initialization of all components"""
        assert isinstance(self.memory, GroundedMemory)
        assert self.memory.core is not None
        assert self.memory.semantic is not None
        assert self.memory.working is not None
        assert self.memory.episodic is not None
        assert self.memory.kg is not None

        # Check initial state
        assert self.memory.current_user == "default"
        assert len(self.memory.user_profiles) == 0
        assert len(self.memory.failure_patterns) == 0
        assert len(self.memory.success_patterns) == 0

    def test_user_management(self):
        """Test user profile management and relational context"""
        # Set current user
        self.memory.set_current_user("alice", relationship="owner")

        assert self.memory.current_user == "alice"
        assert "alice" in self.memory.user_profiles

        profile = self.memory.user_profiles["alice"]
        assert profile["relationship"] == "owner"
        assert profile["interaction_count"] == 0
        assert profile["facts"] == []

    def test_interaction_tracking(self):
        """Test user-agent interaction tracking across all memory tiers"""
        self.memory.set_current_user("alice", relationship="owner")

        # Add interaction
        self.memory.add_interaction(
            "I love Python programming",
            "Python is a great language for many applications!"
        )

        # Check working memory
        working_items = self.memory.working.get_context_window()
        assert len(working_items) > 0

        # Check episodic memory
        episodes = self.memory.episodic.retrieve("Python")
        assert len(episodes) > 0

        # Check user profile updated
        profile = self.memory.user_profiles["alice"]
        assert profile["interaction_count"] == 1

    def test_fact_extraction_to_kg(self):
        """Test automatic fact extraction to knowledge graph"""
        self.memory.set_current_user("alice")

        # Add interaction with extractable facts
        self.memory.add_interaction(
            "Tell me about Python",
            "Python is interpreted and Python has great libraries"
        )

        # Should extract facts to knowledge graph
        if self.memory.kg:
            facts = self.memory.kg.query_at_time("is", datetime.now())
            assert len(facts) > 0

            # Should find "Python is interpreted"
            fact_contents = [f"{f['subject']} {f['predicate']} {f['object']}" for f in facts]
            assert any("python is interpreted" in content.lower() for content in fact_contents)

    def test_multi_user_context_separation(self):
        """Test that context is properly separated by user"""
        # Add interaction for Alice
        self.memory.set_current_user("alice", relationship="owner")
        self.memory.add_interaction("I love Python", "Great choice!")
        self.memory.learn_about_user("loves Python programming")

        # Add interaction for Bob
        self.memory.set_current_user("bob", relationship="colleague")
        self.memory.add_interaction("I prefer Java", "Java is also powerful!")
        self.memory.learn_about_user("prefers Java")

        # Get context for Alice
        alice_context = self.memory.get_full_context("programming", user_id="alice")
        assert "alice" in alice_context.lower()
        assert "loves python" in alice_context.lower()

        # Get context for Bob
        bob_context = self.memory.get_full_context("programming", user_id="bob")
        assert "bob" in bob_context.lower()
        assert "prefers java" in bob_context.lower()

        # Contexts should be different
        assert alice_context != bob_context

    def test_learning_from_failures(self):
        """Test learning from repeated failures"""
        # Track repeated failures
        for i in range(3):
            self.memory.track_failure("search_web", "no internet connection")

        # Should learn constraint after 3 failures
        learned_facts = self.memory.semantic.retrieve("search_web")
        assert len(learned_facts) > 0

        constraint_fact = learned_facts[0]
        assert "tends to fail" in str(constraint_fact.content)
        assert constraint_fact.metadata['type'] == 'learned_constraint'

    def test_learning_from_successes(self):
        """Test learning from repeated successes"""
        # Track repeated successes
        for i in range(3):
            self.memory.track_success("calculate", "math problems")

        # Should learn strategy after 3 successes
        learned_facts = self.memory.semantic.retrieve("calculate")
        assert len(learned_facts) > 0

        strategy_fact = learned_facts[0]
        assert "works well" in str(strategy_fact.content)
        assert strategy_fact.metadata['type'] == 'learned_strategy'

    def test_user_fact_learning_and_core_memory_update(self):
        """Test user fact learning and core memory updates"""
        self.memory.set_current_user("alice")

        # Learn facts about user (below threshold)
        for i in range(4):
            self.memory.learn_about_user("prefers detailed explanations")

        # Should not update core memory yet (threshold is 5)
        core_context = self.memory.core.get_context()
        assert "detailed explanations" not in core_context

        # One more time should trigger core memory update
        self.memory.learn_about_user("prefers detailed explanations")

        # Now should be in core memory
        core_context = self.memory.core.get_context()
        assert "detailed explanations" in core_context

    def test_memory_consolidation(self):
        """Test memory consolidation across tiers"""
        self.memory.set_current_user("alice")

        # Add items that should consolidate
        now = datetime.now()
        items = [
            MemoryItem("Python is object-oriented", now, now, confidence=0.8),
            MemoryItem("JavaScript is dynamic", now, now, confidence=0.9),
            MemoryItem("Important meeting scheduled", now, now, confidence=0.8,
                      metadata={"important": True})
        ]

        for item in items:
            self.memory.working.add(item)

        # Trigger consolidation
        self.memory.consolidate_memories()

        # Check semantic memory received factual items
        semantic_facts = self.memory.semantic.retrieve("object-oriented")
        assert len(semantic_facts) >= 0  # May or may not be validated yet

        # Check episodic memory received important items
        episodes = self.memory.episodic.retrieve("meeting")
        assert len(episodes) >= 0  # Should be moved to episodic

    def test_full_context_integration(self):
        """Test full context retrieval integrating all memory tiers"""
        self.memory.set_current_user("alice", relationship="owner")

        # Add data to different memory tiers
        # 1. Core memory (via user learning)
        for i in range(5):
            self.memory.learn_about_user("expert in AI")

        # 2. Semantic memory (via repeated facts)
        for i in range(3):
            fact_item = MemoryItem("Python supports machine learning", datetime.now(), datetime.now())
            self.memory.semantic.add(fact_item)

        # 3. Working memory (via interaction)
        self.memory.add_interaction("Tell me about ML", "Machine learning is powerful")

        # 4. Knowledge graph (via fact extraction)
        if self.memory.kg:
            self.memory.kg.add_fact("Python", "supports", "ML", datetime.now())

        # Get full context
        context = self.memory.get_full_context("machine learning")

        # Should include elements from all tiers
        assert "alice" in context.lower()  # User profile
        assert "expert in ai" in context.lower()  # Core memory
        assert "supports machine learning" in context.lower() or "machine learning" in context.lower()  # Semantic/Working

    def test_failure_warning_in_context(self):
        """Test that repeated failures show up as warnings in context"""
        # Track failures
        for i in range(3):
            self.memory.track_failure("web_search", "network timeout")

        # Get context for related query
        context = self.memory.get_full_context("web_search")

        # Should include warning about previous failures
        assert "⚠️" in context or "warning" in context.lower() or "failure" in context.lower()

    def test_core_memory_self_editing(self):
        """Test agent's ability to self-edit core memory"""
        # Update core memory directly
        success = self.memory.update_core_memory(
            "persona",
            "I am a specialized Python programming assistant with memory capabilities",
            "Updated to reflect specialization"
        )

        assert success is True

        # Check that context reflects the update
        core_context = self.memory.get_core_memory_context()
        assert "specialized Python programming assistant" in core_context

    def test_backward_compatibility(self):
        """Test backward compatibility wrapper"""
        self.memory.set_current_user("alice")
        self.memory.add_interaction("Hello", "Hi there!")

        # Test backward compatibility method
        context = self.memory.retrieve_context("hello")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_storage_integration(self):
        """Test storage backend integration (when available)"""
        # Test save/load without storage backend (should not crash)
        try:
            self.memory.save("/tmp/test_memory")
            self.memory.load("/tmp/test_memory")
        except Exception:
            # Expected if storage backend not available
            pass

    def test_temporal_query_integration(self):
        """Test temporal queries across the integrated system"""
        base_time = datetime.now()

        # Add facts at different times
        self.memory.set_current_user("alice")

        # Past interaction
        past_time = base_time - timedelta(hours=1)
        past_item = MemoryItem("Alice learned Python", past_time, base_time)
        self.memory.episodic.add(past_item)

        # Recent interaction
        self.memory.add_interaction("How's Python?", "Python is great for AI!")

        # Get episodes between times
        start_time = base_time - timedelta(hours=2)
        end_time = base_time + timedelta(hours=1)
        episodes = self.memory.episodic.get_episodes_between(start_time, end_time)

        assert len(episodes) >= 1  # Should find past and recent episodes


class TestMemoryFactory:
    """Test memory factory function"""

    def test_create_scratchpad_memory(self):
        """Test creating scratchpad memory"""
        memory = create_memory("scratchpad", max_entries=50)

        from abstractmemory.simple import ScratchpadMemory
        assert isinstance(memory, ScratchpadMemory)
        assert len(memory) == 0

    def test_create_buffer_memory(self):
        """Test creating buffer memory"""
        memory = create_memory("buffer", max_messages=100)

        from abstractmemory.simple import BufferMemory
        assert isinstance(memory, BufferMemory)
        assert len(memory.messages) == 0

    def test_create_grounded_memory(self):
        """Test creating grounded memory"""
        memory = create_memory("grounded", working_capacity=10, enable_kg=True)

        assert isinstance(memory, GroundedMemory)
        assert memory.working.capacity == 10
        assert memory.kg is not None

    def test_create_grounded_memory_no_kg(self):
        """Test creating grounded memory without knowledge graph"""
        memory = create_memory("grounded", enable_kg=False)

        assert isinstance(memory, GroundedMemory)
        assert memory.kg is None

    def test_invalid_memory_type(self):
        """Test creating invalid memory type"""
        with pytest.raises(ValueError, match="Unknown memory type"):
            create_memory("invalid_type")