"""
Tests for temporal grounding and bi-temporal modeling.
"""

import pytest
from datetime import datetime, timedelta
from abstractmemory.core.temporal import (
    TemporalSpan, RelationalContext, GroundingAnchor, TemporalIndex
)


class TestTemporalSpan:
    """Test TemporalSpan for validity periods"""

    def test_basic_creation(self):
        """Test basic temporal span creation"""
        start = datetime.now()
        span = TemporalSpan(start=start)

        assert span.start == start
        assert span.end is None
        assert span.valid is True

    def test_with_end_time(self):
        """Test temporal span with end time"""
        start = datetime.now()
        end = start + timedelta(hours=1)
        span = TemporalSpan(start=start, end=end, valid=True)

        assert span.start == start
        assert span.end == end
        assert span.valid is True

    def test_invalid_span(self):
        """Test invalid temporal span"""
        start = datetime.now()
        span = TemporalSpan(start=start, valid=False)

        assert span.start == start
        assert span.valid is False


class TestRelationalContext:
    """Test RelationalContext for WHO grounding"""

    def test_basic_context(self):
        """Test basic relational context"""
        context = RelationalContext(user_id="alice")

        assert context.user_id == "alice"
        assert context.agent_id is None
        assert context.relationship is None
        assert context.session_id is None

    def test_full_context(self):
        """Test complete relational context"""
        context = RelationalContext(
            user_id="alice",
            agent_id="assistant_v1",
            relationship="owner",
            session_id="session_123"
        )

        assert context.user_id == "alice"
        assert context.agent_id == "assistant_v1"
        assert context.relationship == "owner"
        assert context.session_id == "session_123"

    def test_relationship_types(self):
        """Test different relationship types"""
        owner_context = RelationalContext(user_id="alice", relationship="owner")
        colleague_context = RelationalContext(user_id="bob", relationship="colleague")
        stranger_context = RelationalContext(user_id="charlie", relationship="stranger")

        assert owner_context.relationship == "owner"
        assert colleague_context.relationship == "colleague"
        assert stranger_context.relationship == "stranger"


class TestGroundingAnchor:
    """Test GroundingAnchor for multi-dimensional grounding"""

    def setup_method(self):
        """Setup test environment"""
        self.event_time = datetime.now() - timedelta(hours=2)
        self.ingestion_time = datetime.now()
        self.validity_span = TemporalSpan(start=self.event_time)
        self.relational = RelationalContext(user_id="alice", relationship="owner")

    def test_basic_anchor(self):
        """Test basic grounding anchor"""
        anchor = GroundingAnchor(
            event_time=self.event_time,
            ingestion_time=self.ingestion_time,
            validity_span=self.validity_span,
            relational=self.relational
        )

        assert anchor.event_time == self.event_time
        assert anchor.ingestion_time == self.ingestion_time
        assert anchor.validity_span == self.validity_span
        assert anchor.relational == self.relational
        assert anchor.confidence == 1.0

    def test_anchor_with_metadata(self):
        """Test anchor with additional grounding"""
        anchor = GroundingAnchor(
            event_time=self.event_time,
            ingestion_time=self.ingestion_time,
            validity_span=self.validity_span,
            relational=self.relational,
            confidence=0.8,
            source="user_statement",
            location="office"
        )

        assert anchor.confidence == 0.8
        assert anchor.source == "user_statement"
        assert anchor.location == "office"

    def test_temporal_distinction(self):
        """Test temporal distinction in anchor"""
        anchor = GroundingAnchor(
            event_time=self.event_time,
            ingestion_time=self.ingestion_time,
            validity_span=self.validity_span,
            relational=self.relational
        )

        # Event happened before we learned about it
        assert anchor.event_time < anchor.ingestion_time
        assert (anchor.ingestion_time - anchor.event_time).total_seconds() > 7000

    def test_relational_grounding(self):
        """Test relational grounding in anchor"""
        anchor = GroundingAnchor(
            event_time=self.event_time,
            ingestion_time=self.ingestion_time,
            validity_span=self.validity_span,
            relational=self.relational
        )

        assert anchor.relational.user_id == "alice"
        assert anchor.relational.relationship == "owner"


