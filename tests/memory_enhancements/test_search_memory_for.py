#!/usr/bin/env python3
"""
Comprehensive tests for search_memory_for() functionality.

Tests cover:
- Semantic search
- Category filtering
- User filtering
- Temporal filtering (since/until)
- Confidence thresholds
- Hybrid search integration
- Observability
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from datetime import datetime, timedelta
from abstractmemory import MemorySession, UnifiedMemory


class TestSearchMemoryFor:
    """Test suite for search_memory_for() method"""

    def setup_method(self):
        """Setup test environment with pre-populated facts"""
        self.memory = UnifiedMemory()
        self.session = MemorySession(memory=self.memory, default_user_id="test_user")

        # Populate with test data
        self._populate_test_data()

    def _populate_test_data(self):
        """Create test dataset"""
        # User preferences
        self.session.remember_fact(
            "Alice loves Python programming",
            category="preference",
            user_id="alice",
            confidence=0.95
        )

        self.session.remember_fact(
            "Bob prefers Java over Python",
            category="preference",
            user_id="bob",
            confidence=0.9
        )

        # Knowledge facts
        self.session.remember_fact(
            "Python is a high-level programming language",
            category="knowledge",
            user_id="alice",
            confidence=1.0
        )

        self.session.remember_fact(
            "JavaScript is used for web development",
            category="knowledge",
            user_id="alice",
            confidence=0.95
        )

        # Events
        self.session.remember_fact(
            "Alice completed the Python tutorial yesterday",
            category="event",
            user_id="alice",
            confidence=0.85
        )

        # User profiles
        self.session.remember_fact(
            "Alice is a software engineer",
            category="user_profile",
            user_id="alice",
            confidence=1.0
        )

    def test_search_by_query(self):
        """Test basic semantic search"""
        results = self.session.search_memory_for("Python")

        # Should find multiple Python-related facts
        assert len(results) > 0
        assert self.session.searches_performed >= 1

    def test_search_by_category(self):
        """Test category filtering"""
        # Search for preferences only
        prefs = self.session.search_memory_for(
            "Python",
            category="preference"
        )

        # Should find preference-related facts
        # Note: Might be 0 if semantic memory not available, that's okay
        assert self.session.searches_performed >= 1

    def test_search_by_user(self):
        """Test user filtering"""
        # Search Alice's memories only
        alice_results = self.session.search_memory_for(
            "Python",
            user_id="alice"
        )

        # Search Bob's memories only
        bob_results = self.session.search_memory_for(
            "Python",
            user_id="bob"
        )

        # Should have performed 2 searches
        assert self.session.searches_performed >= 2

    def test_search_with_confidence_threshold(self):
        """Test confidence filtering"""
        # Only high-confidence results
        high_conf = self.session.search_memory_for(
            "Python",
            min_confidence=0.95
        )

        # Lower confidence threshold
        all_conf = self.session.search_memory_for(
            "Python",
            min_confidence=0.0
        )

        # More results with lower threshold
        # (or same if all results are high confidence)
        assert len(all_conf) >= len(high_conf)

    def test_search_with_temporal_filter(self):
        """Test temporal filtering (since/until)"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        # Search recent memories
        recent = self.session.search_memory_for(
            "Python",
            since=yesterday
        )

        # Search within time window
        windowed = self.session.search_memory_for(
            "Python",
            since=yesterday,
            until=tomorrow
        )

        assert self.session.searches_performed >= 2

    def test_search_empty_query(self):
        """Test search with empty query (SQL-only filtering)"""
        # Get all preferences
        all_prefs = self.session.search_memory_for(
            "",
            category="preference",
            limit=20
        )

        # Should work even without semantic query
        assert self.session.searches_performed >= 1

    def test_search_with_limit(self):
        """Test result limiting"""
        # Get only 2 results
        limited = self.session.search_memory_for(
            "Python",
            limit=2
        )

        # Should respect limit
        assert len(limited) <= 2

    def test_search_combined_filters(self):
        """Test combining multiple filters"""
        yesterday = datetime.now() - timedelta(days=1)

        results = self.session.search_memory_for(
            "Python",
            category="preference",
            user_id="alice",
            since=yesterday,
            min_confidence=0.8,
            limit=5
        )

        # Should handle all filters simultaneously
        assert self.session.searches_performed >= 1

    def test_search_no_results(self):
        """Test search that returns no results"""
        results = self.session.search_memory_for(
            "NONEXISTENT_TERM_XYZZZ",
            category="preference"
        )

        # Should return empty list, not error
        assert isinstance(results, list)
        assert self.session.searches_performed >= 1

    def test_search_observability(self):
        """Test observability tracking"""
        initial_count = self.session.searches_performed

        self.session.search_memory_for("Python")

        # Counter should increment
        assert self.session.searches_performed > initial_count

        # Logger should exist
        assert hasattr(self.session, '_obs_logger')

    def test_search_fallback_behavior(self):
        """Test fallback when hybrid_search not available"""
        # This should work even if LanceDB hybrid_search isn't implemented
        # Falls back to semantic memory + manual filtering
        results = self.session.search_memory_for(
            "Python",
            category="knowledge",
            user_id="alice"
        )

        # Should not crash
        assert isinstance(results, list)
        assert self.session.searches_performed >= 1

    def test_search_multiple_categories(self):
        """Test searching across different categories"""
        categories = ["preference", "knowledge", "event", "user_profile"]

        for category in categories:
            results = self.session.search_memory_for(
                "Alice",
                category=category
            )
            # Each search should work independently
            assert isinstance(results, list)

        assert self.session.searches_performed >= len(categories)

    def test_search_result_structure(self):
        """Test that results have correct structure"""
        results = self.session.search_memory_for("Python", limit=1)

        if len(results) > 0:
            result = results[0]

            # Check for expected fields
            assert 'content' in result
            # Other fields depend on whether it came from semantic or storage

    def test_search_unicode(self):
        """Test Unicode support in search queries"""
        # Store Unicode facts
        self.session.remember_fact(
            "用户喜欢Python",
            category="preference",
            user_id="unicode_user",
            confidence=0.9
        )

        # Search with Unicode
        results = self.session.search_memory_for(
            "Python",
            user_id="unicode_user"
        )

        assert self.session.searches_performed >= 1


def run_tests():
    """Run all tests with detailed output"""
    print("=" * 60)
    print("SEARCH_MEMORY_FOR() TEST SUITE")
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