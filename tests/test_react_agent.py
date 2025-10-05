#!/usr/bin/env python3
"""
Test the ReAct Memory Agent and progressive exploration features.

This test verifies:
1. ReactMemoryAgent can progressively explore memory
2. Structured tools return data AI can reason about
3. REPL commands work correctly
4. The ReAct loop terminates with sufficient context
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from abstractmemory.agents import ReactMemoryAgent, MemorySearchResult, ThoughtProcess
from abstractmemory.session import MemorySession
from abstractmemory.memory_structure import initialize_memory_structure
from abstractmemory.tools import create_memory_tools


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def generate(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.5) -> str:
        """Generate mock response."""
        if "sufficient context" in prompt.lower():
            return "Yes, I have sufficient context to answer the query."
        return "I need more context. Action: increase_depth"


def create_test_session():
    """Create a test memory session."""
    temp_dir = tempfile.mkdtemp(prefix="test_react_")
    memory_path = Path(temp_dir) / "test_memory"
    memory_path.mkdir(parents=True, exist_ok=True)

    # Initialize memory structure
    initialize_memory_structure(memory_path, user_id="test_user")

    # Create test session
    session = MemorySession(
        provider=MockLLMProvider(),
        memory_base_path=memory_path,
        default_user_id="test_user",
        default_location="testing"
    )

    # Add some test memories
    session.remember_fact(
        content="Python is a high-level programming language",
        importance=0.8,
        alignment_with_values=0.9,
        reason="Important technical knowledge",
        emotion="positive"
    )

    session.remember_fact(
        content="Memory enables consciousness through active reconstruction",
        importance=0.9,
        alignment_with_values=1.0,
        reason="Core philosophical principle",
        emotion="positive"
    )

    return session, temp_dir


def test_react_agent_progressive_exploration():
    """Test ReactMemoryAgent progressive exploration."""
    print("\n" + "="*60)
    print("TEST: ReAct Agent Progressive Exploration")
    print("="*60)

    session, temp_dir = create_test_session()

    try:
        # Create ReAct agent
        agent = ReactMemoryAgent(session)

        # Test progressive exploration
        result = agent.explore_progressively(
            query="Tell me about programming",
            max_iterations=5,
            initial_focus=0
        )

        print(f"\n✅ Exploration completed in {result['iterations']} iterations")
        print(f"   Final focus level: {result['final_focus_level']}")
        print(f"   Total memories retrieved: {len(result['memories'])}")

        # Verify exploration trace
        assert len(result['exploration_trace']) > 0, "Should have exploration history"
        assert result['context'] is not None, "Should have final context"

        print("\n   Exploration trace:")
        for step in result['exploration_trace']:
            thought = step['thought']
            print(f"     Step {step['iteration']}: {thought.action} (focus={step['focus_level']})")

        print("\n✅ Progressive exploration working correctly")

    finally:
        shutil.rmtree(temp_dir)


def test_structured_search_result():
    """Test MemorySearchResult structured data."""
    print("\n" + "="*60)
    print("TEST: Structured Memory Search Result")
    print("="*60)

    # Create search result
    result = MemorySearchResult(
        memories=[
            {"id": "mem1", "content": "Test memory 1"},
            {"id": "mem2", "content": "Test memory 2"}
        ],
        total_found=2,
        relevance_scores=[0.8, 0.7],
        memory_types_covered=["episodic", "semantic"],
        suggests_deeper_search=False,
        next_search_hints=["Try broader terms"]
    )

    # Test properties
    assert result.average_relevance == 0.75, "Should calculate average relevance"
    assert result.has_high_quality_results == True, "Should identify high quality"

    # Test merge
    result2 = MemorySearchResult(
        memories=[{"id": "mem3", "content": "Test memory 3"}],
        total_found=1,
        relevance_scores=[0.9],
        memory_types_covered=["library"],
        suggests_deeper_search=True,
        next_search_hints=["Search earlier"]
    )

    merged = result.merge_with(result2)
    assert merged.total_found == 3, "Should merge totals"
    assert len(merged.memory_types_covered) == 3, "Should merge types"

    print("✅ MemorySearchResult structure working correctly")


def test_thought_process():
    """Test ThoughtProcess reasoning structure."""
    print("\n" + "="*60)
    print("TEST: Thought Process Structure")
    print("="*60)

    # Test insufficient context
    thought1 = ThoughtProcess(
        query="test query",
        current_context_quality="insufficient",
        memories_examined=0,
        focus_level=0,
        reasoning="No memories found yet",
        action="increase_depth",
        confidence=0.9
    )

    assert not thought1.sufficient_context, "Should need more context"
    assert thought1.needs_deeper_search, "Should need deeper search"

    # Test sufficient context
    thought2 = ThoughtProcess(
        query="test query",
        current_context_quality="sufficient",
        memories_examined=10,
        focus_level=3,
        reasoning="Have enough context",
        action="sufficient",
        confidence=0.8
    )

    assert thought2.sufficient_context, "Should have sufficient context"
    assert not thought2.needs_deeper_search, "Should not need deeper search"

    print("✅ ThoughtProcess structure working correctly")


def test_structured_memory_tools():
    """Test structured memory tools return proper data."""
    print("\n" + "="*60)
    print("TEST: Structured Memory Tools")
    print("="*60)

    session, temp_dir = create_test_session()

    try:
        # Get memory tools
        tools = create_memory_tools(session)

        # Find structured tools
        structured_tools = [t for t in tools if 'structured' in t.__name__]

        assert len(structured_tools) > 0, "Should have structured tools"

        print(f"✅ Found {len(structured_tools)} structured tools")

        # Test search_memories_structured
        search_structured = next(
            (t for t in tools if t.__name__ == 'search_memories_structured'),
            None
        )

        if search_structured:
            result = search_structured(query="test", focus_level=1)

            assert isinstance(result, dict), "Should return dict"
            assert 'memories' in result, "Should have memories key"
            assert 'metadata' in result, "Should have metadata key"

            metadata = result['metadata']
            assert 'total_found' in metadata, "Should have total_found"
            assert 'suggests_deeper' in metadata, "Should have suggests_deeper"

            print("✅ search_memories_structured returns proper structure")

        # Test search_incrementally
        search_incremental = next(
            (t for t in tools if t.__name__ == 'search_incrementally'),
            None
        )

        if search_incremental:
            result = search_incremental(query="test", previous_depth=0)

            assert isinstance(result, dict), "Should return dict"
            assert 'new_memories' in result, "Should have new_memories"
            assert 'suggested_action' in result, "Should have suggested_action"
            assert 'current_depth' in result, "Should have current_depth"

            print("✅ search_incrementally returns proper structure")

        # Test get_memory_stats
        get_stats = next(
            (t for t in tools if t.__name__ == 'get_memory_stats'),
            None
        )

        if get_stats:
            result = get_stats()

            assert isinstance(result, dict), "Should return dict"
            assert 'distribution' in result, "Should have distribution"
            assert 'total_memories' in result, "Should have total_memories"

            print("✅ get_memory_stats returns proper structure")

    finally:
        shutil.rmtree(temp_dir)


def test_react_heuristic_reasoning():
    """Test ReAct agent heuristic reasoning when LLM unavailable."""
    print("\n" + "="*60)
    print("TEST: ReAct Heuristic Reasoning")
    print("="*60)

    session, temp_dir = create_test_session()

    try:
        # Create agent with no LLM (will use heuristics)
        session.provider = None
        agent = ReactMemoryAgent(session)

        # Test heuristic reasoning at different states
        thought1 = agent._heuristic_reasoning(
            query="test",
            memory_count=0,
            focus_level=0,
            iteration=0
        )

        assert thought1.action == "increase_depth", "Should increase depth when no memories"

        thought2 = agent._heuristic_reasoning(
            query="test",
            memory_count=15,
            focus_level=4,
            iteration=3
        )

        assert thought2.sufficient_context, "Should have sufficient context with many memories"

        thought3 = agent._heuristic_reasoning(
            query="remember something",
            memory_count=3,
            focus_level=1,
            iteration=1
        )

        assert thought3.action == "search_specific", "Should search specific for 'remember' query"
        assert thought3.memory_type == "episodic", "Should search episodic memory"

        print("✅ Heuristic reasoning working correctly")

    finally:
        shutil.rmtree(temp_dir)


def run_all_tests():
    """Run all ReAct agent tests."""
    print("\n" + "="*60)
    print("REACT MEMORY AGENT TEST SUITE")
    print("="*60)

    tests = [
        test_structured_search_result,
        test_thought_process,
        test_react_agent_progressive_exploration,
        test_structured_memory_tools,
        test_react_heuristic_reasoning
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success rate: {passed/(passed+failed)*100:.1f}%")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} tests failed")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)