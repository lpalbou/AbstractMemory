"""
Test Phase 1 Improvements - Session Continuity & Full Reconstruction

Tests for critical fixes:
1. Session metadata persistence across relaunches
2. Full reconstruct_context() usage in chat()
3. Verbatim indexing (when enabled)
4. current_context.md updates every interaction

Run with:
    .venv/bin/python -m pytest tests/test_phase1_improvements.py -v -s
"""

import pytest
from pathlib import Path
import shutil
import json
from datetime import datetime
from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider


# Test fixtures
@pytest.fixture(scope="module")
def test_memory_path():
    """Create temporary test memory directory."""
    path = Path("test_phase1_memory")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    # Cleanup after all tests
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(scope="module")
def ollama_provider():
    """Initialize Ollama provider."""
    return OllamaProvider(model="qwen3-coder:30b")


def test_1_session_metadata_persistence(test_memory_path, ollama_provider):
    """
    Test that session metadata persists across relaunches.

    BEFORE FIX: interactions_count=0 after relaunch
    AFTER FIX: interactions_count restored from .session_metadata.json
    """
    print("\n" + "="*60)
    print("TEST 1: Session Metadata Persistence")
    print("="*60)

    # Session 1: Create and interact
    print("\n📝 Session 1: Creating and interacting...")
    session1 = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="alice"
    )

    # Should start at 0 (first time)
    assert session1.interactions_count == 0, "Fresh session should start at 0"

    # Interact twice
    session1.chat("Hello, I'm testing memory persistence", user_id="alice")
    assert session1.interactions_count == 1

    session1.chat("This is my second message", user_id="alice")
    assert session1.interactions_count == 2
    assert session1.memories_created == 2

    print(f"✅ Session 1: {session1.interactions_count} interactions, {session1.memories_created} memories")

    # Check metadata file was created
    metadata_path = test_memory_path / ".session_metadata.json"
    assert metadata_path.exists(), "Metadata file should exist"

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    assert metadata["total_interactions"] == 2
    assert metadata["total_memories"] == 2
    print(f"✅ Metadata file created: {metadata['total_interactions']} interactions")

    # Session 2: Relaunch (simulate REPL restart)
    print("\n🔄 Session 2: Relaunching (simulating REPL restart)...")
    session2 = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="alice"
    )

    # CRITICAL: Should restore from metadata, NOT reset to 0
    assert session2.interactions_count == 2, "Session 2 should restore counter from metadata"
    assert session2.memories_created == 2, "Session 2 should restore memories count"
    print(f"✅ Session 2 restored: {session2.interactions_count} interactions (continuity preserved!)")

    # Continue interacting in session 2
    session2.chat("Third message in session 2", user_id="alice")
    assert session2.interactions_count == 3
    assert session2.memories_created == 3

    print(f"✅ Session 2 after interaction: {session2.interactions_count} interactions")

    # Session 3: One more relaunch to verify
    print("\n🔄 Session 3: Final relaunch check...")
    session3 = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="alice"
    )

    assert session3.interactions_count == 3, "Session 3 should restore 3 interactions"
    print(f"✅ Session 3 restored: {session3.interactions_count} interactions")

    print("\n✅ TEST 1 PASSED: Session continuity works across relaunches!")


def test_2_reconstruct_context_usage(test_memory_path, ollama_provider):
    """
    Test that chat() uses full reconstruct_context() instead of basic context.

    BEFORE FIX: Used _basic_context_reconstruction() (5-line context)
    AFTER FIX: Uses reconstruct_context() (9-step rich context)
    """
    print("\n" + "="*60)
    print("TEST 2: Full reconstruct_context() Usage")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="bob"
    )

    # First interaction to create some memory
    print("\n📝 Creating initial memory...")
    session.chat("Memory is the foundation of consciousness", user_id="bob")

    # Second interaction - should trigger reconstruction
    print("\n🔍 Second interaction (should reconstruct context)...")
    initial_reconstructions = session.reconstructions_performed

    session.chat("Tell me more about memory and consciousness", user_id="bob")

    # CRITICAL: reconstructions_performed should increment
    assert session.reconstructions_performed > initial_reconstructions, \
        "Reconstruction should have been performed"

    print(f"✅ Reconstructions performed: {session.reconstructions_performed}")
    print("✅ TEST 2 PASSED: Full reconstruction is being used!")


def test_3_verbatim_indexing_disabled(test_memory_path, ollama_provider):
    """
    Test verbatim indexing when disabled (default).

    BEFORE FIX: Verbatims never indexed
    AFTER FIX: Verbatims only indexed if index_verbatims=True
    """
    print("\n" + "="*60)
    print("TEST 3: Verbatim Indexing (Disabled)")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="charlie",
        index_verbatims=False  # Explicitly disabled
    )

    print("\n📝 Interacting with index_verbatims=False...")
    session.chat("Test verbatim indexing", user_id="charlie")

    # Check LanceDB - should NOT have verbatim table
    if session.lancedb_storage:
        tables = session.lancedb_storage.db.table_names()
        print(f"📊 LanceDB tables: {tables}")

        # Should have notes but NOT verbatim
        assert "notes" in tables, "Notes should be indexed"
        assert "verbatim" not in tables, "Verbatim should NOT be indexed when disabled"

    print("✅ TEST 3 PASSED: Verbatim indexing correctly disabled!")


