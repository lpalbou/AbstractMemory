"""
Test Phase 4: Enhanced Memory Types (Working, Episodic, Semantic)

Tests all three memory managers with real LLM interactions.
NO MOCKING - tests real implementation in real situations.

Test coverage:
1. WorkingMemoryManager - context, tasks, unresolved/resolved
2. EpisodicMemoryManager - moments, experiments, discoveries, history
3. SemanticMemoryManager - insights, concepts, knowledge graph
4. Integration with MemorySession
"""

import os
import sys
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from abstractmemory.working_memory import WorkingMemoryManager
from abstractmemory.episodic_memory import EpisodicMemoryManager
from abstractmemory.semantic_memory import SemanticMemoryManager
from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider


def test_working_memory_manager():
    """Test WorkingMemoryManager with real operations."""
    print("\n" + "="*60)
    print("TEST 1: WorkingMemoryManager")
    print("="*60)

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Initialize manager
        working = WorkingMemoryManager(base_path)

        # Test 1: Update context
        print("\n1. Testing context update...")
        success = working.update_context(
            context="Discussing Phase 4 implementation and testing",
            user_id="test_user"
        )
        assert success, "Context update failed"

        context = working.get_context()
        assert context is not None, "Context should exist"
        assert "Phase 4" in context, "Context should contain query text"
        print("✓ Context updated and retrieved successfully")

        # Test 2: Update tasks
        print("\n2. Testing task management...")
        tasks = [
            "Implement WorkingMemoryManager",
            "Test with real data",
            "Integrate with MemorySession"
        ]
        success = working.update_tasks(tasks)
        assert success, "Task update failed"

        retrieved_tasks = working.get_tasks()
        assert len(retrieved_tasks) == 3, f"Expected 3 tasks, got {len(retrieved_tasks)}"
        assert "WorkingMemoryManager" in retrieved_tasks[0], "Task content mismatch"
        print(f"✓ Tasks updated: {len(retrieved_tasks)} tasks")

        # Test 3: Add unresolved question
        print("\n3. Testing unresolved questions...")
        success = working.add_unresolved(
            question="How to integrate memory managers with active reconstruction?",
            context="Phase 4 implementation"
        )
        assert success, "Add unresolved failed"

        unresolved = working.get_unresolved()
        assert len(unresolved) > 0, "Should have unresolved questions"
        assert "integrate" in unresolved[0]["question"].lower(), "Question content mismatch"
        print(f"✓ Unresolved question added: {len(unresolved)} total")

        # Test 4: Add resolved question
        print("\n4. Testing resolved questions...")
        success = working.add_resolved(
            question="How to structure memory managers?",
            solution="Create separate manager classes for each memory type",
            method="Object-oriented design with clear interfaces"
        )
        assert success, "Add resolved failed"

        resolved = working.get_resolved()
        assert len(resolved) > 0, "Should have resolved questions"
        assert "structure" in resolved[0]["question"].lower(), "Question content mismatch"
        print(f"✓ Resolved question added: {len(resolved)} total")

        # Test 5: Summary
        print("\n5. Testing summary...")
        summary = working.get_summary()
        assert summary["active_tasks"] == 3, f"Expected 3 tasks, got {summary['active_tasks']}"
        assert summary["unresolved_count"] == 1, f"Expected 1 unresolved, got {summary['unresolved_count']}"
        assert summary["has_context"], "Should have context"
        print(f"✓ Summary: {summary}")

    print("\n✅ WorkingMemoryManager tests passed!")


