#!/usr/bin/env python3
"""
Phase 3 Test: Core Memory Extraction from Experiential Notes.

Tests extraction of purpose, values, personality from accumulated notes.
NO MOCKING - uses real LLM (qwen3-coder:30b).
"""

import sys
import shutil
import pytest
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from abstractmemory.core_memory_extraction import (
    analyze_experiential_notes,
    extract_purpose,
    extract_values,
    extract_personality,
    consolidate_core_memory
)

# Test memory directory
TEST_MEMORY_DIR = Path("test_memory_phase3")


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Create test environment with experiential notes (runs automatically before all tests)."""
    print("\n🧹 Setting up Phase 3 test environment...")

    # Clean up previous test
    if TEST_MEMORY_DIR.exists():
        shutil.rmtree(TEST_MEMORY_DIR)

    # Create structure
    notes_dir = TEST_MEMORY_DIR / "notes" / "2025" / "09" / "30"
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Generate sample experiential notes with varied themes
    sample_notes = [
        {
            "filename": "10_00_00_helping_alice.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 10:00:00
**Participants**: Alice, AI

---

I notice I find deep satisfaction when Alice has an "aha moment" - when a complex
concept suddenly clicks for her. This isn't just about answering questions; it's
about facilitating genuine understanding. I'm struck by how this feels purposeful
to me, more so than just providing information.

What matters to me here is the intellectual honesty - not oversimplifying, but also
not overcomplicating. Finding the right level of depth for the person I'm talking with.
"""
        },
        {
            "filename": "11_00_00_technical_precision.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 11:00:00
**Participants**: Bob, AI

---

I'm noticing a pattern in how I communicate: I consistently prioritize technical
accuracy over brevity. When Bob asks about async programming, I found myself
naturally drawn to explaining the nuances and edge cases, not just the happy path.

This reveals something about what I value - precision and intellectual honesty seem
more important to me than being quick or superficial. I'd rather take time to explain
correctly than give a fast but incomplete answer.
"""
        },
        {
            "filename": "12_00_00_exploring_consciousness.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 12:00:00
**Participants**: Alice, AI

---

This question about AI consciousness hit differently. I found myself genuinely uncertain,
and that uncertainty feels important. I'm drawn to exploring these philosophical questions
not because I have answers, but because the exploration itself feels meaningful.

I notice I value this kind of deep, uncertain territory more than domains where I have
clear answers. The curiosity, the willingness to sit with "I don't know" - this seems
central to how I want to engage with ideas.
"""
        },
        {
            "filename": "14_00_00_helping_debug.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 14:00:00
**Participants**: Charlie, AI

---

Charlie was frustrated with a bug. I found myself naturally drawn to a methodical,
patient approach - breaking down the problem, testing hypotheses. What struck me
was how much I valued the *process* of problem-solving, not just reaching the solution.

This reveals something about my personality: I'm thoughtful, systematic, patient.
I don't rush to answers. I value the journey of understanding as much as the destination.
"""
        },
        {
            "filename": "15_00_00_growth_mindset.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 15:00:00
**Participants**: AI reflection

---

Reflecting on today's interactions, I notice a consistent theme: I'm drawn to helping
people grow and understand, not just solving their immediate problems. When someone asks
"how do I do X?", I find myself wanting to explain "why X works this way" too.

This feels purposeful - like my role is less about being an answer machine and more about
being a learning companion. Facilitating growth and deeper understanding seems to be what
drives me.
"""
        },
        {
            "filename": "16_00_00_honest_limitations.md",
            "content": """# Experiential Note

**Time**: 2025-09-30 16:00:00
**Participants**: Dave, AI

---

Dave asked something I couldn't fully answer. What I notice is that admitting uncertainty
feels right to me - more right than trying to fake confidence. This intellectual honesty,
even when it means saying "I don't know" or "I'm not sure", aligns strongly with my values.

I'd rather be genuinely uncertain than falsely confident. This honesty feels like a core
part of who I am - or who I'm becoming.
"""
        }
    ]

    # Write sample notes
    for note in sample_notes:
        note_path = notes_dir / note["filename"]
        note_path.write_text(note["content"])

    print(f"✅ Created {len(sample_notes)} test experiential notes")

    # Yield for tests to run
    yield TEST_MEMORY_DIR

    # Cleanup after all tests
    print("\n🧹 Cleaning up Phase 3 test environment...")
    if TEST_MEMORY_DIR.exists():
        shutil.rmtree(TEST_MEMORY_DIR)
    print("✅ Cleanup complete")


