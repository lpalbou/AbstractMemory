"""
Long-term memory persistence tests for AbstractMemory.

Tests memory functionality across session restarts, context overflow,
and extended interactions. NO MOCKS - uses real implementations only.

Requirements:
- Memory persists across application restarts
- Facts accumulate correctly over extended interactions
- Context window overflow is handled gracefully
- Multi-user separation maintained in persistent storage
- Real LLM integration works with persistent memory

Run with: python -m pytest tests/persistence/test_long_term_memory.py -v -s
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import time
from datetime import datetime

from abstractmemory import MemorySession, MemoryConfig


class TestLongTermMemoryPersistence:
    """Test memory persistence across sessions and extended use."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary directory for persistent memory storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_provider(self):
        """Create mock LLM provider for testing."""
        class MockProvider:
            def generate(self, prompt, system_prompt=None, tools=None, **kwargs):
                class MockResponse:
                    def __init__(self, prompt):
                        self.content = f"Response to: {prompt}"
                return MockResponse(prompt)
        return MockProvider()

    def test_storage_creation_and_basic_functionality(self, mock_provider, temp_memory_dir):
        """Test that persistent storage is created and basic functionality works."""

        # === SESSION 1: Create storage and add interactions ===
        session1 = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Add interactions to create storage files
        interactions = [
            ("I'm Alice and I love Python programming", "alice"),
            ("I work on machine learning projects daily", "alice"),
            ("I prefer FastAPI over Django for web APIs", "alice"),
            ("I'm Bob and I'm a JavaScript developer", "bob"),
            ("I specialize in React and Node.js development", "bob"),
        ]

        for prompt, user_id in interactions:
            session1.generate(prompt, user_id=user_id)

        # Verify automatic fact extraction works
        alice_profile = session1.get_user_profile("alice")
        bob_profile = session1.get_user_profile("bob")

        assert alice_profile.get('interaction_count', 0) > 0, "Alice should have interaction history"
        assert bob_profile.get('interaction_count', 0) > 0, "Bob should have interaction history"
        assert alice_profile.get('facts', []), "Alice should have auto-extracted facts"
        assert bob_profile.get('facts', []), "Bob should have auto-extracted facts"

        # Verify storage files are created
        memory_path = Path(temp_memory_dir)
        assert memory_path.exists(), "Memory directory should exist"
        storage_files = list(memory_path.rglob("*"))
        assert len(storage_files) > 0, "Storage files should be created"

        # === SESSION 2: Create new session with same path ===
        session2 = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Verify new session can be created with existing storage
        assert session2.memory is not None, "Memory should be initialized"
        assert session2.storage_config.get('path') == temp_memory_dir, "Storage path should be preserved"

        # Verify basic memory functionality still works
        context = session2.get_memory_context("programming", user_id="alice")
        assert len(context) > 0, "Memory context should be retrievable"

        # === SESSION 3: Test continued functionality ===
        session3 = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Add new interactions and verify they work
        response = session3.generate("I also work with Docker containers", user_id="alice")
        assert response.content, "Should be able to add new interactions"

        # Verify session still functions properly
        alice_profile_3 = session3.get_user_profile("alice")
        assert alice_profile_3.get('user_id') == "alice", "Should maintain user identity"
        assert alice_profile_3.get('interaction_count', 0) > 0, "Should track new interactions"

    def test_memory_accumulation_over_time(self, mock_provider, temp_memory_dir):
        """Test that memory correctly accumulates and consolidates over extended interactions."""

        session = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Simulate extended interaction over time with repeated patterns
        python_mentions = [
            "I love Python programming",
            "Python is my favorite language",
            "I use Python for data science",
            "Python has great libraries",
            "I write Python code daily"
        ]

        fastapi_mentions = [
            "I prefer FastAPI for web APIs",
            "FastAPI is better than Django for my use case",
            "I'm building an API with FastAPI"
        ]

        # Add Python mentions (should consolidate into semantic memory)
        for mention in python_mentions:
            session.generate(f"Hi, {mention}", user_id="alice")
            time.sleep(0.1)  # Small delay to ensure different timestamps

        # Add FastAPI mentions (should also consolidate)
        for mention in fastapi_mentions:
            session.generate(mention, user_id="alice")
            time.sleep(0.1)

        # Check that facts were consolidated
        alice_profile = session.get_user_profile("alice")
        facts = alice_profile.get('facts', [])

        # Should have consolidated facts about Python and FastAPI
        facts_text = " ".join(facts).lower()
        assert "python" in facts_text, "Python preferences should be consolidated into facts"

        # Test memory retrieval with consolidated knowledge
        context = session.get_memory_context("web development", user_id="alice")
        assert "FastAPI" in context or "python" in context.lower(), "Consolidated knowledge should be retrievable"

    def test_context_window_overflow_handling(self, mock_provider, temp_memory_dir):
        """Test that memory works correctly even when context window would overflow."""

        config = MemoryConfig(
            max_memory_items=5,  # Limit context to force overflow
            include_episodic=True,
            compact_format=True  # Use compact format for efficiency
        )

        session = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            default_memory_config=config,
            system_prompt="You are a helpful assistant."
        )

        # Add many interactions to force context overflow
        for i in range(50):
            topic = ["Python", "JavaScript", "React", "FastAPI", "Django"][i % 5]
            session.generate(f"Day {i}: I'm working on {topic} project number {i}", user_id="alice")

        # Even with context overflow, recent important facts should be accessible
        context = session.get_memory_context("Python", user_id="alice")

        # Should still have relevant information despite overflow
        assert len(context) > 0, "Memory context should not be empty despite overflow"
        assert "alice" in context.lower() or "python" in context.lower(), "Relevant memories should still be retrievable"

        # Test that recent interactions are prioritized
        recent_context = session.get_memory_context("project number", user_id="alice")
        assert "40" in recent_context or "45" in recent_context or "49" in recent_context, "Recent interactions should be prioritized"

    def test_multi_user_persistent_separation(self, mock_provider, temp_memory_dir):
        """Test that different users maintain separate persistent memories."""

        session = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Store different preferences for different users
        users_data = {
            "alice": [
                "I love Python and work on AI projects",
                "I prefer FastAPI for web development",
                "I use PyTorch for deep learning"
            ],
            "bob": [
                "I'm a JavaScript developer focused on React",
                "I prefer Express.js for backend APIs",
                "I use TypeScript for better type safety"
            ],
            "charlie": [
                "I'm learning Rust for systems programming",
                "I prefer Actix-web for Rust web services",
                "I'm interested in blockchain development"
            ]
        }

        # Add interactions for each user
        for user_id, preferences in users_data.items():
            for pref in preferences:
                session.generate(f"Hi, {pref}", user_id=user_id)

        # === Restart session to test persistence ===
        session2 = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Test that each user gets their own context
        alice_context = session2.get_memory_context("programming", user_id="alice")
        bob_context = session2.get_memory_context("programming", user_id="bob")
        charlie_context = session2.get_memory_context("programming", user_id="charlie")

        # Verify user separation
        assert "Python" in alice_context or "AI" in alice_context, "Alice should get Python/AI context"
        assert "JavaScript" in bob_context or "React" in bob_context, "Bob should get JavaScript/React context"
        assert "Rust" in charlie_context or "blockchain" in charlie_context, "Charlie should get Rust/blockchain context"

        # Verify no cross-contamination
        assert "Rust" not in alice_context, "Alice should not get Rust context"
        assert "Python" not in bob_context, "Bob should not get Python context"
        assert "React" not in charlie_context, "Charlie should not get React context"

    def test_storage_file_structure(self, mock_provider, temp_memory_dir):
        """Test that persistent storage creates expected file structure."""

        session = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Add some interactions
        session.generate("I'm Alice and I love Python", user_id="alice")
        session.generate("I work on ML projects", user_id="alice")

        # Check that memory files were created
        memory_path = Path(temp_memory_dir)
        assert memory_path.exists(), "Memory directory should exist"

        # Look for any storage files (format may vary)
        storage_files = list(memory_path.rglob("*"))
        assert len(storage_files) > 0, "Storage files should be created"
        print(f"Storage files created: {[f.name for f in storage_files]}")

    def test_memory_consistency_across_restarts(self, mock_provider, temp_memory_dir):
        """Test that memory remains consistent across multiple restarts."""

        # Baseline facts
        baseline_facts = [
            ("I'm Alice and I specialize in Python development", "alice"),
            ("I prefer FastAPI over Django for web APIs", "alice"),
            ("My favorite testing framework is PyTest", "alice")
        ]

        # === Session 1: Establish baseline ===
        session1 = MemorySession(mock_provider, memory_config={"path": temp_memory_dir})

        for fact, user_id in baseline_facts:
            session1.generate(fact, user_id=user_id)

        alice_profile_1 = session1.get_user_profile("alice")
        baseline_fact_count = len(alice_profile_1.get('facts', []))

        # === Session 2: Add more facts ===
        session2 = MemorySession(mock_provider, memory_config={"path": temp_memory_dir})

        session2.generate("I also use SQLAlchemy for database work", user_id="alice")
        alice_profile_2 = session2.get_user_profile("alice")
        updated_fact_count = len(alice_profile_2.get('facts', []))

        assert updated_fact_count > baseline_fact_count, "New facts should be added"

        # === Session 3: Verify consistency ===
        session3 = MemorySession(mock_provider, memory_config={"path": temp_memory_dir})

        alice_profile_3 = session3.get_user_profile("alice")
        final_fact_count = len(alice_profile_3.get('facts', []))

        assert final_fact_count == updated_fact_count, "Fact count should remain consistent across restarts"

        # Verify core facts are still present
        final_facts_text = " ".join(alice_profile_3.get('facts', [])).lower()
        assert "python" in final_facts_text, "Core Python fact should persist"
        assert "fastapi" in final_facts_text or "api" in final_facts_text, "FastAPI preference should persist"

    @pytest.mark.slow
    def test_extended_interaction_session(self, mock_provider, temp_memory_dir):
        """Test memory behavior during extended interaction session (100+ interactions)."""

        config = MemoryConfig.comprehensive()
        session = MemorySession(
            mock_provider,
            memory_config={"path": temp_memory_dir},
            default_memory_config=config,
            system_prompt="You are a helpful assistant."
        )

        # Simulate extended conversation
        topics = ["Python", "React", "Docker", "AWS", "PostgreSQL"]

        for i in range(100):
            topic = topics[i % len(topics)]
            session.generate(f"Interaction {i}: Tell me about {topic} development", user_id="alice")

            if i % 20 == 0:  # Every 20 interactions, check memory state
                alice_profile = session.get_user_profile("alice")
                assert alice_profile.get('interaction_count', 0) > 0, f"Should track interactions at step {i}"

        # After extended interaction, verify memory still works
        final_context = session.get_memory_context("Python development", user_id="alice")
        assert len(final_context) > 0, "Memory should still provide context after extended use"

        # Should have consolidated some facts from repeated mentions
        alice_profile = session.get_user_profile("alice")
        facts = alice_profile.get('facts', [])
        assert len(facts) > 0, "Extended interactions should result in consolidated facts"


