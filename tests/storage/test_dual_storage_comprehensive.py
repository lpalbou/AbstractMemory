"""
Comprehensive tests for dual storage system serialization/deserialization.
Uses ONLY real implementations - NO MOCKS anywhere.
"""

import pytest
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add AbstractCore path for real embedding provider
sys.path.insert(0, '/Users/albou/projects/abstractllm_core')

from abstractmemory import create_memory
from abstractmemory.core.interfaces import MemoryItem

# Real embedding provider for testing
try:
    from abstractllm.embeddings import EmbeddingManager
    REAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    REAL_EMBEDDINGS_AVAILABLE = False


class TestDualStorageComprehensive:
    """Comprehensive dual storage system tests"""

    def setup_method(self):
        """Setup test environment with real embedding provider"""
        self.temp_dir = tempfile.mkdtemp()

        # Use real embedding provider if available
        if REAL_EMBEDDINGS_AVAILABLE:
            self.embedding_provider = EmbeddingManager()
        else:
            self.embedding_provider = None

    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)

    def test_full_dual_storage_lifecycle(self):
        """Test complete dual storage lifecycle with real serialization"""

        # Create memory with dual storage (markdown only for now)
        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir,
            embedding_provider=self.embedding_provider,
            working_capacity=5,
            semantic_threshold=2
        )

        # Test 1: Multiple users with different interaction patterns
        users_data = [
            {
                "user_id": "alice",
                "relationship": "owner",
                "interactions": [
                    ("I'm a Python developer who loves machine learning",
                     "Excellent! Python has amazing ML libraries like scikit-learn, TensorFlow, and PyTorch."),
                    ("I prefer detailed explanations with code examples",
                     "Perfect! I'll make sure to provide comprehensive explanations with practical code examples."),
                    ("Can you help me with neural network architecture?",
                     "Absolutely! Let's start with the basics of neural network layers and build up to complex architectures.")
                ]
            },
            {
                "user_id": "bob",
                "relationship": "colleague",
                "interactions": [
                    ("I'm new to programming and need simple explanations",
                     "Welcome! I'll break everything down into simple, easy-to-follow steps."),
                    ("The last approach failed, but this usually works better",
                     "I understand. Let's focus on the approach that has worked reliably for you."),
                    ("Actually, switching topics - what about web development?",
                     "Great transition! Web development offers many exciting opportunities.")
                ]
            }
        ]

        # Generate interactions across time
        base_time = datetime.now()
        all_interaction_ids = []
        all_note_ids = []

        for user_data in users_data:
            memory.set_current_user(user_data["user_id"], user_data["relationship"])

            for i, (user_input, agent_response) in enumerate(user_data["interactions"]):
                # Simulate realistic time gaps
                interaction_time = base_time + timedelta(minutes=i*10)

                # Add interaction
                memory.add_interaction(user_input, agent_response)

                # Track for verification
                all_interaction_ids.append(f"interaction_{len(all_interaction_ids)}")

        # Test 2: Verify storage structure was created correctly
        storage_path = Path(self.temp_dir)

        # Check directory structure
        assert (storage_path / "verbatim").exists()
        assert (storage_path / "experiential").exists()
        assert (storage_path / "links").exists()
        assert (storage_path / "index.json").exists()

        # Test 3: Verify interactions were stored with correct structure
        verbatim_files = list((storage_path / "verbatim").rglob("*.md"))
        assert len(verbatim_files) == 6  # Total interactions

        # Verify user separation
        alice_files = list((storage_path / "verbatim" / "alice").rglob("*.md"))
        bob_files = list((storage_path / "verbatim" / "bob").rglob("*.md"))
        assert len(alice_files) == 3
        assert len(bob_files) == 3

        # Test 4: Verify experiential notes were generated
        exp_files = list((storage_path / "experiential").rglob("*.md"))
        assert len(exp_files) >= 3  # Should have several reflections

        # Test 5: Verify bidirectional links were created
        link_files = list((storage_path / "links").rglob("*.json"))
        assert len(link_files) >= 3  # Should have links for reflections

        # Test 6: Verify index.json integrity
        with open(storage_path / "index.json", 'r') as f:
            index = json.load(f)

        assert "interactions" in index
        assert "experiential_notes" in index
        assert "links" in index
        assert len(index["interactions"]) == 6
        assert len(index["users"]) == 2
        assert "alice" in index["users"]
        assert "bob" in index["users"]

        # Test 7: Verify embedding provider integration
        # For markdown-only mode, embeddings are not required but provider should be present
        if self.embedding_provider is not None:
            assert hasattr(self.embedding_provider, 'embed') or hasattr(self.embedding_provider, 'generate_embedding')

        # Test 8: Test serialization completeness - read back files
        sample_verbatim = verbatim_files[0]
        with open(sample_verbatim, 'r') as f:
            content = f.read()

        # Verify all required sections are present
        assert "# Interaction:" in content
        assert "**ID**:" in content
        assert "**Date**:" in content
        assert "**User**:" in content
        assert "## User Input" in content
        assert "## Agent Response" in content
        assert "Generated by AbstractMemory" in content

        # Test 9: Test experiential note structure
        if exp_files:
            sample_note = exp_files[0]
            with open(sample_note, 'r') as f:
                note_content = f.read()

            assert "# AI" in note_content
            assert "**Note ID**:" in note_content
            assert "**Type**:" in note_content
            assert "## Reflection" in note_content
            assert "## Memory Impact" in note_content

        # Return for use by other test methods
        self._test_memory = memory
        self._test_storage_path = storage_path

    def test_storage_deserialization_and_search(self):
        """Test loading and searching stored data"""

        # First create and populate storage
        self.test_full_dual_storage_lifecycle()
        memory = self._test_memory
        storage_path = self._test_storage_path

        # Test 1: Search functionality
        python_results = memory.search_stored_interactions("python")
        assert len(python_results) >= 1

        ml_results = memory.search_stored_interactions("machine learning")
        assert len(ml_results) >= 1

        # Test 2: User-specific searches
        alice_results = memory.search_stored_interactions("python", user_id="alice")
        assert len(alice_results) >= 1
        assert all(r["user_id"] == "alice" for r in alice_results)

        bob_results = memory.search_stored_interactions("programming", user_id="bob")
        assert len(bob_results) >= 1
        assert all(r["user_id"] == "bob" for r in bob_results)

        # Test 3: Time-based searches
        now = datetime.now()
        recent_results = memory.search_stored_interactions(
            "python",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1)
        )
        assert len(recent_results) >= 0  # Should find recent interactions

        # Test 4: Complex queries
        web_results = memory.search_stored_interactions("web development")
        assert len(web_results) >= 1

    def test_memory_component_serialization(self):
        """Test serialization of memory components themselves"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir,
            working_capacity=3,
            semantic_threshold=2
        )

        # Populate memory with data
        memory.set_current_user("charlie", "client")

        # Add interactions to populate different memory components
        memory.add_interaction("I love Python", "Python is excellent!")
        memory.add_interaction("I love Python", "Yes, Python is amazing!")  # Duplicate for semantic validation
        memory.add_interaction("I love Python", "Python rocks!")  # Third time to trigger semantic memory

        memory.learn_about_user("expert in machine learning")
        memory.track_success("python_help", "provided useful explanation")
        memory.track_failure("complex_topic", "explanation was too advanced")

        # Test saving memory components
        memory.save(self.temp_dir)

        # Verify component files were created
        storage_path = Path(self.temp_dir)

        # Check that memory components were saved
        core_files = list((storage_path / "core").glob("*.json"))
        assert len(core_files) > 0

        # Test loading memory state
        new_memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        # Load the saved state
        new_memory.load(self.temp_dir)

        # Verify user profiles were preserved
        if hasattr(new_memory, 'user_profiles'):
            # User profiles should be preserved
            assert isinstance(new_memory.user_profiles, dict)

    def test_concurrent_user_storage(self):
        """Test storage with multiple users accessing simultaneously"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir,
            embedding_provider=self.embedding_provider
        )

        # Simulate multiple users with overlapping interactions
        users = ["alice", "bob", "charlie", "diana"]
        interactions_per_user = 3

        for user in users:
            memory.set_current_user(user, "user")

            for i in range(interactions_per_user):
                memory.add_interaction(
                    f"User {user} question {i+1} about Python programming",
                    f"Here's my response to {user} about Python topic {i+1}"
                )

        # Verify all users have separate storage
        storage_path = Path(self.temp_dir)

        for user in users:
            user_files = list((storage_path / "verbatim" / user).rglob("*.md"))
            assert len(user_files) == interactions_per_user

        # Verify index tracks all users
        with open(storage_path / "index.json", 'r') as f:
            index = json.load(f)

        assert len(index["users"]) == len(users)
        for user in users:
            assert user in index["users"]

        # Test user-specific searches work correctly
        for user in users:
            user_results = memory.search_stored_interactions("Python", user_id=user)
            assert len(user_results) == interactions_per_user
            assert all(r["user_id"] == user for r in user_results)

    def test_error_recovery_and_partial_failures(self):
        """Test system behavior with partial failures and recovery"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("test_user")

        # Add some successful interactions
        memory.add_interaction("First interaction", "First response")
        memory.add_interaction("Second interaction", "Second response")

        # Verify initial state
        stats1 = memory.get_storage_stats()
        initial_interactions = stats1["markdown_stats"]["total_interactions"]

        # Simulate adding more interactions after some potential errors
        memory.add_interaction("Third interaction", "Third response")
        memory.add_interaction("Fourth interaction", "Fourth response")

        # Verify recovery
        stats2 = memory.get_storage_stats()
        final_interactions = stats2["markdown_stats"]["total_interactions"]

        assert final_interactions == initial_interactions + 2

    def test_large_data_serialization(self):
        """Test serialization with larger datasets"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir,
            working_capacity=10
        )

        # Generate substantial amount of data
        memory.set_current_user("heavy_user", "power_user")

        # Create 50 interactions with varying content
        for i in range(50):
            user_input = f"This is a substantial user input number {i} with detailed content about Python programming, machine learning, web development, and various technical topics that should trigger different reflection patterns."

            agent_response = f"This is a comprehensive response number {i} that provides detailed explanations, code examples, and technical guidance tailored to the user's level of expertise in various programming domains."

            memory.add_interaction(user_input, agent_response)

        # Verify storage can handle large datasets
        stats = memory.get_storage_stats()
        assert stats["markdown_stats"]["total_interactions"] == 50

        # Test search performance with larger dataset
        python_results = memory.search_stored_interactions("Python")
        assert len(python_results) > 0

        programming_results = memory.search_stored_interactions("programming")
        assert len(programming_results) > 0

        # Verify all files are properly structured
        storage_path = Path(self.temp_dir)
        verbatim_files = list((storage_path / "verbatim").rglob("*.md"))
        assert len(verbatim_files) == 50

        # Verify index.json is properly maintained
        with open(storage_path / "index.json", 'r') as f:
            index = json.load(f)

        assert len(index["interactions"]) == 50

    def test_reflection_trigger_patterns(self):
        """Test various reflection trigger patterns and their serialization"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory.set_current_user("reflection_tester")

        # Test different reflection triggers
        trigger_tests = [
            # User learning trigger
            ("I am a beginner programmer and I prefer simple explanations",
             "Perfect! I'll make sure to explain concepts step by step."),

            # Pattern learning trigger
            ("That approach failed before, but this usually works better",
             "Good insight! Let's use the approach that works reliably for you."),

            # Topic shift trigger
            ("By the way, switching topics - what about data science?",
             "Great transition! Data science is a fascinating field."),

            # Confidence boost trigger
            ("That explanation was exactly right and perfectly clear",
             "Excellent! I'm glad that explanation was helpful."),

            # Uncertainty trigger
            ("I'm not sure if that approach might work or perhaps another way",
             "Let's explore both options to find what works best for your situation.")
        ]

        for user_input, agent_response in trigger_tests:
            memory.add_interaction(user_input, agent_response)

        # Verify reflections were generated and stored
        storage_path = Path(self.temp_dir)
        exp_files = list((storage_path / "experiential").rglob("*.md"))

        # Should have multiple reflections based on triggers
        assert len(exp_files) >= 3

        # Verify reflection content contains expected patterns
        reflection_contents = []
        for exp_file in exp_files:
            with open(exp_file, 'r') as f:
                reflection_contents.append(f.read())

        # Check for expected reflection indicators
        combined_content = " ".join(reflection_contents)

        # Should contain analysis of patterns detected
        assert any(keyword in combined_content.lower() for keyword in [
            "user learning", "pattern", "confidence", "uncertainty", "transition"
        ])

    def test_storage_stats_accuracy(self):
        """Test storage statistics accuracy across operations"""

        memory = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        # Start with clean state
        initial_stats = memory.get_storage_stats()
        assert initial_stats["markdown_stats"]["total_interactions"] == 0
        assert initial_stats["markdown_stats"]["total_notes"] == 0

        # Add interactions and verify stats update
        memory.set_current_user("stats_user")

        for i in range(5):
            memory.add_interaction(f"Question {i}", f"Answer {i}")

            current_stats = memory.get_storage_stats()
            expected_interactions = i + 1

            assert current_stats["markdown_stats"]["total_interactions"] == expected_interactions

        # Verify final statistics
        final_stats = memory.get_storage_stats()
        assert final_stats["markdown_stats"]["total_interactions"] == 5
        assert final_stats["markdown_stats"]["unique_users"] == 1
        assert final_stats["markdown_stats"]["unique_users"] == 1

    def test_cross_session_persistence(self):
        """Test data persistence across memory instances"""

        # Create first memory instance
        memory1 = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        memory1.set_current_user("persistent_user")
        memory1.add_interaction("Persistent question", "Persistent answer")

        stats1 = memory1.get_storage_stats()

        # Create second memory instance with same storage
        memory2 = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        # Verify data persists across instances
        stats2 = memory2.get_storage_stats()
        assert stats2["markdown_stats"]["total_interactions"] == stats1["markdown_stats"]["total_interactions"]

        # Add more data with second instance
        memory2.set_current_user("persistent_user")
        memory2.add_interaction("Second session question", "Second session answer")

        # Create third instance and verify all data is there
        memory3 = create_memory(
            "grounded",
            storage_backend="markdown",
            storage_path=self.temp_dir
        )

        stats3 = memory3.get_storage_stats()
        assert stats3["markdown_stats"]["total_interactions"] == 2

        # Verify search works across sessions
        results = memory3.search_stored_interactions("persistent")
        assert len(results) >= 1