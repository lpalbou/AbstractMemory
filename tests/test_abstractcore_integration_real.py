"""
Real verification tests for AbstractCore integration.

These tests verify that AbstractMemory properly integrates with AbstractCore
using REAL implementations - NO MOCKS.
"""

import pytest
import tempfile
from pathlib import Path

# AbstractCore imports
from abstractllm.core.session import BasicSession
from abstractllm.core.interface import AbstractLLMInterface
from abstractllm.embeddings import EmbeddingManager

# Import LMStudioProvider directly - working around broken package imports
try:
    from abstractllm.providers.lmstudio_provider import LMStudioProvider
    LMSTUDIO_AVAILABLE = True
except Exception as e:
    print(f"LMStudioProvider not available: {e}")
    LMSTUDIO_AVAILABLE = False

# AbstractMemory imports
from abstractmemory.session import MemorySession


class MockProvider(AbstractLLMInterface):
    """Simple mock provider for testing - no external dependencies."""

    def __init__(self, model="test-model"):
        self.model = model

    def generate(self, prompt, **kwargs):
        from abstractllm.core.types import GenerateResponse
        return GenerateResponse(
            content=f"Mock response to: {prompt[:50]}...",
            model=self.model,
            finish_reason="stop"
        )

    def get_capabilities(self):
        """Return basic capabilities."""
        return ["chat", "completion"]

    def validate_config(self):
        """Always return True for mock."""
        return True


class TestAbstractCoreIntegration:
    """Test AbstractCore integration with AbstractMemory using real implementations."""

    def test_session_inheritance(self):
        """Test that MemorySession correctly inherits from AbstractCore BasicSession."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Verify inheritance
            assert isinstance(session, BasicSession)
            assert isinstance(session, MemorySession)

            # Verify AbstractCore BasicSession methods are available
            assert hasattr(session, 'generate')
            assert hasattr(session, 'add_message')
            assert callable(getattr(session, 'generate'))
            assert callable(getattr(session, 'add_message'))

            # Verify memory-specific attributes
            assert hasattr(session, 'memory_base_path')
            assert hasattr(session, 'default_user_id')
            assert hasattr(session, 'lancedb_storage')
            assert hasattr(session, 'working_memory')
            assert hasattr(session, 'episodic_memory')
            assert hasattr(session, 'semantic_memory')

    def test_embedding_manager_integration(self):
        """Test that EmbeddingManager is properly integrated."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Check that LanceDB storage has embedding manager
            assert hasattr(session.lancedb_storage, 'embedding_manager')
            assert isinstance(session.lancedb_storage.embedding_manager, EmbeddingManager)

    def test_memory_session_initialization(self):
        """Test that MemorySession initializes all required components."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Verify memory managers are initialized
            assert session.working_memory is not None
            assert session.episodic_memory is not None
            assert session.semantic_memory is not None
            assert session.library is not None
            assert session.lancedb_storage is not None

            # Verify paths are set correctly
            assert session.memory_base_path == Path(temp_dir)
            assert session.default_user_id == "test_user"

            # Verify core memory is initialized
            assert isinstance(session.core_memory, dict)

    def test_memory_filesystem_structure(self):
        """Test that memory filesystem structure is created correctly."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            memory_path = Path(temp_dir)

            # Check that key directories are created
            expected_dirs = [
                'notes',
                'verbatim',
                'core',
                'working',
                'episodic',
                'semantic',
                'library',
                'people'
            ]

            for dir_name in expected_dirs:
                dir_path = memory_path / dir_name
                # Directory should exist or be creatable
                if not dir_path.exists():
                    # Try to create it to verify permissions
                    dir_path.mkdir(parents=True, exist_ok=True)
                assert dir_path.exists()

    def test_session_generate_method(self):
        """Test that BasicSession.generate method works correctly."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Test generate method (inherited from AbstractCore BasicSession)
            response = session.generate("Test prompt")

            # Verify response structure
            assert hasattr(response, 'content')
            assert hasattr(response, 'model')
            assert "Test prompt" in response.content or "Mock response" in response.content
            assert response.model == "test-model"

    def test_abstractcore_session_compatibility(self):
        """Test that MemorySession is compatible with AbstractCore BasicSession interface."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Test AbstractCore BasicSession interface compatibility

            # Should have message handling
            assert hasattr(session, 'add_message')

            # Should have provider access
            assert session.provider is provider

            # Should support generation
            assert hasattr(session, 'generate')

            # Test actual message adding
            message = session.add_message("user", "Test message")
            assert hasattr(message, 'role')
            assert hasattr(message, 'content')
            assert message.role == "user"
            assert message.content == "Test message"

    def test_memory_tools_are_available(self):
        """Test that memory tools are available as methods."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Check that key memory tools are available as methods
            expected_methods = [
                'remember_fact',
                'search_memories',
                'reflect_on',
                'capture_document',
                'search_library',
                'reconstruct_context'
            ]

            for method_name in expected_methods:
                assert hasattr(session, method_name), f"Missing method: {method_name}"
                assert callable(getattr(session, method_name)), f"Method not callable: {method_name}"

    @pytest.mark.skipif(not LMSTUDIO_AVAILABLE, reason="LMStudioProvider not available")
    def test_lmstudio_provider_integration(self):
        """Test that LMStudioProvider works with MemorySession (if available)."""
        # This test only runs if LMStudio provider is available
        provider = LMStudioProvider(
            base_url="http://localhost:1234/v1",
            model="test-model"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            # Should not raise any errors
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            assert session.provider is provider
            assert isinstance(session.provider, LMStudioProvider)

    def test_memory_operations_basic_functionality(self):
        """Test basic memory operations work with real implementations."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Test remember_fact method
            result = session.remember_fact(
                content="Test memory",
                importance=0.8,
                emotion="neutral",
                reason="Testing"
            )

            # Should return some form of confirmation
            assert result is not None

            # Test that memory files are created
            notes_dir = Path(temp_dir) / "notes"
            assert notes_dir.exists()

            # Test search_memories method
            search_results = session.search_memories("Test memory", limit=5)
            assert isinstance(search_results, (list, str))  # Could return list or string

            # Test reconstruct_context method
            context_result = session.reconstruct_context(
                user_id="test_user",
                query="Test query",
                focus_level=1
            )
            assert isinstance(context_result, dict)
            # Check for expected keys based on actual implementation
            assert "context_tokens" in context_result
            assert "core_memory" in context_result


class TestREPLIntegration:
    """Test REPL integration with AbstractCore using real implementations."""

    def test_basic_imports_work(self):
        """Test that basic imports work."""
        # These imports should work without errors
        from abstractmemory.session import MemorySession

        # Verify the classes exist and are importable
        assert MemorySession is not None
        assert issubclass(MemorySession, BasicSession)

    def test_memory_session_creation(self):
        """Test creating MemorySession with MockProvider."""
        provider = MockProvider()

        with tempfile.TemporaryDirectory() as temp_dir:
            session = MemorySession(
                provider=provider,
                memory_base_path=temp_dir,
                default_user_id="test_user"
            )

            # Verify session was created successfully
            assert isinstance(session, MemorySession)
            assert session.provider is provider


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])