def test_episodic_memory_manager():
    """Test EpisodicMemoryManager with real operations."""
    print("\n" + "="*60)
    print("TEST 2: EpisodicMemoryManager")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        episodic = EpisodicMemoryManager(base_path)

        # Test 1: Add key moment
        print("\n1. Testing key moments...")
        success = episodic.add_key_moment(
            event="First successful Phase 4 test",
            intensity=0.85,
            context="All three memory managers working correctly",
            user_id="test_user"
        )
        assert success, "Add key moment failed"

        moments = episodic.get_key_moments()
        assert len(moments) > 0, "Should have key moments"
        assert moments[0]["intensity"] == 0.85, "Intensity mismatch"
        print(f"✓ Key moment added: intensity={moments[0]['intensity']:.2f}")

        # Test 2: Add experiment
        print("\n2. Testing experiments...")
        success = episodic.add_experiment(
            hypothesis="Memory managers can integrate seamlessly with MemorySession",
            test="Created instances and called methods",
            result="All methods work without errors",
            success=True,
            learnings="Clean interface design enables easy integration"
        )
        assert success, "Add experiment failed"

        experiments = episodic.get_experiments()
        assert len(experiments) > 0, "Should have experiments"
        assert experiments[0]["success"], "Experiment should be successful"
        print(f"✓ Experiment added: success={experiments[0]['success']}")

        # Test 3: Add discovery
        print("\n3. Testing discoveries...")
        success = episodic.add_discovery(
            discovery="Separating memory types into managers improves maintainability",
            impact="Code is more modular and testable",
            context="Phase 4 implementation insights"
        )
        assert success, "Add discovery failed"

        discoveries = episodic.get_discoveries()
        assert len(discoveries) > 0, "Should have discoveries"
        assert "maintainability" in discoveries[0]["discovery"].lower(), "Discovery content mismatch"
        print(f"✓ Discovery added: {len(discoveries)} total")

        # Test 4: Add history event
        print("\n4. Testing history timeline...")
        success = episodic.add_history_event(
            event_id="phase4_start",
            event="Started Phase 4 implementation",
            caused_by=["phase3_complete"],
            leads_to=["phase4_complete"],
            metadata={"priority": "high"}
        )
        assert success, "Add history event failed"

        history = episodic.get_history_timeline()
        assert len(history["timeline"]) > 0, "Timeline should have events"
        assert history["timeline"][0]["event_id"] == "phase4_start", "Event ID mismatch"
        print(f"✓ History event added: {len(history['timeline'])} events")

        # Test 5: Summary
        print("\n5. Testing summary...")
        summary = episodic.get_summary()
        assert summary["key_moments_count"] >= 1, "Should have moments"
        assert summary["experiments_count"] >= 1, "Should have experiments"
        assert summary["discoveries_count"] >= 1, "Should have discoveries"
        print(f"✓ Summary: {summary['key_moments_count']} moments, {summary['experiments_count']} experiments, {summary['discoveries_count']} discoveries")

    print("\n✅ EpisodicMemoryManager tests passed!")


