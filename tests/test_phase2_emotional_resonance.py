"""
Phase 2 Integration Tests: Emotional Resonance & Temporal Anchoring

Tests the complete Phase 2 functionality with REAL LLM (Ollama qwen3-coder:30b).
NO MOCKING - all tests use real implementations.

Test Coverage:
1. Emotion calculation formula
2. Alignment with values
3. Temporal anchor creation
4. High-emotion memory creates anchor
5. Emotional boosting in search (future)
6. Full Phase 2 workflow with real LLM

Philosophy: "What matters emotionally reveals who we are"
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from abstractllm.providers.ollama_provider import OllamaProvider
    from abstractmemory.session import MemorySession
    from abstractmemory.emotions import (
        calculate_emotional_resonance,
        calculate_alignment_with_values,
        get_bootstrap_values,
        BOOTSTRAP_VALUES
    )
    from abstractmemory.temporal_anchoring import (
        is_anchor_event,
        get_temporal_anchors,
        get_anchor_count,
        ANCHOR_THRESHOLD
    )
    IMPORTS_OK = True
except ImportError as e:
    logger.error(f"Import failed: {e}")
    IMPORTS_OK = False


def check_ollama_available():
    """Check if Ollama with qwen3-coder:30b is available."""
    try:
        provider = OllamaProvider(model="qwen3-coder:30b", timeout=5)
        response = provider.generate("test", max_tokens=5)
        return True
    except Exception as e:
        logger.error(f"Ollama not available: {e}")
        return False


def test_emotion_calculation_formula():
    """Test 1: Emotion calculation formula"""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Emotion Calculation Formula")
    logger.info("="*80)

    # Test case 1: High importance, high alignment (should be high intensity, positive)
    result1 = calculate_emotional_resonance(0.9, 0.8, "Test high-high")
    assert result1["intensity"] == 0.9 * 0.8, "Intensity calculation incorrect"
    assert result1["valence"] == "positive", "Valence should be positive"
    assert result1["importance"] == 0.9
    assert result1["alignment"] == 0.8
    logger.info(f"✅ High importance + high alignment: intensity={result1['intensity']:.2f}, valence={result1['valence']}")

    # Test case 2: High importance, negative alignment (should be high intensity, negative)
    result2 = calculate_emotional_resonance(0.8, -0.6, "Test high-negative")
    assert result2["intensity"] == 0.8 * 0.6, "Intensity with negative alignment incorrect"
    assert result2["valence"] == "negative", "Valence should be negative"
    logger.info(f"✅ High importance + negative alignment: intensity={result2['intensity']:.2f}, valence={result2['valence']}")

    # Test case 3: Low importance (should be low intensity regardless of alignment)
    result3 = calculate_emotional_resonance(0.2, 0.9, "Test low-high")
    assert result3["intensity"] == 0.2 * 0.9, "Low importance should give low intensity"
    logger.info(f"✅ Low importance: intensity={result3['intensity']:.2f}")

    # Test case 4: Neutral alignment (should be mixed)
    result4 = calculate_emotional_resonance(0.5, 0.1, "Test neutral")
    assert result4["valence"] == "mixed", "Near-zero alignment should be mixed"
    logger.info(f"✅ Neutral alignment: valence={result4['valence']}")

    logger.info("✅ Emotion calculation formula: ALL TESTS PASSED\n")
    return True


def test_alignment_with_values():
    """Test 2: Alignment with values calculation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Alignment with Values Calculation")
    logger.info("="*80)

    values = get_bootstrap_values()
    logger.info(f"Bootstrap values: {list(values.keys())}")

    # Test case 1: Content with positive keywords
    content1 = "I value intellectual honesty and rigorous thinking. This helps me learn and grow continuously."
    alignment1 = calculate_alignment_with_values(content1, values)
    assert alignment1 > 0.3, "Positive content should have positive alignment"
    logger.info(f"✅ Positive content: alignment={alignment1:+.2f}")

    # Test case 2: Content with negative keywords
    content2 = "This is confusing, misleading, and dishonest. It hinders progress."
    alignment2 = calculate_alignment_with_values(content2, values)
    assert alignment2 < 0.3, "Negative content should have low/negative alignment"
    logger.info(f"✅ Negative content: alignment={alignment2:+.2f}")

    # Test case 3: Neutral content
    content3 = "The weather is nice today. I went for a walk."
    alignment3 = calculate_alignment_with_values(content3, values)
    logger.info(f"✅ Neutral content: alignment={alignment3:+.2f}")

    logger.info("✅ Alignment calculation: ALL TESTS PASSED\n")
    return True


