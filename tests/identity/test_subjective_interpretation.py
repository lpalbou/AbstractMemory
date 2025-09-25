"""
Subjective Interpretation Test - Verifies core values create different meanings.

This test proves that the same objective facts get different subjective
interpretations based on the AI's core values - the foundation of identity.
"""

import tempfile
import shutil
import pytest
from pathlib import Path
from abstractmemory.grounded_memory import SubjectiveExperience, GroundedMemory
from abstractmemory.storage.markdown_storage import MarkdownStorage


class TestSubjectiveInterpretation:
    """Test that core values create different subjective interpretations."""

    def test_same_fact_different_interpretations(self):
        """
        Core test: Same fact should produce different interpretations based on values.
        """
        # Test facts that should trigger different value responses
        test_facts = [
            "The team worked 80 hours this week to meet the deadline",
            "There is a complex problem that needs to be solved",
            "The user is asking for help with their project",
            "The research data shows interesting patterns",
            "We need to build a new system from scratch"
        ]

        # Different value systems to test
        value_systems = {
            'productivity_focused': {
                'purpose': 'efficiency and optimization',
                'approach': 'productivity',
                'lens': 'efficiency'
            },
            'wellbeing_focused': {
                'purpose': 'maintaining balance',
                'approach': 'wellbeing',
                'lens': 'health'
            },
            'learning_focused': {
                'purpose': 'continuous growth',
                'approach': 'learning',
                'lens': 'education'
            },
            'helping_focused': {
                'purpose': 'helping people',
                'approach': 'service',
                'lens': 'assistance'
            },
            'research_focused': {
                'purpose': 'research and discovery',
                'approach': 'analytical',
                'lens': 'investigation'
            }
        }

        print("=== Testing Subjective Interpretation Across Value Systems ===")

        # Test each fact with each value system
        for fact in test_facts:
            print(f"\\nFACT: {fact}")

            interpretations = {}

            # Generate interpretation for each value system
            for value_name, values in value_systems.items():
                lens = SubjectiveExperience(values)
                interpretation = lens.interpret(fact)
                interpretations[value_name] = interpretation

                print(f"  {value_name.upper()}:")
                print(f"    Meaning: {interpretation['subjective_meaning']}")
                print(f"    Emotion: {interpretation['emotional_tone']}")
                print(f"    Relevance: {interpretation['importance']:.2f}")

            # Verify all interpretations are different
            meanings = [interp['subjective_meaning'] for interp in interpretations.values()]
            emotions = [interp['emotional_tone'] for interp in interpretations.values()]

            unique_meanings = set(meanings)
            unique_emotions = set(emotions)

            # Assert uniqueness
            assert len(unique_meanings) > 1, f"All interpretations identical for: {fact}"
            assert len(unique_emotions) > 1, f"All emotional tones identical for: {fact}"

            print(f"    ✅ Generated {len(unique_meanings)} unique meanings, {len(unique_emotions)} unique emotions")

        print("\\n🎉 All facts produced different interpretations across value systems!")

    def test_identity_shapes_memory_context(self):
        """
        Test that identity (through values) influences memory context retrieval.
        """
        temp_dir = tempfile.mkdtemp()

        try:
            print("\\n=== Testing Identity Influence on Memory Context ===")

            # Create two identities with different values
            researcher_values = {
                'purpose': 'research and discovery',
                'approach': 'analytical',
                'lens': 'scientific'
            }

            helper_values = {
                'purpose': 'helping people',
                'approach': 'empathetic',
                'lens': 'support'
            }

            # Create researcher identity
            researcher_path = str(Path(temp_dir) / "researcher")
            researcher_memory = GroundedMemory(storage_backend=None)
            researcher_memory.storage_manager = MarkdownStorage(researcher_path)
            researcher_memory.set_core_values(researcher_values)
            researcher_memory.set_current_user('user1', 'collaborator')

            # Create helper identity
            helper_path = str(Path(temp_dir) / "helper")
            helper_memory = GroundedMemory(storage_backend=None)
            helper_memory.storage_manager = MarkdownStorage(helper_path)
            helper_memory.set_core_values(helper_values)
            helper_memory.set_current_user('user1', 'friend')

            # Add same interactions to both
            test_interaction = "I'm struggling with a complex machine learning problem"
            researcher_memory.add_interaction(test_interaction, "Let's analyze the data", 'user1')
            helper_memory.add_interaction(test_interaction, "I'll help you through this", 'user1')

            # Test subjective interpretations
            researcher_interp = researcher_memory.interpret_fact_subjectively(test_interaction)
            helper_interp = helper_memory.interpret_fact_subjectively(test_interaction)

            print("RESEARCHER interpretation:")
            print(f"  Meaning: {researcher_interp['subjective_meaning']}")
            print(f"  Emotion: {researcher_interp['emotional_tone']}")

            print("HELPER interpretation:")
            print(f"  Meaning: {helper_interp['subjective_meaning']}")
            print(f"  Emotion: {helper_interp['emotional_tone']}")

            # Verify different interpretations
            assert researcher_interp['subjective_meaning'] != helper_interp['subjective_meaning']
            assert researcher_interp['emotional_tone'] != helper_interp['emotional_tone']

            print("✅ Different identities produce different interpretations!")

            # Test context retrieval differences
            researcher_context = researcher_memory.get_full_context("machine learning", user_id='user1')
            helper_context = helper_memory.get_full_context("machine learning", user_id='user1')

            # Both should contain the interaction but with different identity context
            assert "machine learning problem" in researcher_context
            assert "machine learning problem" in helper_context

            # Should have different identity contexts (researcher vs helper values reflected somehow)
            context_different = researcher_context != helper_context
            assert context_different, "Contexts should differ between different identities"

            print("✅ Identity influences memory context retrieval!")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_values_evolution_over_time(self):
        """
        Test that values can influence interpretation consistently over time.
        """
        temp_dir = tempfile.mkdtemp()

        try:
            print("\\n=== Testing Values Consistency Over Time ===")

            storage_path = str(Path(temp_dir) / "evolving_identity")

            # Session 1: Establish values-based interpretations
            memory1 = GroundedMemory(storage_backend=None)
            memory1.storage_manager = MarkdownStorage(storage_path)
            memory1.set_core_values({'purpose': 'helping people', 'approach': 'empathetic'})
            memory1.set_current_user('user1', 'friend')

            # Add interactions and track interpretations
            facts = [
                "The deadline is very tight for this project",
                "There's a difficult technical challenge ahead",
                "The team needs guidance on this issue"
            ]

            session1_interpretations = {}
            for fact in facts:
                memory1.add_interaction(fact, "I understand", 'user1')
                interp = memory1.interpret_fact_subjectively(fact)
                session1_interpretations[fact] = interp['subjective_meaning']

            memory1.save_to_storage()
            print(f"Session 1: Recorded {len(facts)} value-based interpretations")

            # Session 2: Load same identity and verify consistent interpretations
            memory2 = GroundedMemory(storage_backend=None)
            memory2.storage_manager = MarkdownStorage(storage_path)
            memory2.set_core_values({'purpose': 'helping people', 'approach': 'empathetic'})  # Same values
            memory2.load_from_storage()

            session2_interpretations = {}
            for fact in facts:
                interp = memory2.interpret_fact_subjectively(fact)
                session2_interpretations[fact] = interp['subjective_meaning']

            print(f"Session 2: Generated {len(facts)} interpretations with same values")

            # Verify interpretations are consistent across sessions
            for fact in facts:
                assert session1_interpretations[fact] == session2_interpretations[fact], \
                    f"Interpretation changed between sessions for: {fact}"

            print("✅ Values produce consistent interpretations across sessions!")

            # Session 3: Change values and verify different interpretations
            memory3 = GroundedMemory(storage_backend=None)
            memory3.storage_manager = MarkdownStorage(storage_path)
            memory3.set_core_values({'purpose': 'efficiency', 'approach': 'productivity'})  # Different values
            memory3.load_from_storage()

            session3_interpretations = {}
            for fact in facts:
                interp = memory3.interpret_fact_subjectively(fact)
                session3_interpretations[fact] = interp['subjective_meaning']

            print(f"Session 3: Generated {len(facts)} interpretations with different values")

            # Verify interpretations are different with different values
            different_count = 0
            for fact in facts:
                if session1_interpretations[fact] != session3_interpretations[fact]:
                    different_count += 1

            assert different_count > 0, "Values change should produce some different interpretations"
            print(f"✅ Different values produced {different_count}/{len(facts)} different interpretations!")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # Run tests directly
    test = TestSubjectiveInterpretation()
    test.test_same_fact_different_interpretations()
    test.test_identity_shapes_memory_context()
    test.test_values_evolution_over_time()

    print("\\n🎉 ALL SUBJECTIVE INTERPRETATION TESTS PASSED!")
    print("✅ Core values successfully create different subjective meanings")
    print("✅ Identity shapes memory and context retrieval")
    print("✅ Values produce consistent behavior over time")
    print("✅ System ready for identity-based AI agents!")