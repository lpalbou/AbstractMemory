"""
Tests for SemanticMemory - Validated facts and concepts.
"""

import pytest
from datetime import datetime
from abstractmemory.components.semantic import SemanticMemory
from abstractmemory.core.interfaces import MemoryItem


class TestSemanticMemory:
    """Test SemanticMemory implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.semantic_memory = SemanticMemory(validation_threshold=3)

    def test_initialization(self):
        """Test proper initialization"""
        assert self.semantic_memory.validation_threshold == 3
        assert len(self.semantic_memory.facts) == 0
        assert len(self.semantic_memory.concepts) == 0
        assert len(self.semantic_memory.pending_facts) == 0

    def test_add_fact_below_threshold(self):
        """Test adding fact below validation threshold"""
        now = datetime.now()
        item = MemoryItem("Python is a programming language", now, now)

        # First occurrence - should not be validated yet
        result = self.semantic_memory.add(item)
        assert result == ""  # Not validated
        assert len(self.semantic_memory.facts) == 0
        assert len(self.semantic_memory.pending_facts) == 1

    def test_add_fact_reaches_threshold(self):
        """Test fact validation when threshold is reached"""
        now = datetime.now()
        item = MemoryItem("Python is interpreted", now, now)

        # Add same fact multiple times
        for i in range(3):
            result = self.semantic_memory.add(item)

        # Third time should validate the fact
        assert result != ""  # Should return fact ID
        assert len(self.semantic_memory.facts) == 1
        assert len(self.semantic_memory.pending_facts) == 0

    def test_fact_confidence_grows_with_repetition(self):
        """Test that confidence increases with repetition"""
        now = datetime.now()
        item = MemoryItem("JavaScript is dynamic", now, now)

        # Add fact 5 times to exceed threshold
        for i in range(5):
            self.semantic_memory.add(item)

        # Check that confidence reflects repetition
        fact_id = list(self.semantic_memory.facts.keys())[0]
        fact = self.semantic_memory.facts[fact_id]

        assert fact['confidence'] > 0.3  # Should be higher due to multiple occurrences
        assert fact['occurrence_count'] == 3  # Validated at threshold (3), then cleared from pending

    def test_retrieve_validated_facts(self):
        """Test retrieving validated facts by query"""
        now = datetime.now()

        # Add facts to validate them
        python_item = MemoryItem("Python supports object-oriented programming", now, now)
        java_item = MemoryItem("Java is strongly typed", now, now)

        # Validate facts by adding multiple times
        for i in range(3):
            self.semantic_memory.add(python_item)
            self.semantic_memory.add(java_item)

        # Retrieve Python facts
        results = self.semantic_memory.retrieve("Python")

        assert len(results) == 1
        assert "object-oriented" in str(results[0].content)
        assert results[0].confidence > 0

    def test_retrieve_sorted_by_confidence(self):
        """Test that results are sorted by confidence"""
        now = datetime.now()

        # Create different semantic memory instances to test confidence ordering
        fact1 = MemoryItem("Python fact 1", now, now)
        fact2 = MemoryItem("Python fact 2", now, now)

        # Add both facts to reach validation threshold
        for i in range(3):
            self.semantic_memory.add(fact1)
        for i in range(3):
            self.semantic_memory.add(fact2)

        # Now manually adjust confidence to test sorting
        facts = list(self.semantic_memory.facts.values())
        if len(facts) >= 2:
            facts[0]['confidence'] = 0.4
            facts[1]['confidence'] = 0.7

        results = self.semantic_memory.retrieve("Python")

        # Should be sorted by confidence
        assert len(results) == 2
        assert results[0].confidence >= results[1].confidence

    def test_retrieve_with_limit(self):
        """Test retrieve with result limit"""
        now = datetime.now()

        # Add multiple facts
        for i in range(4):
            fact = MemoryItem(f"Python fact {i}", now, now)
            for j in range(3):  # Validate each fact
                self.semantic_memory.add(fact)

        results = self.semantic_memory.retrieve("Python", limit=2)
        assert len(results) == 2

    def test_retrieve_no_matches(self):
        """Test retrieve with no matching facts"""
        now = datetime.now()
        fact = MemoryItem("JavaScript is dynamic", now, now)

        # Validate the fact
        for i in range(3):
            self.semantic_memory.add(fact)

        results = self.semantic_memory.retrieve("Python")
        assert len(results) == 0

    def test_consolidate_builds_concepts(self):
        """Test that consolidation builds concept relationships"""
        now = datetime.now()

        # Add facts with common terms
        facts = [
            "Python programming language",
            "Python web development",
            "Language syntax rules",
            "Programming paradigms"
        ]

        # Validate all facts
        for fact_text in facts:
            fact = MemoryItem(fact_text, now, now)
            for i in range(3):
                self.semantic_memory.add(fact)

        # Consolidate to build concepts
        consolidated_count = self.semantic_memory.consolidate()

        assert consolidated_count > 0
        assert len(self.semantic_memory.concepts) > 0

        # Should have concepts for common terms
        assert "python" in self.semantic_memory.concepts
        assert "programming" in self.semantic_memory.concepts

    def test_get_concept_network(self):
        """Test retrieving concept networks"""
        now = datetime.now()

        # Add facts related to Python
        python_facts = [
            "Python is interpreted",
            "Python supports object-oriented programming",
            "Python has dynamic typing"
        ]

        # Validate facts
        for fact_text in python_facts:
            fact = MemoryItem(fact_text, now, now)
            for i in range(3):
                self.semantic_memory.add(fact)

        # Consolidate to build concepts
        self.semantic_memory.consolidate()

        # Get Python concept network
        network = self.semantic_memory.get_concept_network("python")

        assert network['concept'] == "python"
        assert len(network['facts']) > 0
        assert any("interpreted" in str(fact) for fact in network['facts'])

    def test_get_concept_network_nonexistent(self):
        """Test retrieving non-existent concept"""
        network = self.semantic_memory.get_concept_network("nonexistent")

        assert network['concept'] == "nonexistent"
        assert network['facts'] == []

    def test_different_validation_threshold(self):
        """Test with different validation threshold"""
        memory = SemanticMemory(validation_threshold=2)
        now = datetime.now()
        fact = MemoryItem("Test fact", now, now)

        # Should validate after 2 occurrences
        memory.add(fact)
        assert len(memory.facts) == 0

        memory.add(fact)
        assert len(memory.facts) == 1

    def test_pending_facts_tracking(self):
        """Test tracking of pending facts"""
        now = datetime.now()
        fact1 = MemoryItem("Fact one", now, now)
        fact2 = MemoryItem("Fact two", now, now)

        # Add facts below threshold
        self.semantic_memory.add(fact1)
        self.semantic_memory.add(fact2)
        self.semantic_memory.add(fact1)  # Second occurrence of fact1

        assert len(self.semantic_memory.pending_facts) == 2
        assert self.semantic_memory.pending_facts["fact one"] == 2
        assert self.semantic_memory.pending_facts["fact two"] == 1

    def test_fact_metadata_preservation(self):
        """Test that fact metadata is preserved"""
        now = datetime.now()
        fact = MemoryItem("Test fact", now, now, confidence=0.8)

        # Validate the fact
        for i in range(3):
            self.semantic_memory.add(fact)

        results = self.semantic_memory.retrieve("Test")

        assert len(results) == 1
        result = results[0]

        # Check that temporal information is preserved
        assert result.event_time == now
        assert result.ingestion_time is not None

        # Check metadata
        assert 'occurrence_count' in result.metadata
        assert result.metadata['occurrence_count'] == 3

    def test_case_insensitive_fact_validation(self):
        """Test case-insensitive fact validation"""
        now = datetime.now()

        # Add same fact with different cases
        fact1 = MemoryItem("Python is great", now, now)
        fact2 = MemoryItem("PYTHON IS GREAT", now, now)
        fact3 = MemoryItem("python is great", now, now)

        # All should count toward same fact
        self.semantic_memory.add(fact1)
        self.semantic_memory.add(fact2)
        self.semantic_memory.add(fact3)

        # Should validate as one fact
        assert len(self.semantic_memory.facts) == 1
        assert len(self.semantic_memory.pending_facts) == 0