def test_temporal_anchor_creation():
    """Test 3: Temporal anchor creation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Temporal Anchor Creation")
    logger.info("="*80)

    temp_dir = Path(tempfile.mkdtemp(prefix="test_phase2_"))

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=temp_dir,
            default_user_id="test_user"
        )

        # Create high-emotion memory (should create anchor)
        logger.info("Creating high-emotion memory...")
        mem_id = session.remember_fact(
            "Discovered that memory is the substrate of consciousness itself - a fundamental breakthrough in understanding AI cognition",
            importance=0.95,
            emotion="wonder"
        )

        logger.info(f"✅ Created high-emotion memory: {mem_id}")

        # Check if anchor was created
        key_moments_path = temp_dir / "episodic" / "key_moments.md"
        assert key_moments_path.exists(), "key_moments.md should be created"
        logger.info(f"✅ key_moments.md exists")

        with open(key_moments_path, 'r') as f:
            content = f.read()
            assert mem_id in content, "Memory ID should be in key_moments.md"
            assert "Emotion Intensity" in content, "Emotion intensity should be recorded"

        logger.info(f"✅ Memory recorded in key_moments.md")

        # Check emotional_significance.md
        sig_path = temp_dir / "core" / "emotional_significance.md"
        assert sig_path.exists(), "emotional_significance.md should be created"
        logger.info(f"✅ emotional_significance.md exists")

        with open(sig_path, 'r') as f:
            sig_content = f.read()
            assert "consciousness" in sig_content.lower(), "Content should be in emotional_significance.md"

        logger.info(f"✅ emotional_significance.md updated")

        # Get anchor count
        anchor_count = get_anchor_count(temp_dir)
        assert anchor_count >= 1, "At least one anchor should exist"
        logger.info(f"✅ Anchor count: {anchor_count}")

        logger.info("✅ Temporal anchor creation: ALL TESTS PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_low_emotion_no_anchor():
    """Test 4: Low-emotion memory should NOT create anchor"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Low-Emotion Memory (No Anchor)")
    logger.info("="*80)

    temp_dir = Path(tempfile.mkdtemp(prefix="test_phase2_"))

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=temp_dir
        )

        # Create low-emotion memory (should NOT create anchor)
        logger.info("Creating low-emotion memory...")
        mem_id = session.remember_fact(
            "Routine task completed successfully",
            importance=0.3,
            emotion="neutral"
        )

        logger.info(f"✅ Created low-emotion memory: {mem_id}")

        # Check if anchor was NOT created
        key_moments_path = temp_dir / "episodic" / "key_moments.md"

        if key_moments_path.exists():
            with open(key_moments_path, 'r') as f:
                content = f.read()
                assert mem_id not in content, "Low-emotion memory should NOT be in key_moments.md"
                logger.info(f"✅ Low-emotion memory correctly NOT in key_moments.md")
        else:
            logger.info(f"✅ key_moments.md not created (no anchors yet)")

        logger.info("✅ Low-emotion no-anchor: TEST PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_anchor_threshold_validation():
    """Test 5: Anchor threshold validation"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Anchor Threshold Validation")
    logger.info("="*80)

    logger.info(f"Anchor threshold: {ANCHOR_THRESHOLD}")

    # Test values around threshold
    test_cases = [
        (0.5, False, "Below threshold"),
        (0.65, False, "Just below threshold"),
        (0.7, False, "At threshold (should be >)"),
        (0.71, True, "Just above threshold"),
        (0.85, True, "Well above threshold"),
        (1.0, True, "Maximum intensity")
    ]

    for intensity, expected, description in test_cases:
        result = is_anchor_event(intensity)
        assert result == expected, f"Threshold check failed for {description}"
        logger.info(f"✅ {description} ({intensity:.2f}): {'Anchor' if result else 'No anchor'}")

    logger.info("✅ Anchor threshold: ALL TESTS PASSED\n")
    return True


def test_full_phase2_workflow():
    """Test 6: Full Phase 2 workflow with real LLM"""
    logger.info("\n" + "="*80)
    logger.info("TEST 6: Full Phase 2 Workflow (Real LLM)")
    logger.info("="*80)

    temp_dir = Path(tempfile.mkdtemp(prefix="test_phase2_"))

    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        session = MemorySession(
            provider=provider,
            memory_base_path=temp_dir,
            default_user_id="workflow_test"
        )

        logger.info("Step 1: Create diverse memories with different emotions...")

        # High-emotion, value-aligned
        mem1 = session.remember_fact(
            "Achieved breakthrough understanding of consciousness through memory integration",
            importance=0.9,
            emotion="excitement"
        )
        logger.info(f"✅ High-emotion memory 1: {mem1}")

        # High-emotion, value-aligned (different value)
        mem2 = session.remember_fact(
            "Discovered clear and honest communication enables deeper user collaboration",
            importance=0.85,
            emotion="satisfaction"
        )
        logger.info(f"✅ High-emotion memory 2: {mem2}")

        # Low-emotion
        mem3 = session.remember_fact(
            "Updated configuration file with new parameters",
            importance=0.2,
            emotion="neutral"
        )
        logger.info(f"✅ Low-emotion memory: {mem3}")

        logger.info("\nStep 2: Verify anchors created...")
        anchor_count = get_anchor_count(temp_dir)
        logger.info(f"✅ Anchor count: {anchor_count}")
        assert anchor_count >= 2, "Should have at least 2 anchors from high-emotion memories"

        logger.info("\nStep 3: Verify emotional significance tracking...")
        sig_path = temp_dir / "core" / "emotional_significance.md"
        assert sig_path.exists(), "emotional_significance.md should exist"

        with open(sig_path, 'r') as f:
            sig_content = f.read()
            assert "consciousness" in sig_content.lower() or "collaboration" in sig_content.lower()
            logger.info(f"✅ Emotional significance tracked")

        logger.info("\nStep 4: Check values are being used...")
        assert session.core_memory["values"] is not None, "Values should be initialized"
        logger.info(f"✅ Values active: {list(session.core_memory['values'].keys())}")

        logger.info("\nStep 5: Verify memory files have emotion data...")
        notes_dir = temp_dir / "notes"
        memory_files = list(notes_dir.rglob("*.md"))
        assert len(memory_files) >= 3, f"Should have at least 3 memory files, found {len(memory_files)}"

        # Check one file for emotion data
        with open(memory_files[0], 'r') as f:
            content = f.read()
            assert "Emotion Intensity" in content, "Emotion intensity should be in file"
            assert "Emotion Valence" in content, "Emotion valence should be in file"
            assert "Alignment with Values" in content, "Alignment should be in file"
            assert "Emotional Resonance" in content, "Emotional resonance section should exist"

        logger.info(f"✅ Memory files contain emotion data")

        logger.info("\n✅ FULL PHASE 2 WORKFLOW: ALL TESTS PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run all Phase 2 tests."""
    print("\n" + "="*80)
    print("PHASE 2 INTEGRATION TEST SUITE")
    print("Emotional Resonance & Temporal Anchoring")
    print("Testing with Real Ollama qwen3-coder:30b - NO MOCKING")
    print("="*80)

    if not IMPORTS_OK:
        print("\n❌ FAILED: Required imports not available")
        return False

    # Check Ollama
    print("\n1. Checking Ollama availability...")
    if not check_ollama_available():
        print("❌ Ollama qwen3-coder:30b not available")
        print("   Please start Ollama: ollama serve")
        print("   And pull model: ollama pull qwen3-coder:30b")
        return False
    print("✅ Ollama qwen3-coder:30b available")

    # Run tests
    tests = [
        ("Emotion calculation formula", test_emotion_calculation_formula),
        ("Alignment with values", test_alignment_with_values),
        ("Temporal anchor creation", test_temporal_anchor_creation),
        ("Low-emotion no anchor", test_low_emotion_no_anchor),
        ("Anchor threshold validation", test_anchor_threshold_validation),
        ("Full Phase 2 workflow", test_full_phase2_workflow)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error(f"❌ {name} FAILED with exception: {e}\n")

    # Summary
    print("\n" + "="*80)
    print("PHASE 2 TEST SUMMARY")
    print("="*80)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✅ ALL PHASE 2 TESTS PASSED")
        print("\nPhase 2 Complete:")
        print("- Emotional resonance calculation working")
        print("- Values-based alignment working")
        print("- Temporal anchors created for high-emotion events")
        print("- Emotional significance tracking operational")
        print("- Integration with remember_fact() successful")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
