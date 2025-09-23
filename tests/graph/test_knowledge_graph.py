"""
Tests for TemporalKnowledgeGraph - Bi-temporal knowledge representation.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory.graph.knowledge_graph import TemporalKnowledgeGraph


class TestTemporalKnowledgeGraph:
    """Test TemporalKnowledgeGraph implementation"""

    def setup_method(self):
        """Setup test environment"""
        self.kg = TemporalKnowledgeGraph()

    def test_initialization(self):
        """Test proper initialization"""
        assert self.kg.graph.number_of_nodes() == 0
        assert self.kg.graph.number_of_edges() == 0
        assert self.kg._node_counter == 0
        assert self.kg._edge_counter == 0
        assert len(self.kg.ontology) == 0

    def test_add_entity(self):
        """Test adding entities to the graph"""
        entity_id = self.kg.add_entity("Python", "language")

        assert entity_id.startswith("entity_")
        assert self.kg.graph.number_of_nodes() == 1
        assert self.kg.graph.nodes[entity_id]['value'] == "Python"
        assert self.kg.graph.nodes[entity_id]['type'] == "language"

    def test_add_entity_deduplication(self):
        """Test that duplicate entities are not created"""
        # Add same entity twice
        id1 = self.kg.add_entity("Python", "language")
        id2 = self.kg.add_entity("Python", "language")

        # Should return same ID
        assert id1 == id2
        assert self.kg.graph.number_of_nodes() == 1

    def test_add_entity_updates_ontology(self):
        """Test that ontology is updated when adding entities"""
        self.kg.add_entity("Python", "language")
        self.kg.add_entity("JavaScript", "language")
        self.kg.add_entity("Alice", "person")

        assert "language" in self.kg.ontology
        assert "person" in self.kg.ontology
        assert len(self.kg.ontology["language"]) == 2
        assert len(self.kg.ontology["person"]) == 1

    def test_add_fact(self):
        """Test adding facts to the knowledge graph"""
        now = datetime.now()
        fact_id = self.kg.add_fact(
            subject="Python",
            predicate="is",
            object="programming language",
            event_time=now,
            confidence=0.9
        )

        assert fact_id.startswith("edge_")
        assert self.kg.graph.number_of_nodes() == 2  # Python and "programming language"
        assert self.kg.graph.number_of_edges() == 1

        # Check edge data
        edges = list(self.kg.graph.edges(data=True, keys=True))
        _, _, key, data = edges[0]
        assert data['predicate'] == "is"
        assert data['confidence'] == 0.9
        assert data['valid'] is True

    def test_fact_temporal_anchoring(self):
        """Test temporal anchoring of facts"""
        event_time = datetime.now() - timedelta(hours=1)
        fact_id = self.kg.add_fact("Alice", "knows", "Python", event_time)

        edges = list(self.kg.graph.edges(data=True, keys=True))
        _, _, _, data = edges[0]

        anchor = data['anchor']
        assert anchor.event_time == event_time
        assert anchor.ingestion_time > event_time
        assert anchor.validity_span.start == event_time

    def test_query_at_time_basic(self):
        """Test basic temporal queries"""
        base_time = datetime.now()
        event_time = base_time - timedelta(hours=1)

        # Add fact that happened 1 hour ago (use base_time as ingestion time to avoid microsecond issues)
        self.kg.add_fact("Python", "is", "interpreted", event_time, ingestion_time=base_time)

        # Query at current time - should find the fact
        results = self.kg.query_at_time("is", base_time)

        assert len(results) == 1
        result = results[0]
        assert result['subject'] == "Python"
        assert result['predicate'] == "is"
        assert result['object'] == "interpreted"

    def test_query_at_time_before_knowledge(self):
        """Test query before fact was learned"""
        base_time = datetime.now()
        event_time = base_time - timedelta(hours=1)

        # Add fact (learned now, but event happened 1 hour ago)
        self.kg.add_fact("Python", "is", "interpreted", event_time)

        # Query before we learned about it (2 hours ago)
        query_time = base_time - timedelta(hours=2)
        results = self.kg.query_at_time("is", query_time)

        assert len(results) == 0  # Shouldn't know about it yet

    def test_query_at_time_future_event(self):
        """Test query for future events"""
        base_time = datetime.now()
        future_time = base_time + timedelta(hours=1)

        # Add fact about future event
        self.kg.add_fact("Conference", "starts", "tomorrow", future_time)

        # Query at current time - shouldn't find future event
        results = self.kg.query_at_time("starts", base_time)

        assert len(results) == 0

    def test_fact_contradictions(self):
        """Test handling of contradictory facts"""
        base_time = datetime.now()

        # Add initial fact
        self.kg.add_fact("Alice", "works_at", "Company A", base_time - timedelta(hours=2), ingestion_time=base_time - timedelta(hours=2))

        # Add contradictory fact (newer)
        self.kg.add_fact("Alice", "works_at", "Company B", base_time - timedelta(hours=1), ingestion_time=base_time - timedelta(hours=1))

        # Query should show newer fact is valid
        results = self.kg.query_at_time("works_at", base_time)

        # Should have one valid fact (newer one)
        valid_results = [r for r in results if r['object'] == "Company B"]
        assert len(valid_results) == 1

    def test_get_entity_evolution(self):
        """Test tracking entity evolution over time"""
        base_time = datetime.now()

        # Add facts about Alice at different times
        self.kg.add_fact("Alice", "works_at", "Company A", base_time - timedelta(hours=3))
        self.kg.add_fact("Alice", "learns", "Python", base_time - timedelta(hours=2))
        self.kg.add_fact("Alice", "works_at", "Company B", base_time - timedelta(hours=1))

        # Get Alice's evolution over last 4 hours
        start_time = base_time - timedelta(hours=4)
        evolution = self.kg.get_entity_evolution("Alice", start_time, base_time)

        assert len(evolution) == 3
        # Should be sorted by time
        times = [event['time'] for event in evolution]
        assert times == sorted(times)

        # Check event types
        assert all(event['type'] in ['fact_added', 'fact_invalidated'] for event in evolution)

    def test_get_entity_evolution_nonexistent(self):
        """Test evolution for non-existent entity"""
        base_time = datetime.now()
        start_time = base_time - timedelta(hours=1)

        evolution = self.kg.get_entity_evolution("NonExistent", start_time, base_time)
        assert len(evolution) == 0

    def test_multiple_fact_types(self):
        """Test knowledge graph with multiple fact types"""
        now = datetime.now()

        # Add different types of facts
        facts = [
            ("Python", "is", "language"),
            ("Alice", "knows", "Python"),
            ("Python", "has", "syntax"),
            ("Alice", "works_at", "TechCorp")
        ]

        for subject, predicate, obj in facts:
            self.kg.add_fact(subject, predicate, obj, now, ingestion_time=now)

        # Test different predicate queries
        is_results = self.kg.query_at_time("is", now)
        knows_results = self.kg.query_at_time("knows", now)
        has_results = self.kg.query_at_time("has", now)

        assert len(is_results) == 1
        assert len(knows_results) == 1
        assert len(has_results) == 1

    def test_fact_metadata_preservation(self):
        """Test that fact metadata is preserved"""
        now = datetime.now()
        fact_id = self.kg.add_fact(
            "Python", "created_by", "Guido",
            event_time=now,
            confidence=0.95,
            source="Wikipedia",
            ingestion_time=now
        )

        results = self.kg.query_at_time("created_by", now)

        assert len(results) == 1
        result = results[0]
        assert result['confidence'] == 0.95
        assert result['source'] == "Wikipedia"
        assert result['event_time'] == now

    def test_temporal_overlap_detection(self):
        """Test temporal overlap detection between facts"""
        base_time = datetime.now()

        # Add overlapping facts about same relationship
        self.kg.add_fact("Alice", "lives_in", "City A", base_time - timedelta(hours=2))
        self.kg.add_fact("Alice", "lives_in", "City B", base_time - timedelta(hours=1))

        # Both facts should exist in graph but older one should be invalidated
        all_edges = list(self.kg.graph.edges(data=True, keys=True))

        # Should have 2 edges total
        assert len(all_edges) == 2

        # But only one should be valid
        valid_edges = [edge for edge in all_edges if edge[3]['valid']]
        assert len(valid_edges) == 1

        # Valid edge should be the newer one
        valid_edge = valid_edges[0]
        anchor = valid_edge[3]['anchor']
        assert anchor.event_time == base_time - timedelta(hours=1)

    def test_case_sensitive_entities(self):
        """Test that entities are case-sensitive"""
        now = datetime.now()

        # Add facts with different cases
        self.kg.add_fact("python", "is", "language", now)
        self.kg.add_fact("Python", "is", "popular", now)

        # Should create separate entities
        assert self.kg.graph.number_of_nodes() == 4  # python, Python, language, popular

    def test_confidence_tracking(self):
        """Test confidence tracking in facts"""
        now = datetime.now()

        # Add facts with different confidence levels
        self.kg.add_fact("Python", "is", "easy", now, confidence=0.8, ingestion_time=now)
        self.kg.add_fact("Python", "is", "powerful", now, confidence=0.95, ingestion_time=now)

        results = self.kg.query_at_time("is", now)

        assert len(results) == 2
        confidences = [r['confidence'] for r in results]
        assert 0.8 in confidences
        assert 0.95 in confidences

    def test_empty_graph_queries(self):
        """Test queries on empty graph"""
        now = datetime.now()

        results = self.kg.query_at_time("any_predicate", now)
        assert len(results) == 0

        evolution = self.kg.get_entity_evolution("any_entity", now, now)
        assert len(evolution) == 0