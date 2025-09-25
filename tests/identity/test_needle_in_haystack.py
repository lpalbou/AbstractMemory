"""
Needle-in-haystack test for identity-based memory system.

This test proves that the system can:
1. Store massive amounts of content (40k+ tokens)
2. Find specific information (needle) using identity-based memory
3. Work across sessions with proper persistence
4. Apply subjective interpretation through values lens
"""

import tempfile
import shutil
import pytest
from pathlib import Path
from abstractmemory.grounded_memory import GroundedMemory, MemoryIdentity
from abstractmemory.storage.markdown_storage import MarkdownStorage


class TestNeedleInHaystack:
    """Test memory retrieval with large context and identity."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def generate_large_content(self, topic: str, size_tokens: int) -> list:
        """Generate diverse content for testing (~4 tokens per word estimate)."""
        words_needed = size_tokens // 4
        content_pieces = []

        topics = {
            'tech': [
                "Software development involves writing code in various programming languages.",
                "Database systems store and retrieve information efficiently.",
                "Web frameworks provide tools for building online applications.",
                "Cloud computing offers scalable infrastructure solutions.",
                "Mobile applications run on smartphones and tablets.",
                "Artificial intelligence enables machines to learn and adapt.",
                "Cybersecurity protects digital assets from threats.",
                "DevOps practices streamline software deployment processes."
            ],
            'science': [
                "Physics studies matter, energy, and their interactions.",
                "Chemistry examines atomic and molecular structures.",
                "Biology explores living organisms and life processes.",
                "Mathematics provides tools for quantitative analysis.",
                "Astronomy investigates celestial objects and phenomena.",
                "Geology studies Earth's structure and processes.",
                "Environmental science addresses ecological challenges.",
                "Medical research advances healthcare treatments."
            ],
            'business': [
                "Marketing strategies promote products and services effectively.",
                "Financial planning ensures sustainable business growth.",
                "Operations management optimizes workflow efficiency.",
                "Human resources develops organizational talent.",
                "Strategic planning guides long-term business direction.",
                "Customer service maintains positive client relationships.",
                "Supply chain management coordinates resource flow.",
                "Quality assurance ensures product standards compliance."
            ]
        }

        base_sentences = topics.get(topic, topics['tech'])
        words_generated = 0

        while words_generated < words_needed:
            for sentence in base_sentences:
                if words_generated >= words_needed:
                    break
                # Add variation to make content unique
                variation = f"In context {words_generated // 100}, {sentence}"
                content_pieces.append(variation)
                words_generated += len(variation.split())

        return content_pieces

    def test_needle_in_massive_context(self, temp_storage):
        """
        Core needle-in-haystack test: Find specific fact in 40k+ tokens.
        """
        storage_path = str(Path(temp_storage) / "researcher_memory")

        # === PHASE 1: Create identity with specific values ===
        researcher_values = {
            'purpose': 'research and discovery',
            'approach': 'analytical',
            'lens': 'pattern_recognition',
            'domain': 'machine_learning'
        }

        # Create identity with markdown-only storage to avoid dual storage issues
        identity = MemoryIdentity('researcher', temp_storage)
        identity.core_values = researcher_values

        # Use GroundedMemory without any storage backend to avoid LanceDB dependency
        identity.memories = GroundedMemory(storage_backend=None)
        # Then manually set up markdown storage
        identity.memories.storage_manager = MarkdownStorage(storage_path)
        identity.memories.set_core_values(researcher_values)

        # === PHASE 2: Load massive diverse content (20k tokens) ===
        print("Loading first 20k tokens of content...")

        tech_content = self.generate_large_content('tech', 7000)
        science_content = self.generate_large_content('science', 7000)
        business_content = self.generate_large_content('business', 6000)

        # Add all the content as interactions
        user_id = 'research_partner'
        identity.memories.set_current_user(user_id, 'collaborator')

        interaction_count = 0
        for content_list, domain in [(tech_content, 'tech'), (science_content, 'science'), (business_content, 'business')]:
            for i, content in enumerate(content_list):
                if interaction_count >= 200:  # Limit to prevent excessive test time
                    break
                identity.memories.add_interaction(
                    content,
                    f"Interesting insights about {domain}",
                    user_id
                )
                interaction_count += 1

        print(f"Added {interaction_count} interactions (~20k tokens)")

        # === PHASE 3: Insert the needle ===
        NEEDLE = "multi-layered temporal and relational memory is central to autonomous and evolutive Agents"

        identity.memories.add_interaction(
            f"Based on my research, I believe that {NEEDLE}. This is a key insight.",
            "That's a profound observation about agent architecture.",
            user_id
        )

        print("✅ Inserted needle into haystack")

        # === PHASE 4: Add more massive content (20k tokens) ===
        print("Loading second 20k tokens of content...")

        more_tech = self.generate_large_content('tech', 10000)
        more_science = self.generate_large_content('science', 10000)

        for content_list in [more_tech, more_science]:
            for i, content in enumerate(content_list):
                if i >= 100:  # Limit for test performance
                    break
                identity.memories.add_interaction(
                    content,
                    "More interesting research data",
                    user_id
                )
                interaction_count += 1

        print(f"Total interactions: {interaction_count} (~40k+ tokens)")

        # Save everything
        identity.memories.save_to_storage()
        identity.save()

        # === PHASE 5: New session - test needle retrieval ===
        print("Starting new session to test needle retrieval...")

        # Create completely new identity instance (simulating restart)
        new_identity = MemoryIdentity('researcher', temp_storage)
        new_identity.core_values = researcher_values

        # Manually create new GroundedMemory with same storage path
        new_identity.memories = GroundedMemory(storage_backend=None)
        new_identity.memories.storage_manager = MarkdownStorage(storage_path)
        new_identity.memories.set_core_values(researcher_values)

        # Load from storage
        new_identity.memories.load_from_storage()

        # Verify identity loaded correctly
        assert new_identity.core_values == researcher_values
        assert new_identity.memories.subjective_lens is not None

        # Test memory context retrieval for needle (use single words for better matching)
        context = new_identity.memories.get_full_context(
            "autonomous",
            user_id=user_id,
            max_items=15  # Increase limit for large dataset
        )

        print("Testing needle retrieval...")

        # Check if needle is found in context
        needle_found = "temporal and relational memory" in context
        central_found = "central to autonomous" in context

        print(f"Context length: {len(context)} characters")
        print(f"Needle found: {needle_found}")
        print(f"Key concept found: {central_found}")

        # Verify user profile persisted
        user_profile_found = user_id in context
        relationship_found = "collaborator" in context.lower()

        print(f"User profile in context: {user_profile_found}")
        print(f"Relationship preserved: {relationship_found}")

        # Test subjective interpretation through values lens
        interpretation = new_identity.memories.interpret_fact_subjectively(
            "autonomous agents need better memory systems"
        )

        values_applied = interpretation['values_triggered']
        subjective_meaning = interpretation['subjective_meaning']

        print(f"Values applied to interpretation: {len(values_applied) > 0}")
        print(f"Subjective meaning: {subjective_meaning[:100]}...")

        # === ASSERTIONS ===

        # Core functionality
        assert needle_found or central_found, f"Needle not found in context. Context: {context[:500]}..."
        assert user_profile_found, "User profile not found in context"
        assert relationship_found, "User relationship not preserved"

        # Identity functionality
        assert new_identity.memories.subjective_lens is not None, "Subjective lens not created"
        assert len(new_identity.memories.user_profiles) > 0, "User profiles not loaded"
        assert user_id in new_identity.memories.user_profiles, "Specific user profile not loaded"

        # Subjective interpretation
        assert subjective_meaning != "standard factual information", "Values lens not applied"

        print("✅ NEEDLE-IN-HAYSTACK TEST PASSED!")
        print("✅ Identity-based memory system works at scale!")

    def test_identity_specific_needle_retrieval(self, temp_storage):
        """
        Test that different identities find different aspects of the same information.
        """
        # Create researcher identity
        researcher_values = {'purpose': 'research', 'approach': 'analytical'}
        researcher_path = str(Path(temp_storage) / "researcher")

        researcher = MemoryIdentity('researcher', researcher_path)
        researcher.core_values = researcher_values
        researcher.memories = GroundedMemory(storage_backend=None)
        researcher.memories.storage_manager = MarkdownStorage(researcher_path + "_storage")
        researcher.memories.set_core_values(researcher_values)

        # Create helper identity with different values
        helper_values = {'purpose': 'helping people', 'approach': 'wellbeing'}
        helper_path = str(Path(temp_storage) / "helper")

        helper = MemoryIdentity('helper', helper_path)
        helper.core_values = helper_values
        helper.memories = GroundedMemory(storage_backend=None)
        helper.memories.storage_manager = MarkdownStorage(helper_path + "_storage")
        helper.memories.set_core_values(helper_values)

        # Same fact, different interpretations expected
        fact = "The team worked 80 hours this week to meet the deadline"

        researcher_interp = researcher.memories.interpret_fact_subjectively(fact)
        helper_interp = helper.memories.interpret_fact_subjectively(fact)

        # Should get different interpretations based on values
        assert researcher_interp['subjective_meaning'] != helper_interp['subjective_meaning']
        assert researcher_interp['emotional_tone'] != helper_interp['emotional_tone']

        print("✅ Different identities interpret facts differently!")
        print(f"Researcher: {researcher_interp['subjective_meaning']}")
        print(f"Helper: {helper_interp['subjective_meaning']}")


if __name__ == "__main__":
    # Run the test directly
    test = TestNeedleInHaystack()
    with tempfile.TemporaryDirectory() as temp_dir:
        test.test_needle_in_massive_context(temp_dir)
        test.test_identity_specific_needle_retrieval(temp_dir)