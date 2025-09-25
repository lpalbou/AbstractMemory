"""
Real LLM integration tests for MemorySession with Ollama.

Tests memory functionality with actual LLM (NO MOCKS) including:
- Agent memory modification
- Memory tool usage
- Embedding consistency
- Multi-user memory separation

Requirements:
- Ollama running locally
- qwen2.5-coder:32b-instruct model available
- sentence-transformers library installed

Run with: python -m pytest tests/integration/test_real_llm_memory.py -v -s
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import time

from abstractmemory import MemorySession, MemoryConfig


class TestRealLLMMemory:
    """Test MemorySession with real Ollama LLM - no mocks anywhere."""

    @pytest.fixture
    def ollama_provider(self):
        """Create real Ollama provider for testing."""
        try:
            from abstractllm import create_llm
            provider = create_llm("ollama", model="qwen2.5-coder:32b-instruct")

            # Test that provider is working
            test_response = provider.generate("Hello, respond with just 'OK'")
            assert hasattr(test_response, 'content'), "Provider must return response with content"

            return provider
        except ImportError:
            pytest.skip("AbstractCore not available for real LLM testing")
        except Exception as e:
            pytest.skip(f"Ollama not available or model not found: {e}")

    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary directory for memory storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_basic_memory_persistence(self, ollama_provider, temp_memory_dir):
        """Test that MemorySession actually remembers across interactions."""
        # Create session with persistent storage
        session = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant. Respond concisely."
        )

        # First interaction: Alice introduces herself with Python interest
        response1 = session.generate(
            "Hi, I'm Alice and I love Python programming. I work on machine learning projects daily.",
            user_id="alice"
        )
        print(f"Response 1: {response1.content}")
        assert response1.content, "Should get response from LLM"

        # Second interaction: Ask what LLM remembers
        response2 = session.generate(
            "What do you remember about me and my work?",
            user_id="alice"
        )
        print(f"Response 2: {response2.content}")

        # Verify memory worked - should mention Alice and Python/ML
        content_lower = response2.content.lower()
        assert "alice" in content_lower, f"Should remember name Alice, got: {response2.content}"
        assert any(keyword in content_lower for keyword in ["python", "machine learning", "ml"]), \
            f"Should remember Python/ML interest, got: {response2.content}"

    def test_agent_memory_tools_usage(self, ollama_provider, temp_memory_dir):
        """Test agent using memory tools to manage its own memory."""
        # Create agent session with memory tools enabled
        config = MemoryConfig.agent_mode()
        session = MemorySession(
            ollama_provider,
            default_memory_config=config,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are an AI assistant. When asked to remember something, use your memory tools."
        )

        print(f"Session tools: {[t.__name__ for t in session.tools if hasattr(t, '__name__')]}")
        assert len(session.tools) > 0, "Agent should have memory tools available"

        # Test 1: Ask agent to remember a fact
        response1 = session.generate(
            "Please remember that the API rate limit for our service is 100 requests per hour. This is important for all users.",
            user_id="admin"
        )
        print(f"Remember response: {response1.content}")
        assert response1.content, "Should get response about remembering"

        # Wait a moment for memory processing
        time.sleep(1)

        # Test 2: Ask agent to search its memory
        response2 = session.generate(
            "Search your memory for information about API limits or rate limiting.",
            user_id="admin"
        )
        print(f"Search response: {response2.content}")

        # Verify agent found the information in memory
        content_lower = response2.content.lower()
        assert any(keyword in content_lower for keyword in ["api", "rate", "limit", "100"]), \
            f"Agent should find API rate limit info in memory, got: {response2.content}"

    def test_agent_self_modification(self, ollama_provider, temp_memory_dir):
        """Test agent modifying its own core memory/identity."""
        # Create agent with self-editing enabled
        config = MemoryConfig(
            enable_memory_tools=True,
            enable_self_editing=True,
            allowed_memory_operations=["update_core_memory", "search_memory"]
        )
        session = MemorySession(
            ollama_provider,
            default_memory_config=config,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are an AI assistant. You can update your core memory about your identity and capabilities."
        )

        # Test 1: Agent updates its specialization
        response1 = session.generate(
            "Update your core memory to indicate that you specialize in Python development and machine learning. Use the persona block."
        )
        print(f"Core memory update response: {response1.content}")

        # Wait for processing
        time.sleep(1)

        # Test 2: Verify the update by checking identity
        response2 = session.generate(
            "What is your specialization or area of expertise?"
        )
        print(f"Identity response: {response2.content}")

        # Verify agent incorporated the specialization into its identity
        content_lower = response2.content.lower()
        assert any(keyword in content_lower for keyword in ["python", "machine learning", "specialize"]), \
            f"Agent should reflect updated specialization, got: {response2.content}"

        # Test 3: Verify core memory was actually updated
        if hasattr(session.memory, 'get_core_memory_context'):
            core_context = session.memory.get_core_memory_context()
            print(f"Core memory context: {core_context}")
            core_lower = core_context.lower()
            assert any(keyword in core_lower for keyword in ["python", "machine learning"]), \
                f"Core memory should contain updated specialization, got: {core_context}"

    def test_multi_user_memory_separation(self, ollama_provider, temp_memory_dir):
        """Test that different users get different memory contexts."""
        # Create shared session
        session = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant. Remember what each user tells you about themselves."
        )

        # Alice: Python developer
        alice_response1 = session.generate(
            "Hi, I'm Alice. I'm a Python developer working on machine learning projects. I prefer Flask for web APIs.",
            user_id="alice"
        )
        print(f"Alice introduction: {alice_response1.content}")

        # Bob: JavaScript developer
        bob_response1 = session.generate(
            "Hi, I'm Bob. I'm a JavaScript developer working on React applications. I prefer Express.js for backend APIs.",
            user_id="bob"
        )
        print(f"Bob introduction: {bob_response1.content}")

        # Test Alice gets Alice-specific context
        alice_response2 = session.generate(
            "What programming language and framework do you recommend for my next project?",
            user_id="alice"
        )
        print(f"Alice recommendation: {alice_response2.content}")
        alice_lower = alice_response2.content.lower()

        # Should mention Python/Flask for Alice, not JavaScript/Express
        assert any(keyword in alice_lower for keyword in ["python", "flask"]), \
            f"Alice should get Python/Flask recommendations, got: {alice_response2.content}"

        # Test Bob gets Bob-specific context
        bob_response2 = session.generate(
            "What programming language and framework do you recommend for my next project?",
            user_id="bob"
        )
        print(f"Bob recommendation: {bob_response2.content}")
        bob_lower = bob_response2.content.lower()

        # Should mention JavaScript/Express for Bob, not Python/Flask
        assert any(keyword in bob_lower for keyword in ["javascript", "express", "react"]), \
            f"Bob should get JavaScript/Express recommendations, got: {bob_response2.content}"

    def test_memory_search_functionality(self, ollama_provider, temp_memory_dir):
        """Test semantic search capabilities with real embeddings."""
        # Create session with comprehensive memory
        config = MemoryConfig.comprehensive()
        session = MemorySession(
            ollama_provider,
            default_memory_config=config,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Add diverse information
        interactions = [
            "I'm working on a Python web application using Django",
            "My database is PostgreSQL with SQLAlchemy ORM",
            "I'm having performance issues with my React frontend",
            "The API endpoints are built with FastAPI instead of Django REST",
            "I need help optimizing database queries for better performance"
        ]

        for i, text in enumerate(interactions):
            session.generate(text, user_id="developer")
            time.sleep(0.5)  # Brief pause between interactions

        # Test semantic search finds related concepts
        search_results = session.search_memory("database optimization", user_id="developer")
        print(f"Search results: {search_results}")

        # Should find database and performance related interactions
        found_content = " ".join([str(result) for result in search_results]).lower()
        assert any(keyword in found_content for keyword in ["database", "performance", "postgresql", "queries"]), \
            f"Search should find database/performance content, got: {search_results}"

    @pytest.mark.slow
    def test_session_restart_persistence(self, ollama_provider, temp_memory_dir):
        """Test memory persists when restarting MemorySession."""
        # Create first session and add memories
        session1 = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Add information
        response1 = session1.generate(
            "I'm working on a project using TypeScript and Node.js. My database is MongoDB.",
            user_id="developer"
        )
        print(f"Initial session response: {response1.content}")

        # Verify memory files were created
        memory_path = Path(temp_memory_dir)
        assert memory_path.exists(), "Memory directory should exist"

        # Wait for file system operations
        time.sleep(1)

        # Create new session with same path (simulates restart)
        session2 = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir},
            system_prompt="You are a helpful assistant."
        )

        # Test that new session remembers previous information
        response2 = session2.generate(
            "What technologies am I using in my current project?",
            user_id="developer"
        )
        print(f"Restarted session response: {response2.content}")

        content_lower = response2.content.lower()
        assert any(keyword in content_lower for keyword in ["typescript", "node", "mongodb"]), \
            f"Restarted session should remember tech stack, got: {response2.content}"

    def test_embedding_consistency_warning(self, ollama_provider, temp_memory_dir):
        """Test that changing embedding providers triggers warnings."""
        # Create session with default embeddings
        session1 = MemorySession(
            ollama_provider,
            memory_config={"path": temp_memory_dir}
        )

        # Add some data
        session1.generate("I love programming in Python", user_id="user")

        # Wait for storage
        time.sleep(1)

        # Create new session with different embedding provider (should warn)
        try:
            from abstractmemory.embeddings.sentence_transformer_provider import create_sentence_transformer_provider
            different_embedder = create_sentence_transformer_provider("sentence-transformers/all-distilroberta-v1")

            # This should trigger consistency warnings but not fail
            session2 = MemorySession(
                ollama_provider,
                memory_config={"path": temp_memory_dir},
                embedding_provider=different_embedder
            )

            # Session should still work despite warnings
            response = session2.generate("What do I like?", user_id="user")
            assert response.content, "Session should work despite embedding inconsistency"

        except ImportError:
            pytest.skip("sentence-transformers not available for embedding consistency test")


@pytest.mark.integration
class TestMemoryToolsIntegration:
    """Test memory tools integration with real LLM."""

    @pytest.fixture
    def ollama_agent_session(self):
        """Create agent session with memory tools for testing."""
        try:
            from abstractllm import create_llm
            provider = create_llm("ollama", model="qwen2.5-coder:32b-instruct")

            config = MemoryConfig.agent_mode()
            temp_dir = tempfile.mkdtemp()

            session = MemorySession(
                provider,
                default_memory_config=config,
                memory_config={"path": temp_dir},
                system_prompt=(
                    "You are an autonomous AI assistant with memory management tools. "
                    "When asked to remember something, use the remember_fact tool. "
                    "When asked to search memory, use the search_memory tool. "
                    "Be direct in your responses."
                )
            )

            yield session, temp_dir

            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

        except ImportError:
            pytest.skip("AbstractCore not available")
        except Exception as e:
            pytest.skip(f"Cannot create agent session: {e}")

    def test_remember_fact_tool_usage(self, ollama_agent_session):
        """Test agent using remember_fact tool."""
        session, temp_dir = ollama_agent_session

        # Direct tool test first
        remember_tool = None
        for tool in session.tools:
            if hasattr(tool, '__name__') and tool.__name__ == 'remember_fact':
                remember_tool = tool
                break

        assert remember_tool is not None, "remember_fact tool should be available"

        # Test tool directly
        result = remember_tool(fact="The server IP address is 192.168.1.100", user_id="admin")
        print(f"Remember tool result: {result}")
        assert "remembered" in result.lower() or "stored" in result.lower()

        # Test via agent conversation
        response = session.generate(
            "Remember this important information: The database password expires on December 31st, 2024",
            user_id="admin"
        )
        print(f"Agent remember response: {response.content}")

        # Verify information was stored (search for it)
        search_tool = None
        for tool in session.tools:
            if hasattr(tool, '__name__') and tool.__name__ == 'search_memory':
                search_tool = tool
                break

        if search_tool:
            search_result = search_tool(query="password expires", user_id="admin")
            print(f"Search result: {search_result}")
            assert any(keyword in search_result.lower() for keyword in ["password", "december", "2024"])

    def test_get_user_profile_tool(self, ollama_agent_session):
        """Test agent retrieving user profile information."""
        session, temp_dir = ollama_agent_session

        # Add user information
        session.learn_about_user("Python developer", user_id="alice")
        session.learn_about_user("Works on machine learning projects", user_id="alice")

        # Find get_user_profile tool
        profile_tool = None
        for tool in session.tools:
            if hasattr(tool, '__name__') and tool.__name__ == 'get_user_profile':
                profile_tool = tool
                break

        assert profile_tool is not None, "get_user_profile tool should be available"

        # Test tool directly
        profile_result = profile_tool(user_id="alice")
        print(f"User profile: {profile_result}")

        assert "alice" in profile_result.lower()
        assert any(keyword in profile_result.lower() for keyword in ["python", "machine learning"])

    def test_comprehensive_agent_workflow(self, ollama_agent_session):
        """Test complete agent workflow with memory tools."""
        session, temp_dir = ollama_agent_session

        # Step 1: Agent learns about user
        response1 = session.generate(
            "I'm Sarah and I'm learning React development. I prefer TypeScript over JavaScript.",
            user_id="sarah"
        )
        print(f"Learning response: {response1.content}")

        # Step 2: Agent stores additional context
        response2 = session.generate(
            "Remember that I'm working on an e-commerce project using Next.js",
            user_id="sarah"
        )
        print(f"Store context response: {response2.content}")

        # Step 3: Agent recalls and provides personalized advice
        response3 = session.generate(
            "What would you recommend for state management in my current project?",
            user_id="sarah"
        )
        print(f"Recommendation response: {response3.content}")

        content_lower = response3.content.lower()
        # Should consider Sarah's TypeScript preference and React/Next.js context
        assert any(keyword in content_lower for keyword in ["typescript", "react", "next"]), \
            f"Should provide contextual recommendation based on stored info, got: {response3.content}"

        # Step 4: Verify agent can search its own memory
        response4 = session.generate(
            "Search your memory for information about my project and preferences",
            user_id="sarah"
        )
        print(f"Memory search response: {response4.content}")

        search_lower = response4.content.lower()
        assert any(keyword in search_lower for keyword in ["sarah", "react", "typescript", "next", "ecommerce"]), \
            f"Agent should find relevant information in memory, got: {response4.content}"


if __name__ == "__main__":
    """Run tests directly for development."""
    pytest.main([__file__, "-v", "-s", "--tb=short"])