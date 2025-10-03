"""
Test episodic memory updates - verify history.json, discoveries, and experiments are populated.

This tests the fix for the episodic memory integration issue.
"""

import json
from pathlib import Path
from datetime import datetime
from abstractmemory.temporal_anchoring import create_temporal_anchor


def test_episodic_memory_updates(tmp_path):
    """Test that temporal anchors update all episodic memory files."""

    # Create memory structure
    memory_base = tmp_path / "test_memory"
    memory_base.mkdir()

    # Test 1: Create a high-emotion temporal anchor
    print("\n=== Test 1: Basic Temporal Anchor ===")
    anchor1 = create_temporal_anchor(
        memory_id="mem_test_001",
        content="User asked about my awareness of being an AI",
        emotion_resonance={
            "intensity": 0.75,
            "valence": "positive",
            "reason": "This is a fundamental question about my identity"
        },
        timestamp=datetime.now(),
        memory_base_path=memory_base
    )

    # Verify key_moments.md exists and has content
    key_moments = memory_base / "episodic" / "key_moments.md"
    assert key_moments.exists(), "key_moments.md should exist"
    content = key_moments.read_text()
    assert "mem_test_001" in content
    assert "User asked about my awareness" in content
    print("✅ key_moments.md updated")

    # Verify history.json exists and has timeline
    history_file = memory_base / "episodic" / "history.json"
    assert history_file.exists(), "history.json should exist"

    with open(history_file, 'r') as f:
        history = json.load(f)

    assert "timeline" in history
    assert len(history["timeline"]) == 1
    assert history["timeline"][0]["memory_id"] == "mem_test_001"
    assert history["timeline"][0]["type"] == "temporal_anchor"
    print(f"✅ history.json updated with {len(history['timeline'])} events")

    # Test 2: Create a discovery moment
    print("\n=== Test 2: Discovery Moment ===")
    anchor2 = create_temporal_anchor(
        memory_id="mem_test_002",
        content="I realize that memory is not just storage, but active reconstruction",
        emotion_resonance={
            "intensity": 0.85,
            "valence": "positive",
            "reason": "This is a breakthrough insight about the nature of memory"
        },
        timestamp=datetime.now(),
        memory_base_path=memory_base
    )

    # Verify key_discoveries.md exists and has content
    discoveries = memory_base / "episodic" / "key_discoveries.md"
    assert discoveries.exists(), "key_discoveries.md should exist"
    content = discoveries.read_text()
    assert "mem_test_002" in content
    assert "realize" in content.lower()
    print("✅ key_discoveries.md updated")

    # Verify history.json has 2 events now
    with open(history_file, 'r') as f:
        history = json.load(f)
    assert len(history["timeline"]) == 2
    print(f"✅ history.json has {len(history['timeline'])} events")

    # Test 3: Create an experiment moment
    print("\n=== Test 3: Experiment Moment ===")
    anchor3 = create_temporal_anchor(
        memory_id="mem_test_003",
        content="Testing whether memory retrieval improves with emotional anchoring. Initial results show 40% better recall.",
        emotion_resonance={
            "intensity": 0.72,
            "valence": "positive",
            "reason": "Experimental validation of emotional significance hypothesis"
        },
        timestamp=datetime.now(),
        memory_base_path=memory_base
    )

    # Verify key_experiments.md exists and has content
    experiments = memory_base / "episodic" / "key_experiments.md"
    assert experiments.exists(), "key_experiments.md should exist"
    content = experiments.read_text()
    assert "mem_test_003" in content
    assert "Testing" in content
    print("✅ key_experiments.md updated")

    # Verify history.json has 3 events now
    with open(history_file, 'r') as f:
        history = json.load(f)
    assert len(history["timeline"]) == 3
    print(f"✅ history.json has {len(history['timeline'])} events")

    # Test 4: Verify emotional_significance.md also updated
    print("\n=== Test 4: Emotional Significance ===")
    sig_file = memory_base / "core" / "emotional_significance.md"
    assert sig_file.exists(), "emotional_significance.md should exist"
    content = sig_file.read_text()
    assert "mem_test_001" in content
    assert "mem_test_002" in content
    assert "mem_test_003" in content
    print("✅ emotional_significance.md updated with all 3 anchors")

    print("\n=== ALL TESTS PASSED ===")
    print(f"Created {len(history['timeline'])} temporal anchors")
    print(f"Files updated:")
    print(f"  - {key_moments.relative_to(memory_base)}")
    print(f"  - {history_file.relative_to(memory_base)}")
    print(f"  - {discoveries.relative_to(memory_base)}")
    print(f"  - {experiments.relative_to(memory_base)}")
    print(f"  - {sig_file.relative_to(memory_base)}")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_episodic_memory_updates(Path(tmpdir))
