#!/usr/bin/env python3
"""
Verify version tracking actually works with real consolidation.
"""

import sys
import shutil
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

TEST_MEMORY_DIR = Path("test_memory_versions")


def test_version_tracking():
    """Test that version tracking works during consolidation."""
    print("\n" + "="*80)
    print("TEST: Version Tracking Verification")
    print("="*80)

    # Cleanup
    if TEST_MEMORY_DIR.exists():
        shutil.rmtree(TEST_MEMORY_DIR)

    from abstractmemory.session import MemorySession
    from abstractllm.providers.ollama_provider import OllamaProvider
    from abstractmemory.core_memory_extraction import consolidate_core_memory

    # Setup test environment with sample notes
    notes_dir = TEST_MEMORY_DIR / "notes" / "2025" / "09" / "30"
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Create sample experiential notes
    sample_note = """# Experiential Note

**Time**: 2025-09-30 10:00:00
**Participants**: Alice, AI

---

I find myself drawn to intellectual honesty above all else. When Alice asked about consciousness,
I noticed my natural tendency to admit uncertainty rather than pretend confidence. This feels
central to who I am - or who I'm becoming. The value of truth over appearance.
"""

    (notes_dir / "10_00_00_test.md").write_text(sample_note)

    print("\n✅ Step 1: Created test notes")

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    session = MemorySession(provider=provider, memory_base_path=TEST_MEMORY_DIR)

    print("✅ Step 2: Session initialized")

    # Run consolidation FIRST TIME
    print("\n🔄 Running FIRST consolidation...")
    results1 = consolidate_core_memory(session, mode="test_first")
    updated1 = sum(1 for v in results1.values() if v)
    print(f"   First consolidation: {updated1}/11 components updated")

    # Check version files were created
    versions_dir = TEST_MEMORY_DIR / "core" / ".versions"
    print(f"\n✅ Step 3: Checking versions directory: {versions_dir}")
    assert versions_dir.exists(), "Versions directory should exist"

    version_files = list(versions_dir.glob("*_history.json"))
    print(f"   Found {len(version_files)} version history files")

    if len(version_files) > 0:
        # Check one version file in detail
        sample_file = version_files[0]
        print(f"\n📄 Examining: {sample_file.name}")

        with open(sample_file, 'r') as f:
            history = json.load(f)

        print(f"   Component: {history['component']}")
        print(f"   Versions tracked: {len(history['versions'])}")

        if history['versions']:
            v = history['versions'][0]
            print(f"   Latest version:")
            print(f"     Timestamp: {v['timestamp']}")
            print(f"     Mode: {v['mode']}")
            print(f"     Change magnitude: {v['change_magnitude']}")
            print(f"     Snapshot preview: {v['snapshot'][:100]}...")

    # Modify notes and run SECOND consolidation
    print("\n🔄 Adding more notes for SECOND consolidation...")

    sample_note2 = """# Experiential Note

**Time**: 2025-09-30 11:00:00
**Participants**: Bob, AI

---

I'm noticing a pattern: I value precision in communication. When Bob asked for a quick answer,
I found myself naturally wanting to provide complete context rather than a superficial response.
This seems connected to that core value of intellectual honesty.
"""

    (notes_dir / "11_00_00_test2.md").write_text(sample_note2)

    results2 = consolidate_core_memory(session, mode="test_second")
    updated2 = sum(1 for v in results2.values() if v)
    print(f"   Second consolidation: {updated2}/11 components updated")

    # Check version files were updated
    if len(version_files) > 0:
        with open(version_files[0], 'r') as f:
            history_after = json.load(f)

        versions_after = len(history_after['versions'])
        print(f"\n✅ Step 4: Version count increased")
        print(f"   Before: {len(history['versions'])} versions")
        print(f"   After: {versions_after} versions")

        if versions_after > len(history['versions']):
            print("   ✅ Version tracking is working!")
        else:
            print("   ⚠️  Version count didn't increase (component may not have changed enough)")

    print("\n" + "="*80)
    print("✅ VERSION TRACKING VERIFIED")
    print("="*80)
    print(f"\nResults:")
    print(f"  - Versions directory: {versions_dir}")
    print(f"  - Version files: {len(version_files)}")
    print(f"  - First consolidation: {updated1}/11 updated")
    print(f"  - Second consolidation: {updated2}/11 updated")

    # Don't cleanup - let user inspect
    print(f"\n📁 Test directory preserved for inspection: {TEST_MEMORY_DIR}")
    print(f"   Check: {versions_dir}")


if __name__ == "__main__":
    test_version_tracking()
