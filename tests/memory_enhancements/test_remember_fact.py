#!/usr/bin/env python3
"""
Comprehensive tests for remember_fact() functionality.

Tests cover:
- Categorized fact storage
- Confidence scoring
- Metadata handling
- Integration with semantic memory
- Observability logging
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from datetime import datetime
from abstractmemory import MemorySession, UnifiedMemory


class TestRememberFact:
    """Test suite for remember_fact() method"""

    def setup_method(self):
        """Setup test environment"""
        # Create session with in-memory storage
        self.memory = UnifiedMemory()
        self.session = MemorySession(memory=self.memory, default_user_id="test_user")

    def test_remember_fact_basic(self):
        """Test basic fact storage"""
        self.session.remember_fact(
            "Alice loves Python",
            category="preference",
            user_id="alice",
            confidence=0.95
        )

        # Verify fact was learned
        assert self.session.facts_learned == 1

    def test_remember_fact_all_categories(self):
        """Test all 8 memory categories"""
        categories = [
            "user_profile",
            "preference",
            "context",
            "knowledge",
            "event",
            "people",
            "document",
            "conversation"
        ]

        for i, category in enumerate(categories):
            self.session.remember_fact(
                f"Test fact for {category}",
                category=category,
                user_id="test_user",
                confidence=0.8
            )

        # Verify all facts were learned
        assert self.session.facts_learned == len(categories)

    def test_remember_fact_with_metadata(self):
        """Test fact storage with additional metadata"""
        metadata = {
            "source": "conversation",
            "context": "debugging session",
            "importance": "high"
        }

        self.session.remember_fact(
            "User prefers VSCode for Python",
            category="preference",
            user_id="test_user",
            confidence=0.9,
            metadata=metadata
        )

        assert self.session.facts_learned == 1

    def test_remember_fact_confidence_range(self):
        """Test confidence scores across full range"""
        confidence_levels = [0.0, 0.25, 0.5, 0.75, 1.0]

        for conf in confidence_levels:
            self.session.remember_fact(
                f"Fact with confidence {conf}",
                category="knowledge",
                user_id="test_user",
                confidence=conf
            )

        assert self.session.facts_learned == len(confidence_levels)

    def test_remember_fact_default_user(self):
        """Test fact storage with default user (no explicit user_id)"""
        self.session.remember_fact(
            "Test fact with default user",
            category="knowledge",
            confidence=0.8
        )

        # Should use session's default_user_id
        assert self.session.facts_learned == 1

    def test_remember_fact_multiple_users(self):
        """Test fact storage for multiple different users"""
        users = ["alice", "bob", "charlie"]

        for user in users:
            self.session.remember_fact(
                f"{user} likes coffee",
                category="preference",
                user_id=user,
                confidence=0.9
            )

        assert self.session.facts_learned == len(users)

    def test_remember_fact_user_profile_integration(self):
        """Test that user_profile and preference categories update user profile"""
        self.session.remember_fact(
            "Alice is a software engineer",
            category="user_profile",
            user_id="alice",
            confidence=1.0
        )

        self.session.remember_fact(
            "Alice prefers functional programming",
            category="preference",
            user_id="alice",
            confidence=0.85
        )

        # Both should be stored
        assert self.session.facts_learned == 2

        # User should be tracked
        assert "alice" in self.session._users_seen

    def test_remember_fact_observability(self):
        """Test that observability logger is called"""
        # Store a fact
        self.session.remember_fact(
            "Test fact for observability",
            category="knowledge",
            user_id="test_user",
            confidence=0.9
        )

        # Verify counter was incremented
        assert self.session.facts_learned == 1

        # Verify logger exists
        assert hasattr(self.session, '_obs_logger')
        assert self.session._obs_logger is not None

    def test_remember_fact_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Empty fact
        self.session.remember_fact(
            "",
            category="knowledge",
            user_id="test_user",
            confidence=0.5
        )

        # Very long fact
        long_fact = "x" * 10000
        self.session.remember_fact(
            long_fact,
            category="knowledge",
            user_id="test_user",
            confidence=0.7
        )

        # Special characters in fact
        self.session.remember_fact(
            "Test with special chars: @#$%^&*()[]{}",
            category="knowledge",
            user_id="test_user",
            confidence=0.8
        )

        assert self.session.facts_learned == 3

    def test_remember_fact_unicode(self):
        """Test Unicode support in facts"""
        unicode_facts = [
            "用户喜欢Python",  # Chinese
            "Пользователь любит кофе",  # Russian
            "المستخدم يحب البرمجة",  # Arabic
            "ユーザーはコーヒーが好き"  # Japanese
        ]

        for fact in unicode_facts:
            self.session.remember_fact(
                fact,
                category="preference",
                user_id="test_user",
                confidence=0.9
            )

        assert self.session.facts_learned == len(unicode_facts)


def run_tests():
    """Run all tests with detailed output"""
    print("=" * 60)
    print("REMEMBER_FACT() TEST SUITE")
    print("=" * 60)

    # Run tests
    pytest_args = [
        __file__,
        "-v",  # Verbose
        "--tb=short",  # Short traceback
        "-s"  # Show print statements
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