class TestTemporalIndex:
    """Test TemporalIndex for efficient temporal queries"""

    def setup_method(self):
        """Setup test environment"""
        self.index = TemporalIndex()
        self.base_time = datetime.now()

    def create_test_anchor(self, event_offset_hours: int, ingestion_offset_hours: int = 0, user_id: str = "alice") -> GroundingAnchor:
        """Helper to create test anchors"""
        event_time = self.base_time - timedelta(hours=event_offset_hours)
        ingestion_time = self.base_time - timedelta(hours=ingestion_offset_hours)
        validity_span = TemporalSpan(start=event_time)
        relational = RelationalContext(user_id=user_id)

        return GroundingAnchor(
            event_time=event_time,
            ingestion_time=ingestion_time,
            validity_span=validity_span,
            relational=relational
        )

    def test_add_anchor(self):
        """Test adding anchors to index"""
        anchor = self.create_test_anchor(1)
        self.index.add_anchor("anchor_1", anchor)

        assert "anchor_1" in self.index._anchors
        assert self.index._anchors["anchor_1"] == anchor

    def test_query_at_time_basic(self):
        """Test basic temporal query"""
        # Add anchor for event 2 hours ago, learned 1 hour ago
        anchor = self.create_test_anchor(event_offset_hours=2, ingestion_offset_hours=1)
        self.index.add_anchor("anchor_1", anchor)

        # Query at current time - should find the anchor
        valid_ids = self.index.query_at_time(self.base_time)
        assert "anchor_1" in valid_ids

    def test_query_at_time_not_yet_learned(self):
        """Test query before anchor was ingested"""
        # Add anchor learned 1 hour ago
        anchor = self.create_test_anchor(event_offset_hours=2, ingestion_offset_hours=1)
        self.index.add_anchor("anchor_1", anchor)

        # Query at time before we learned about it
        query_time = self.base_time - timedelta(hours=2)
        valid_ids = self.index.query_at_time(query_time)
        assert "anchor_1" not in valid_ids

    def test_query_at_time_future_event(self):
        """Test query before event happened"""
        # Add anchor for future event
        future_anchor = GroundingAnchor(
            event_time=self.base_time + timedelta(hours=1),
            ingestion_time=self.base_time,
            validity_span=TemporalSpan(start=self.base_time + timedelta(hours=1)),
            relational=RelationalContext(user_id="alice")
        )
        self.index.add_anchor("future_anchor", future_anchor)

        # Query at current time - shouldn't find future event
        valid_ids = self.index.query_at_time(self.base_time)
        assert "future_anchor" not in valid_ids

    def test_invalidated_anchor(self):
        """Test query with invalidated anchor"""
        # Create anchor that was invalidated
        anchor = self.create_test_anchor(event_offset_hours=2, ingestion_offset_hours=1)
        anchor.validity_span.end = self.base_time - timedelta(minutes=30)
        anchor.validity_span.valid = False
        self.index.add_anchor("invalidated", anchor)

        # Query at current time - shouldn't find invalidated anchor
        valid_ids = self.index.query_at_time(self.base_time)
        assert "invalidated" not in valid_ids

    def test_get_evolution(self):
        """Test knowledge evolution tracking"""
        # Add anchor learned 2 hours ago
        anchor1 = self.create_test_anchor(event_offset_hours=3, ingestion_offset_hours=2)
        self.index.add_anchor("anchor_1", anchor1)

        # Add anchor learned 1 hour ago
        anchor2 = self.create_test_anchor(event_offset_hours=2, ingestion_offset_hours=1)
        self.index.add_anchor("anchor_2", anchor2)

        # Add anchor that was invalidated 30 minutes ago
        anchor3 = self.create_test_anchor(event_offset_hours=4, ingestion_offset_hours=3)
        anchor3.validity_span.end = self.base_time - timedelta(minutes=30)
        self.index.add_anchor("anchor_3", anchor3)

        # Get evolution over last 3 hours
        start_time = self.base_time - timedelta(hours=3)
        evolution = self.index.get_evolution(start_time, self.base_time)

        # Should have 4 events: 3 additions and 1 invalidation
        # anchor_3 added (3 hours ago), anchor_1 added (2 hours ago),
        # anchor_2 added (1 hour ago), anchor_3 invalidated (30 min ago)
        assert len(evolution) == 4

        # Check events are in chronological order
        times = [event[0] for event in evolution]
        assert times == sorted(times)

        # Check event descriptions
        descriptions = [event[1] for event in evolution]
        assert any("Added: anchor_1" in desc for desc in descriptions)
        assert any("Added: anchor_2" in desc for desc in descriptions)
        assert any("Invalidated: anchor_3" in desc for desc in descriptions)

    def test_multiple_anchors_query(self):
        """Test query with multiple valid anchors"""
        # Add multiple anchors
        for i in range(3):
            anchor = self.create_test_anchor(event_offset_hours=i+1, ingestion_offset_hours=0)
            self.index.add_anchor(f"anchor_{i}", anchor)

        # Query should find all valid anchors
        valid_ids = self.index.query_at_time(self.base_time)
        assert len(valid_ids) == 3
        assert "anchor_0" in valid_ids
        assert "anchor_1" in valid_ids
        assert "anchor_2" in valid_ids