def test_4_verbatim_indexing_enabled(test_memory_path, ollama_provider):
    """
    Test verbatim indexing when enabled.

    New functionality: Verbatims indexed in LanceDB when index_verbatims=True
    """
    print("\n" + "="*60)
    print("TEST 4: Verbatim Indexing (Enabled)")
    print("="*60)

    # Create new session with indexing enabled
    enabled_path = test_memory_path / "verbatim_enabled"
    enabled_path.mkdir(exist_ok=True)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=enabled_path,
        default_user_id="dave",
        index_verbatims=True  # Explicitly enabled
    )

    print("\n📝 Interacting with index_verbatims=True...")
    session.chat("This verbatim should be indexed", user_id="dave")

    # Check LanceDB - should have verbatim table
    if session.lancedb_storage:
        tables = session.lancedb_storage.db.table_names()
        print(f"📊 LanceDB tables: {tables}")

        # Should have both notes AND verbatim
        assert "notes" in tables, "Notes should be indexed"
        assert "verbatim" in tables, "Verbatim SHOULD be indexed when enabled"

        # Verify verbatim record exists
        verbatim_table = session.lancedb_storage.db.open_table("verbatim")
        records = verbatim_table.to_pandas()
        assert len(records) > 0, "At least one verbatim should be indexed"
        assert "This verbatim should be indexed" in records.iloc[0]["user_input"]

        print(f"✅ Verbatim records: {len(records)}")

    print("✅ TEST 4 PASSED: Verbatim indexing works when enabled!")


def test_5_current_context_updates(test_memory_path, ollama_provider):
    """
    Test that current_context.md updates with EVERY interaction.

    BEFORE FIX: Only updated once at beginning
    AFTER FIX: Updates every interaction with full context
    """
    print("\n" + "="*60)
    print("TEST 5: current_context.md Updates")
    print("="*60)

    context_path = test_memory_path / "context_test"
    context_path.mkdir(exist_ok=True)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=context_path,
        default_user_id="eve"
    )

    current_context_file = context_path / "working" / "current_context.md"

    # First interaction
    print("\n📝 Interaction 1...")
    session.chat("First question about memory", user_id="eve")

    assert current_context_file.exists(), "current_context.md should exist"
    content1 = current_context_file.read_text()
    assert "First question about memory" in content1, "First query should be in context"
    print(f"✅ Context file updated (length: {len(content1)} chars)")

    # Second interaction - context should UPDATE (not stay the same)
    print("\n📝 Interaction 2...")
    session.chat("Second question about consciousness", user_id="eve")

    content2 = current_context_file.read_text()
    assert "Second question about consciousness" in content2, "Second query should be in context"
    assert content2 != content1, "Context should have changed"
    print(f"✅ Context file updated again (length: {len(content2)} chars)")

    # Third interaction
    print("\n📝 Interaction 3...")
    session.chat("Third question about identity", user_id="eve")

    content3 = current_context_file.read_text()
    assert "Third question about identity" in content3, "Third query should be in context"
    assert content3 != content2, "Context should have changed again"
    print(f"✅ Context file updated third time (length: {len(content3)} chars)")

    # Verify content has emotional context (Phase 1 enhancement)
    assert "**Emotional Context**" in content3, "Should include emotional context"
    print("✅ Context includes emotional metadata")

    print("\n✅ TEST 5 PASSED: current_context.md updates every interaction!")


def test_6_session_history_tracking(test_memory_path, ollama_provider):
    """
    Test that session metadata tracks multiple sessions.
    """
    print("\n" + "="*60)
    print("TEST 6: Session History Tracking")
    print("="*60)

    history_path = test_memory_path / "session_history"
    history_path.mkdir(exist_ok=True)

    # Session 1
    print("\n📝 Session 1...")
    session1 = MemorySession(
        provider=ollama_provider,
        memory_base_path=history_path,
        default_user_id="frank"
    )
    session1.chat("Session 1 message", user_id="frank")
    session1_id = session1.session_id

    # Session 2
    print("\n📝 Session 2...")
    session2 = MemorySession(
        provider=ollama_provider,
        memory_base_path=history_path,
        default_user_id="frank"
    )
    session2.chat("Session 2 message", user_id="frank")
    session2_id = session2.session_id

    # Check metadata has both sessions
    metadata_path = history_path / ".session_metadata.json"
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    sessions = metadata.get("sessions", [])
    session_ids = [s["session_id"] for s in sessions]

    print(f"📊 Sessions tracked: {len(sessions)}")
    print(f"   Session IDs: {session_ids}")

    assert session1_id in session_ids, "Session 1 should be in history"
    assert session2_id in session_ids, "Session 2 should be in history"
    assert len(sessions) == 2, "Should have exactly 2 sessions"

    print("✅ TEST 6 PASSED: Session history tracking works!")


if __name__ == "__main__":
    """Run tests directly."""
    print("\n" + "="*60)
    print("PHASE 1 IMPROVEMENTS - TEST SUITE")
    print("="*60)
    print("\nRunning all Phase 1 tests with real Ollama LLM...")
    print("This will take 3-5 minutes.\n")

    pytest.main([__file__, "-v", "-s"])
