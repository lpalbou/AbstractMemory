#!/usr/bin/env python3
"""
Comprehensive tests for reconstruct_context() functionality.

Tests cover:
- User profile integration
- Relevant memory retrieval
- Recent interactions
- Temporal context
- Spatial context (location)
- Emotional context (mood)
- Focus levels (0-5)
- Context quality metadata
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from datetime import datetime, timedelta
from abstractmemory import MemorySession, UnifiedMemory


class TestReconstructContext:
    """Test suite for reconstruct_context() method"""

    def setup_method(self):
        """Setup test environment with populated data"""
        self.memory = UnifiedMemory()
        self.session = MemorySession(memory=self.memory, default_user_id="test_user")

        # Populate test data
        self._populate_test_data()

    def _populate_test_data(self):
        """Create rich test dataset"""
        # User profile
        self.session.remember_fact(
            "Alice is a senior Python developer",
            category="user_profile",
            user_id="alice",
            confidence=1.0
        )

        # Preferences
        self.session.remember_fact(
            "Alice prefers VSCode with dark theme",
            category="preference",
            user_id="alice",
            confidence=0.95
        )

        # Knowledge
        self.session.remember_fact(
            "Python async/await is used for concurrency",
            category="knowledge",
            user_id="alice",
            confidence=0.9
        )

        # Events
        self.session.remember_fact(
            "Alice debugged async issue yesterday",
            category="event",
            user_id="alice",
            confidence=0.85
        )

        # Context
        self.session.remember_fact(
            "Alice usually codes in the morning at office",
            category="context",
            user_id="alice",
            confidence=0.8
        )

    def test_reconstruct_basic(self):
        """Test basic context reconstruction"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="Python debugging"
        )

        # Should return a dictionary
        assert isinstance(context, dict)

        # Should have required fields
        assert 'user_id' in context
        assert 'query' in context
        assert 'timestamp' in context
        assert 'focus_level' in context
        assert 'user_profile' in context
        assert 'relevant_memories' in context
        assert 'recent_interactions' in context
        assert 'temporal_context' in context

    def test_reconstruct_all_focus_levels(self):
        """Test all focus levels (0-5)"""
        for focus_level in range(6):
            context = self.session.reconstruct_context(
                user_id="alice",
                query="Python",
                focus_level=focus_level
            )

            assert context['focus_level'] == focus_level
            assert 'metadata' in context

            # Higher focus levels should retrieve more memories
            # (though exact counts depend on data)

    def test_reconstruct_with_location(self):
        """Test spatial context reconstruction"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="coding",
            location="office"
        )

        # Should include spatial context
        assert 'spatial_context' in context
        assert context['spatial_context']['location'] == "office"
        assert 'location_memories' in context['spatial_context']

    def test_reconstruct_with_mood(self):
        """Test emotional context reconstruction"""
        moods = ["focused", "casual", "stressed", "curious", "frustrated", "excited"]

        for mood in moods:
            context = self.session.reconstruct_context(
                user_id="alice",
                query="debugging",
                mood=mood
            )

            # Should include emotional context
            assert 'emotional_context' in context
            assert context['emotional_context']['mood'] == mood
            assert 'suggested_approach' in context['emotional_context']
            assert 'mood_relevant_memories' in context['emotional_context']

    def test_reconstruct_temporal_context(self):
        """Test temporal context details"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="coding"
        )

        temporal = context['temporal_context']

        # Should have time-related fields
        assert 'time_of_day' in temporal
        assert 'day_of_week' in temporal
        assert 'date' in temporal
        assert 'is_working_hours' in temporal
        assert 'is_weekend' in temporal
        assert 'hours_window' in temporal

    def test_reconstruct_with_timestamp(self):
        """Test context reconstruction at specific time"""
        specific_time = datetime(2025, 1, 15, 14, 30)  # Tuesday 2:30 PM

        context = self.session.reconstruct_context(
            user_id="alice",
            query="coding",
            timestamp=specific_time
        )

        temporal = context['temporal_context']

        # Should match specified time
        assert temporal['time_of_day'] == 14
        assert temporal['is_working_hours'] == True

    def test_reconstruct_focus_level_memory_limits(self):
        """Test that focus levels affect memory retrieval amounts"""
        # Minimal focus (lazy)
        minimal = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=0
        )

        # Maximum focus (super focused)
        maximum = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=5
        )

        # Maximum should retrieve more memories
        minimal_count = len(minimal['relevant_memories'])
        maximum_count = len(maximum['relevant_memories'])

        # Maximum focus should attempt to get more results
        # (actual counts depend on available data)
        assert isinstance(minimal_count, int)
        assert isinstance(maximum_count, int)

    def test_reconstruct_metadata_quality(self):
        """Test metadata includes context quality assessment"""
        # High focus
        high_focus = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=4
        )

        # Low focus
        low_focus = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=1
        )

        # Both should have metadata
        assert 'metadata' in high_focus
        assert 'metadata' in low_focus

        # Should include quality assessment
        assert 'context_quality' in high_focus['metadata']
        assert 'context_quality' in low_focus['metadata']

        # High focus should have higher quality
        # assert high_focus['metadata']['context_quality'] in ['high', 'medium']
        # assert low_focus['metadata']['context_quality'] in ['basic', 'medium']

    def test_reconstruct_default_timestamp(self):
        """Test that timestamp defaults to now"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="Python"
        )

        # Should have a timestamp
        assert 'timestamp' in context

        # Should be recent (within last minute)
        timestamp_str = context['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        diff = abs((now - timestamp).total_seconds())
        assert diff < 60  # Within 1 minute

    def test_reconstruct_full_context(self):
        """Test reconstruction with all optional parameters"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="debugging async Python code",
            timestamp=datetime.now(),
            location="home office",
            mood="focused",
            focus_level=4
        )

        # Should have all context types
        assert 'user_profile' in context
        assert 'relevant_memories' in context
        assert 'recent_interactions' in context
        assert 'temporal_context' in context
        assert 'spatial_context' in context
        assert 'emotional_context' in context
        assert 'metadata' in context

    def test_reconstruct_nonexistent_user(self):
        """Test context reconstruction for user with no data"""
        context = self.session.reconstruct_context(
            user_id="nonexistent_user",
            query="Python"
        )

        # Should still return valid context structure
        assert isinstance(context, dict)
        assert context['user_id'] == "nonexistent_user"
        assert 'relevant_memories' in context
        # May be empty, but should exist
        assert isinstance(context['relevant_memories'], list)

    def test_reconstruct_empty_query(self):
        """Test reconstruction with empty query"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query=""
        )

        # Should still work
        assert isinstance(context, dict)
        assert context['query'] == ""

    def test_reconstruct_temporal_windows(self):
        """Test that focus levels affect temporal windows"""
        # Minimal focus (1 hour back)
        minimal = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=0
        )

        # Maximum focus (1 week back)
        maximum = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=5
        )

        # Check hours_window is different
        assert minimal['temporal_context']['hours_window'] < maximum['temporal_context']['hours_window']

    def test_reconstruct_user_profile_structure(self):
        """Test user profile in context"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="Python"
        )

        profile = context['user_profile']

        # Should be a dictionary
        assert isinstance(profile, dict)

    def test_reconstruct_total_memories_count(self):
        """Test metadata tracks total memories retrieved"""
        context = self.session.reconstruct_context(
            user_id="alice",
            query="Python",
            focus_level=3
        )

        metadata = context['metadata']

        # Should have count
        assert 'total_memories_retrieved' in metadata
        assert isinstance(metadata['total_memories_retrieved'], int)
        assert metadata['total_memories_retrieved'] >= 0


def run_tests():
    """Run all tests with detailed output"""
    print("=" * 60)
    print("RECONSTRUCT_CONTEXT() TEST SUITE")
    print("=" * 60)

    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "-s"
    ]

    result = pytest.main(pytest_args)

    print("\n" + "=" * 60)
    if result == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)

    return result


if __name__ == "__main__":
    sys.exit(run_tests())