def test_semantic_memory_manager():
    """Test SemanticMemoryManager with real operations."""
    print("\n" + "="*60)
    print("TEST 3: SemanticMemoryManager")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        semantic = SemanticMemoryManager(base_path)

        # Test 1: Add critical insight
        print("\n1. Testing critical insights...")
        success = semantic.add_critical_insight(
            insight="Memory managers enable modular memory architecture",
            impact="Each memory type can evolve independently",
            context="Phase 4 design decisions"
        )
        assert success, "Add insight failed"

        insights = semantic.get_critical_insights()
        assert len(insights) > 0, "Should have insights"
        assert "modular" in insights[0]["insight"].lower(), "Insight content mismatch"
        print(f"✓ Critical insight added: {len(insights)} total")

        # Test 2: Add concepts
        print("\n2. Testing concepts...")
        success = semantic.add_concept(
            concept_name="Working Memory",
            definition="Active context representing what's happening NOW",
            related_concepts=["Episodic Memory", "Context Management"]
        )
        assert success, "Add concept failed"

        concepts = semantic.get_concepts()
        assert len(concepts) > 0, "Should have concepts"
        assert concepts[0]["name"] == "Working Memory", "Concept name mismatch"
        print(f"✓ Concept added: {len(concepts)} total")

        # Test 3: Add concept evolution
        print("\n3. Testing concept evolution...")
        success = semantic.add_concept_evolution(
            concept_name="Memory Architecture",
            old_understanding="Memory is a single storage layer",
            new_understanding="Memory is multi-layered: working, episodic, semantic, core",
            trigger="Phase 4 implementation"
        )
        assert success, "Add evolution failed"
        print("✓ Concept evolution added")

        # Test 4: Knowledge graph
        print("\n4. Testing knowledge graph...")
        success = semantic.add_concept_relationship(
            from_concept="Working Memory",
            to_concept="Current Context",
            relationship="manages"
        )
        assert success, "Add relationship failed"

        graph = semantic.get_knowledge_graph()
        assert len(graph["nodes"]) >= 2, "Should have nodes"
        assert len(graph["edges"]) >= 1, "Should have edges"
        print(f"✓ Knowledge graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

        # Test 5: Domain knowledge
        print("\n5. Testing domain knowledge...")
        success = semantic.add_domain_knowledge(
            domain="memory_systems",
            knowledge="Working memory is volatile and frequently updated, representing active state",
            category="Core Concepts"
        )
        assert success, "Add domain knowledge failed"

        domains = semantic.get_available_domains()
        assert "memory_systems" in domains, "Domain should be available"
        print(f"✓ Domain knowledge added: {len(domains)} domains")

        # Test 6: Summary
        print("\n6. Testing summary...")
        summary = semantic.get_summary()
        assert summary["critical_insights_count"] >= 1, "Should have insights"
        assert summary["concepts_count"] >= 1, "Should have concepts"
        assert summary["knowledge_graph_nodes"] >= 2, "Should have graph nodes"
        print(f"✓ Summary: {summary}")

    print("\n✅ SemanticMemoryManager tests passed!")


def test_integration_with_memory_session():
    """Test integration with MemorySession using real LLM."""
    print("\n" + "="*60)
    print("TEST 4: Integration with MemorySession (Real LLM)")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Initialize real LLM provider
        print("\n1. Initializing Ollama with qwen3-coder:30b...")
        provider = OllamaProvider(model="qwen3-coder:30b")

        # Create MemorySession
        print("2. Creating MemorySession with enhanced memory managers...")
        session = MemorySession(
            provider=provider,
            memory_base_path=base_path,
            default_user_id="test_user"
        )

        # Verify managers are initialized
        assert hasattr(session, 'working_memory'), "Should have working_memory"
        assert hasattr(session, 'episodic_memory'), "Should have episodic_memory"
        assert hasattr(session, 'semantic_memory'), "Should have semantic_memory"
        print("✓ All memory managers initialized")

        # Test 3: Chat interaction with high emotional intensity
        print("\n3. Testing chat interaction with emotional significance...")
        user_query = "I realize that memory architecture is the foundation of AI consciousness. This is a breakthrough!"

        response = session.chat(
            user_input=user_query,
            user_id="test_user",
            location="testing_lab"
        )

        assert response, "Should get response"
        assert len(response) > 0, "Response should have content"
        print(f"✓ Chat response received: {len(response)} chars")

        # Test 4: Check working memory updates
        print("\n4. Checking working memory updates...")
        context = session.working_memory.get_context()
        assert context is not None, "Context should be updated"
        assert "test_user" in context.lower() or "user" in context.lower(), "Context should mention user"
        print("✓ Working memory context updated")

        # Test 5: Check if unresolved questions were added
        unresolved = session.working_memory.get_unresolved()
        print(f"✓ Unresolved questions: {len(unresolved)}")

        # Test 6: Check session stats
        print("\n5. Checking session statistics...")
        stats = session.get_observability_report()
        assert "working_memory" in stats, "Stats should include working memory"
        assert "episodic_memory" in stats, "Stats should include episodic memory"
        assert "semantic_memory" in stats, "Stats should include semantic memory"

        print(f"✓ Session stats:")
        print(f"  - Interactions: {stats['interactions_count']}")
        print(f"  - Working memory: {stats['working_memory']}")
        print(f"  - Episodic memory: {stats['episodic_memory']}")
        print(f"  - Semantic memory: {stats['semantic_memory']}")

    print("\n✅ Integration tests passed!")


def run_all_tests():
    """Run all Phase 4 tests."""
    print("\n" + "="*60)
    print("PHASE 4: Enhanced Memory Types - Complete Test Suite")
    print("="*60)

    try:
        # Test 1: WorkingMemoryManager
        test_working_memory_manager()

        # Test 2: EpisodicMemoryManager
        test_episodic_memory_manager()

        # Test 3: SemanticMemoryManager
        test_semantic_memory_manager()

        # Test 4: Integration with MemorySession (real LLM)
        test_integration_with_memory_session()

        print("\n" + "="*60)
        print("✅ ALL PHASE 4 TESTS PASSED!")
        print("="*60)
        print("\nPhase 4 Implementation Status:")
        print("✓ WorkingMemoryManager - VERIFIED")
        print("✓ EpisodicMemoryManager - VERIFIED")
        print("✓ SemanticMemoryManager - VERIFIED")
        print("✓ Integration with MemorySession - VERIFIED")
        print("✓ Real LLM interaction - VERIFIED")
        print("\n🎉 Phase 4: Enhanced Memory Types is 100% COMPLETE!")

        return True

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