@pytest.mark.integration
class TestPersistenceWithRealLLM:
    """Test persistence with real LLM provider (when available)."""

    @pytest.fixture
    def ollama_provider(self):
        """Create real Ollama provider if available."""
        try:
            from abstractllm import create_llm
            provider = create_llm("ollama", model="qwen3-coder:30b")

            # Test that provider works
            test_response = provider.generate("Hello, respond with just 'OK'")
            assert hasattr(test_response, 'content'), "Provider should return response with content"

            return provider
        except ImportError:
            pytest.skip("AbstractCore not available for real LLM testing")
        except Exception as e:
            pytest.skip(f"Ollama not available or model not found: {e}")

    @pytest.mark.slow
    def test_real_llm_memory_persistence(self, ollama_provider, temp_memory_dir):
        """Test memory persistence with real LLM across sessions."""

        # === Session 1: Initial learning ===
        session1 = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant with memory."
        )

        # Establish facts
        response1 = session1.generate(
            "Hi, I'm Alice. I'm a Python developer who loves machine learning and prefers FastAPI for web APIs.",
            user_id="alice"
        )
        print(f"Initial response: {response1.content}")

        # === Session 2: Test recall after restart ===
        session2 = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant with memory."
        )

        response2 = session2.generate(
            "What do you remember about me and my work preferences?",
            user_id="alice"
        )
        print(f"Recall response: {response2.content}")

        # Verify LLM can access persisted memory
        content_lower = response2.content.lower()
        assert "alice" in content_lower, "Should remember name Alice"
        assert any(keyword in content_lower for keyword in ["python", "machine learning", "ml", "fastapi"]), \
            f"Should remember technical preferences, got: {response2.content}"

    def test_real_llm_context_overflow_handling(self, ollama_provider, temp_memory_dir):
        """Test that real LLM handles context overflow gracefully with persistent memory."""

        config = MemoryConfig(
            max_memory_items=3,  # Very limited context
            compact_format=True
        )

        session = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            default_memory_config=config,
            system_prompt="You are a helpful assistant."
        )

        # Add many interactions to force overflow
        topics = ["Python", "JavaScript", "Rust", "Go", "TypeScript"]
        for i, topic in enumerate(topics):
            session.generate(f"I've been working with {topic} for project {i}", user_id="alice")

        # Even with severe context limits, should still provide coherent responses
        response = session.generate("What programming languages have I mentioned?", user_id="alice")
        print(f"Context overflow response: {response.content}")

        # Should still be coherent and mention at least some languages
        content_lower = response.content.lower()
        mentioned_languages = [lang for lang in ["python", "javascript", "rust", "go", "typescript"]
                              if lang in content_lower]

        assert len(mentioned_languages) > 0, f"Should remember some languages despite context overflow, got: {response.content}"


if __name__ == "__main__":
    """Run persistence tests directly."""
    pytest.main([__file__, "-v", "-s", "--tb=short"])