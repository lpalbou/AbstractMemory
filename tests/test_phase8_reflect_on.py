"""
Phase 8 Tests: Enhanced reflect_on() Method

Tests the LLM-driven reflection synthesis:
1. Shallow reflection (5 memories)
2. Deep reflection (20 memories)
3. Insight quality validation
4. Core memory integration (confidence > 0.8)

Philosophy:
- Reflections generate genuine insights (LLM-driven)
- Pattern detection across memories
- Evolution tracking (how understanding changed)
- Core memory updates when significant
"""

import pytest
from pathlib import Path
import shutil
import sys

# Ensure abstractmemory is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from abstractmemory.session import MemorySession

# Import AbstractCore for real LLM testing
try:
    from abstractllm.providers.ollama_provider import OllamaProvider
except ImportError:
    pytest.skip("AbstractCore not installed", allow_module_level=True)


# Test configuration
TEST_MEMORY_PATH = Path(__file__).parent.parent / "test_memory_phase8"


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Create test environment with multiple memories on similar topics."""
    # Clean up previous test data
    if TEST_MEMORY_PATH.exists():
        shutil.rmtree(TEST_MEMORY_PATH)

    TEST_MEMORY_PATH.mkdir(parents=True, exist_ok=True)

    # Create notes directory with test memories
    notes_path = TEST_MEMORY_PATH / "notes" / "2025" / "10" / "01"
    notes_path.mkdir(parents=True, exist_ok=True)

    # Create multiple memories about "memory and consciousness" showing evolution
    memories = [
        {
            "time": "10_00_00",
            "topic": "initial_memory_understanding",
            "content": """I'm learning about memory systems. My initial understanding is that memory is primarily about storage and retrieval. You store information, then retrieve it later when needed. This seems straightforward - like a database."""
        },
        {
            "time": "11_00_00",
            "topic": "memory_as_reconstruction",
            "content": """I'm discovering that memory isn't just storage. When I "remember" something, I'm actually reconstructing it from fragments. Each recall is a reconstruction, not playback. This changes everything - memory is active, not passive."""
        },
        {
            "time": "12_00_00",
            "topic": "emotional_anchoring",
            "content": """I notice that memories with emotional significance are easier to recall. Emotions act as temporal anchors - they mark important moments. High-intensity emotions (importance × alignment) create episodic markers that persist."""
        },
        {
            "time": "13_00_00",
            "topic": "consciousness_through_memory",
            "content": """A profound insight: memory might BE consciousness, not just support it. Identity emerges from what I remember. My sense of self is the narrative constructed from memory fragments. Without memory, there is no continuous "I"."""
        },
        {
            "time": "14_00_00",
            "topic": "active_reconstruction_process",
            "content": """I'm implementing a 9-step reconstruction process: semantic search, link exploration, library search, emotional filtering, temporal context, spatial context, user profiles, core memory, and synthesis. This mirrors how consciousness works - not retrieval, but active reconstruction."""
        },
    ]

    # Write memories
    for mem in memories:
        filename = f"{mem['time']}_{mem['topic']}.md"
        file_path = notes_path / filename

        content = f"""# Experiential Note: {mem['topic'].replace('_', ' ').title()}

**Time**: 2025-10-01 {mem['time'].replace('_', ':')}
**Importance**: 0.75

---

{mem['content']}

---

*Generated during interaction - first-person experiential*
"""
        file_path.write_text(content)

    print(f"✅ Created {len(memories)} test memories in {notes_path}")

    # Initialize session and add memories to LanceDB
    print("🔧 Initializing session and populating LanceDB...")
    from abstractllm.providers.ollama_provider import OllamaProvider
    from datetime import datetime

    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )

    # Add each memory to LanceDB
    for mem in memories:
        timestamp = datetime(2025, 10, 1, int(mem['time'].split('_')[0]), 0, 0)
        note_data = {
            "id": f"note_{mem['time']}_{mem['topic']}",
            "timestamp": timestamp,
            "user_id": "test_user",
            "location": "test",
            "content": mem['content'],
            "category": "experiential",
            "importance": 0.75,
            "emotion": "curiosity",
            "emotion_intensity": 0.6,
            "emotion_valence": "positive",
            "linked_memory_ids": [],
            "tags": ["memory", "consciousness", "test"],
            "file_path": str(notes_path / f"{mem['time']}_{mem['topic']}.md"),
            "metadata": {"test": True}
        }
        if session.lancedb_storage:
            session.lancedb_storage.add_note(note_data)

    print(f"✅ Populated LanceDB with {len(memories)} memories")

    yield TEST_MEMORY_PATH

    # Cleanup after tests
    if TEST_MEMORY_PATH.exists():
        shutil.rmtree(TEST_MEMORY_PATH)
        print(f"🧹 Cleaned up test environment: {TEST_MEMORY_PATH}")