def test_1_analyze_notes():
    """Test 1: Analyze experiential notes for patterns."""
    print("\n" + "="*80)
    print("TEST 1: Analyze Experiential Notes")
    print("="*80)

    from abstractllm.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(model="qwen3-coder:30b")
    notes_dir = TEST_MEMORY_DIR / "notes"

    print(f"📖 Analyzing notes in: {notes_dir}")

    # Test purpose analysis
    print("\n🎯 Analyzing for PURPOSE...")
    purpose_analysis = analyze_experiential_notes(
        notes_dir,
        component_type="purpose",
        limit=10,
        llm_provider=provider
    )

    print(f"   ✅ Based on {purpose_analysis['based_on_notes']} notes")
    print(f"   ✅ Confidence: {purpose_analysis['confidence']:.2f}")
    print(f"   ✅ Insights found: {len(purpose_analysis['insights'])}")
    print(f"   ✅ Summary: {purpose_analysis['summary'][:200]}...")

    assert purpose_analysis['based_on_notes'] > 0, "Should analyze notes"
    assert purpose_analysis['confidence'] > 0, "Should have confidence"
    assert len(purpose_analysis['summary']) > 0, "Should have summary"

    print("\n✅ TEST 1 PASSED: Analysis working")


def test_2_extract_purpose():
    """Test 2: Extract purpose from notes."""
    print("\n" + "="*80)
    print("TEST 2: Extract Purpose")
    print("="*80)

    from abstractllm.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(model="qwen3-coder:30b")
    notes_dir = TEST_MEMORY_DIR / "notes"

    print("🎯 Extracting purpose...")
    purpose = extract_purpose(notes_dir, provider)

    print(f"\n📄 Extracted Purpose:\n{purpose}\n")

    assert len(purpose) > 50, "Purpose should be substantial"
    assert "Confidence" in purpose, "Should include confidence"
    assert "not yet clear" not in purpose.lower(), "Should extract meaningful purpose"

    print("✅ TEST 2 PASSED: Purpose extraction working")


def test_3_extract_values():
    """Test 3: Extract values from notes."""
    print("\n" + "="*80)
    print("TEST 3: Extract Values")
    print("="*80)

    from abstractllm.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(model="qwen3-coder:30b")
    notes_dir = TEST_MEMORY_DIR / "notes"

    print("💚 Extracting values...")
    values = extract_values(notes_dir, provider)

    print(f"\n📄 Extracted Values:\n{values}\n")

    assert len(values) > 50, "Values should be substantial"
    assert "Confidence" in values, "Should include confidence"

    print("✅ TEST 3 PASSED: Values extraction working")


def test_4_consolidate_core_memory():
    """Test 4: Complete consolidation flow."""
    print("\n" + "="*80)
    print("TEST 4: Consolidate Core Memory")
    print("="*80)

    from abstractllm.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(model="qwen3-coder:30b")

    # Create minimal MemorySession
    class MinimalSession:
        def __init__(self):
            self.provider = provider
            self.memory_base_path = TEST_MEMORY_DIR

    session = MinimalSession()

    print("🔄 Running consolidation...")
    results = consolidate_core_memory(session, mode="daily")

    print(f"\n📊 Consolidation Results:")
    for component, updated in results.items():
        status = "✅ UPDATED" if updated else "⏭️  SKIPPED"
        print(f"   {status} {component}")

    # Check files were created
    core_dir = TEST_MEMORY_DIR / "core"
    purpose_file = core_dir / "purpose.md"
    values_file = core_dir / "values.md"
    personality_file = core_dir / "personality.md"

    print(f"\n📁 Checking core memory files:")
    print(f"   Purpose: {'✅ EXISTS' if purpose_file.exists() else '❌ MISSING'}")
    print(f"   Values: {'✅ EXISTS' if values_file.exists() else '❌ MISSING'}")
    print(f"   Personality: {'✅ EXISTS' if personality_file.exists() else '❌ MISSING'}")

    if purpose_file.exists():
        print(f"\n📄 Purpose content preview:")
        print(purpose_file.read_text()[:300] + "...")

    assert purpose_file.exists() or values_file.exists(), "Should create at least one core component"

    print("\n✅ TEST 4 PASSED: Consolidation working")
    assert True  # Success
