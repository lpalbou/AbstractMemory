"""
Test Memory Validation - Prevent AI from hallucinating user facts

Tests the fixes for the critical memory hallucination issue where AI was
creating false memories about users (e.g., "User has interest in science fiction")
when the user had only said "hello".
"""

import pytest
from pathlib import Path
import shutil
from datetime import datetime

from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider


# Test memory base path
TEST_MEMORY_PATH = Path("test_memory_validation")


@pytest.fixture(scope="module")
def setup_test_environment():
    """Setup and cleanup test environment."""
    # Clean up any existing test directory
    if TEST_MEMORY_PATH.exists():
        shutil.rmtree(TEST_MEMORY_PATH)

    # Create test directory
    TEST_MEMORY_PATH.mkdir(parents=True, exist_ok=True)

    yield

    # Cleanup after tests
    if TEST_MEMORY_PATH.exists():
        shutil.rmtree(TEST_MEMORY_PATH)


@pytest.fixture
def memory_session(setup_test_environment):
    """Create a MemorySession for testing."""
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )
    return session


def test_1_validation_blocks_user_assumption_without_evidence(memory_session):
    """
    Test that AI cannot store assumptions about user preferences without evidence.

    This is the core issue: AI said "User has interest in both science fiction and fantasy genres"
    when user only said "hello". This should be blocked.
    """
    # Attempt to remember a user preference without evidence
    result = memory_session.remember_fact(
        content="User has interest in both science fiction and fantasy genres",
        importance=0.8,
        alignment_with_values=0.9,
        reason="This is a clear preference",
        source="ai_observed",  # Claiming to have observed, but no evidence
        evidence=""  # NO EVIDENCE
    )

    # Should be rejected
    assert result is None, "Memory should be rejected when claiming user preference without evidence"
    print("✅ PASS: AI cannot store user preferences without evidence")


def test_2_validation_requires_evidence_for_user_claims(memory_session):
    """Test that user-related claims require evidence."""
    # Attempt to store a user fact without evidence
    result = memory_session.remember_fact(
        content="User prefers concise responses",
        importance=0.7,
        source="ai_inferred",
        evidence=""  # Missing evidence
    )

    # Should be rejected
    assert result is None, "User-related claim without evidence should be rejected"
    print("✅ PASS: User claims require evidence")


def test_3_validation_accepts_user_stated_with_evidence(memory_session):
    """Test that user statements with evidence are accepted."""
    # Store a user fact with proper evidence
    result = memory_session.remember_fact(
        content="User enjoys science fiction",
        importance=0.8,
        source="user_stated",
        evidence="User said: 'I love science fiction books'",
        reason="Direct user statement about preferences"
    )

    # Should be accepted
    assert result is not None, "User statement with evidence should be accepted"
    assert result.startswith("mem_"), "Should return valid memory ID"
    print(f"✅ PASS: User statements with evidence accepted: {result}")


def test_4_ai_reflections_allowed_without_user_evidence(memory_session):
    """Test that AI's own reflections don't require user evidence."""
    # AI reflecting on its own processing
    result = memory_session.remember_fact(
        content="I notice I tend to default to book recommendations when greeted",
        importance=0.7,
        source="ai_reflection",
        reason="Self-awareness about response patterns"
    )

    # Should be accepted (it's about AI, not user)
    assert result is not None, "AI self-reflections should be allowed"
    print(f"✅ PASS: AI self-reflections allowed: {result}")


def test_5_validation_checks_reliability_scores(memory_session):
    """Test that reliability scores are calculated correctly."""
    # Test different source types
    sources = [
        ("user_stated", 0.95),
        ("ai_observed", 0.80),
        ("ai_inferred", 0.60),
        ("ai_reflection", 0.70),
    ]

    for source, expected_min in sources:
        reliability = memory_session._calculate_reliability(source, "")
        assert reliability >= expected_min - 0.01, f"Reliability for {source} should be >= {expected_min}"
        print(f"✅ PASS: {source} reliability = {reliability:.2f} (expected >= {expected_min})")


def test_6_hello_scenario_no_false_memories(memory_session):
    """
    Test the exact scenario from the bug report.

    User says "hello". AI should NOT create any memories about user preferences.
    This is the integration test for the full fix.
    """
    # Simulate what would happen if AI tries to remember false facts after "hello"
    false_memories = [
        "User has interest in both science fiction and fantasy genres",
        "User enjoys reading",
        "User prefers plot-driven narratives",
        "User is looking for book recommendations",
    ]

    rejected_count = 0
    for false_memory in false_memories:
        result = memory_session.remember_fact(
            content=false_memory,
            importance=0.8,
            source="ai_observed",
            evidence=""  # No evidence - user only said "hello"!
        )
        if result is None:
            rejected_count += 1

    # ALL should be rejected
    assert rejected_count == len(false_memories), \
        f"All {len(false_memories)} false memories should be rejected"

    print(f"✅ PASS: All {rejected_count}/{len(false_memories)} hallucinated memories rejected")
    print("✅ FIX VERIFIED: AI can no longer create false user preferences on 'hello'")


def test_7_memory_includes_source_and_evidence_in_file(memory_session):
    """Test that saved memories include source and evidence in the markdown file."""
    # Create a valid memory with evidence
    memory_id = memory_session.remember_fact(
        content="User mentioned they work as a software engineer",
        importance=0.7,
        source="user_stated",
        evidence="User said: 'I'm a software engineer'",
        reason="Useful context for technical discussions"
    )

    assert memory_id is not None

    # Find the memory file
    memory_files = list(TEST_MEMORY_PATH.glob(f"notes/**/{memory_id}.md"))
    assert len(memory_files) > 0, "Memory file should exist"

    # Read the file and check for source/evidence section
    with open(memory_files[0], 'r') as f:
        content = f.read()

    assert "## Source & Evidence" in content, "File should have Source & Evidence section"
    assert "**Source**: user_stated" in content, "File should show source"
    assert "**Evidence**:" in content, "File should show evidence"

    print(f"✅ PASS: Memory file includes source and evidence information")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
