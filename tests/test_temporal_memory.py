"""
Test temporal memory implementation.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory import TemporalMemory
from abstractmemory.core.interfaces import MemoryItem
from abstractmemory.graph.knowledge_graph import TemporalKnowledgeGraph


class TestTemporalMemory:
    """Test temporal memory system"""

    def test_memory_creation(self):
        """Test memory can be created"""
        memory = TemporalMemory(working_capacity=5)
        assert memory.working is not None
        assert memory.episodic is not None
        assert memory.kg is not None

    def test_add_interaction(self):
        """Test adding interactions"""
        memory = TemporalMemory(working_capacity=5)

        # Add interaction
        memory.add_interaction("Hello", "Hi there!")

        # Check working memory has items
        assert len(memory.working.items) == 1

        # Check episodic memory has items
        assert len(memory.episodic.episodes) == 1

    def test_retrieve_context(self):
        """Test context retrieval"""
        memory = TemporalMemory(working_capacity=5)

        # Add some interactions
        memory.add_interaction("My name is Alice", "Nice to meet you, Alice!")
        memory.add_interaction("I like programming", "That's great!")

        # Retrieve context
        context = memory.retrieve_context("Alice")
        assert "Alice" in context

    def test_working_memory_capacity(self):
        """Test working memory capacity limit"""
        memory = TemporalMemory(working_capacity=3)

        # Add more items than capacity
        for i in range(5):
            memory.add_interaction(f"Message {i}", f"Response {i}")

        # Working memory should not exceed capacity
        assert len(memory.working.items) <= 3


class TestKnowledgeGraph:
    """Test knowledge graph functionality"""

    def test_graph_creation(self):
        """Test graph can be created"""
        graph = TemporalKnowledgeGraph()
        assert graph.graph is not None
        assert len(graph.ontology) == 0

    def test_add_entity(self):
        """Test adding entities"""
        graph = TemporalKnowledgeGraph()

        # Add entity
        entity_id = graph.add_entity("Alice", "Person")
        assert entity_id is not None
        assert len(graph.graph.nodes) == 1

        # Should deduplicate
        entity_id2 = graph.add_entity("Alice", "Person")
        assert entity_id == entity_id2
        assert len(graph.graph.nodes) == 1

    def test_add_fact(self):
        """Test adding facts"""
        graph = TemporalKnowledgeGraph()

        # Add fact
        fact_id = graph.add_fact(
            subject="Alice",
            predicate="works_at",
            object="OpenAI",
            event_time=datetime.now()
        )
        assert fact_id is not None
        assert len(graph.graph.edges) == 1

    def test_query_at_time(self):
        """Test temporal queries"""
        graph = TemporalKnowledgeGraph()

        # Add fact
        now = datetime.now()
        graph.add_fact("Alice", "works_at", "OpenAI", now)

        # Query should find the fact
        facts = graph.query_at_time("works_at", now + timedelta(seconds=1))
        assert len(facts) == 1
        assert facts[0]['subject'] == "Alice"
        assert facts[0]['predicate'] == "works_at"
        assert facts[0]['object'] == "OpenAI"