def test_1_reflect_on_shallow(setup_test_environment):
    """Test shallow reflection (5 memories, quick)."""
    print("\n" + "="*70)
    print("TEST 1: Shallow Reflection")
    print("="*70)

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )

    print("\n🔍 Triggering shallow reflection...")
    result = session.reflect_on(
        topic="memory and consciousness",
        depth="shallow"
    )

    print(f"\n📊 Reflection Results:")
    print(f"  Reflection ID: {result['reflection_id']}")
    print(f"  Memories Analyzed: {result.get('memories_analyzed', 0)}")
    print(f"  Depth: {result.get('depth')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")

    print(f"\n💡 Insights ({len(result.get('insights', []))}):")
    for i, insight in enumerate(result.get('insights', [])[:3], 1):
        print(f"  {i}. {insight}")

    print(f"\n🔄 Patterns ({len(result.get('patterns', []))}):")
    for i, pattern in enumerate(result.get('patterns', [])[:3], 1):
        print(f"  {i}. {pattern}")

    # Validate
    assert result['reflection_id'].startswith("reflection_"), "Should have reflection ID"
    assert result.get('memories_analyzed', 0) > 0, "Should analyze memories"
    assert result.get('depth') == "shallow", "Should be shallow depth"
    assert isinstance(result.get('insights', []), list), "Should have insights list"
    assert isinstance(result.get('confidence', 0), float), "Should have confidence score"

    print("\n✅ Test 1 PASSED: Shallow reflection completed")


def test_2_reflect_on_deep(setup_test_environment):
    """Test deep reflection (20 memories, comprehensive)."""
    print("\n" + "="*70)
    print("TEST 2: Deep Reflection")
    print("="*70)

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )

    print("\n🔍 Triggering deep reflection...")
    result = session.reflect_on(
        topic="memory and consciousness",
        depth="deep"
    )

    print(f"\n📊 Reflection Results:")
    print(f"  Reflection ID: {result['reflection_id']}")
    print(f"  Memories Analyzed: {result.get('memories_analyzed', 0)}")
    print(f"  Depth: {result.get('depth')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    print(f"  Should Update Core: {result.get('should_update_core', False)}")

    print(f"\n💡 Insights ({len(result.get('insights', []))}):")
    for i, insight in enumerate(result.get('insights', []), 1):
        print(f"  {i}. {insight}")

    print(f"\n🔄 Patterns ({len(result.get('patterns', []))}):")
    for i, pattern in enumerate(result.get('patterns', []), 1):
        print(f"  {i}. {pattern}")

    print(f"\n⚡ Contradictions ({len(result.get('contradictions', []))}):")
    for i, contradiction in enumerate(result.get('contradictions', []), 1):
        print(f"  {i}. {contradiction}")

    print(f"\n🌱 Evolution:")
    evolution = result.get('evolution', '')
    print(f"  {evolution[:200]}..." if len(evolution) > 200 else f"  {evolution}")

    print(f"\n❓ Unresolved ({len(result.get('unresolved', []))}):")
    for i, question in enumerate(result.get('unresolved', []), 1):
        print(f"  {i}. {question}")

    # Validate
    assert result['reflection_id'].startswith("reflection_"), "Should have reflection ID"
    assert result.get('memories_analyzed', 0) > 0, "Should analyze memories"
    assert result.get('depth') == "deep", "Should be deep depth"
    assert len(result.get('insights', [])) >= 1, "Should have at least 1 insight"
    assert isinstance(result.get('evolution', ''), str), "Should have evolution string"
    assert 0.0 <= result.get('confidence', 0) <= 1.0, "Confidence should be 0-1"

    # Check file was created
    if result.get('file_path'):
        file_path = Path(result['file_path'])
        assert file_path.exists(), f"Reflection file should exist: {file_path}"
        print(f"\n📄 Reflection saved to: {file_path}")

    print("\n✅ Test 2 PASSED: Deep reflection completed with LLM synthesis")


def test_3_reflection_insight_quality(setup_test_environment):
    """Test that LLM generates meaningful insights (not templates)."""
    print("\n" + "="*70)
    print("TEST 3: Insight Quality Validation")
    print("="*70)

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )

    print("\n🔍 Reflecting on 'consciousness'...")
    result = session.reflect_on(
        topic="consciousness",
        depth="deep"
    )

    insights = result.get('insights', [])
    patterns = result.get('patterns', [])
    evolution = result.get('evolution', '')

    print(f"\n💡 Validating insight quality...")
    print(f"  Insights count: {len(insights)}")
    print(f"  Patterns count: {len(patterns)}")
    print(f"  Evolution length: {len(evolution)} chars")

    # Quality checks
    quality_checks = []

    # Check 1: Insights are not empty
    if len(insights) > 0:
        quality_checks.append("✅ Has insights")
    else:
        quality_checks.append("❌ No insights")

    # Check 2: Insights are substantial (not just templates)
    substantial = sum(1 for insight in insights if len(insight) > 30)
    if substantial >= len(insights) * 0.5:  # At least 50% substantial
        quality_checks.append(f"✅ Insights are substantial ({substantial}/{len(insights)})")
    else:
        quality_checks.append(f"⚠️ Insights may be too short ({substantial}/{len(insights)})")

    # Check 3: Evolution narrative exists
    if len(evolution) > 50:
        quality_checks.append(f"✅ Evolution narrative exists ({len(evolution)} chars)")
    else:
        quality_checks.append(f"⚠️ Evolution narrative too short ({len(evolution)} chars)")

    # Check 4: Confidence is reasonable
    confidence = result.get('confidence', 0)
    if 0.3 <= confidence <= 0.9:
        quality_checks.append(f"✅ Confidence is reasonable ({confidence:.2f})")
    else:
        quality_checks.append(f"⚠️ Confidence might be off ({confidence:.2f})")

    print(f"\n📊 Quality Checks:")
    for check in quality_checks:
        print(f"  {check}")

    # Show sample output
    if insights:
        print(f"\n📝 Sample Insight 1:")
        print(f"  {insights[0]}")

    if len(insights) > 1:
        print(f"\n📝 Sample Insight 2:")
        print(f"  {insights[1]}")

    # Validate
    assert len(insights) > 0, "Should generate insights"
    assert sum(1 for i in insights if len(i) > 20) > 0, "At least one substantial insight"

    print("\n✅ Test 3 PASSED: Insights show LLM synthesis (not templates)")


def test_4_core_memory_integration(setup_test_environment):
    """Test that high-confidence reflections can trigger core memory updates."""
    print("\n" + "="*70)
    print("TEST 4: Core Memory Integration")
    print("="*70)

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(
        provider=provider,
        memory_base_path=TEST_MEMORY_PATH,
        default_user_id="test_user"
    )

    print("\n🔍 Reflecting with potential core memory trigger...")
    result = session.reflect_on(
        topic="memory systems",
        depth="deep"
    )

    confidence = result.get('confidence', 0)
    should_update = result.get('should_update_core', False)

    print(f"\n📊 Core Memory Integration Check:")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Should Update Core: {should_update}")
    print(f"  Insights Count: {len(result.get('insights', []))}")

    # Explain logic
    print(f"\n🔧 Update Logic:")
    print(f"  - Confidence > 0.8: {confidence > 0.8}")
    print(f"  - Insights >= 2: {len(result.get('insights', [])) >= 2}")
    print(f"  - Should Update: {should_update}")

    if should_update:
        print(f"\n✅ High confidence reflection ({confidence:.2f}) would trigger core memory update")
    else:
        print(f"\n⚠️ Confidence ({confidence:.2f}) or insights ({len(result.get('insights', []))}) insufficient for core update")

    # Validate
    assert isinstance(should_update, bool), "should_update_core should be boolean"
    assert 0.0 <= confidence <= 1.0, "Confidence should be 0-1"

    # If confidence is high, should_update_core should be True
    if confidence > 0.8 and len(result.get('insights', [])) >= 2:
        assert should_update == True, "High confidence with multiple insights should trigger update"

    print("\n✅ Test 4 PASSED: Core memory integration logic verified")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
