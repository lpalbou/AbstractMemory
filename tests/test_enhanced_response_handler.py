"""
Tests for the enhanced response handler with AbstractCore integration.
"""

import pytest
import tempfile
import json
from pathlib import Path

# AbstractCore imports
from abstractllm.core.interface import AbstractLLMInterface
from abstractllm.core.types import GenerateResponse

# AbstractMemory imports
from abstractmemory.response_handler import EnhancedMemoryResponseHandler
from abstractmemory.memory_response_models import MemoryResponse, MemoryAction, EmotionalResonance


class MockProvider(AbstractLLMInterface):
    """Simple mock provider for testing."""

    def __init__(self, model="test-model"):
        self.model = model

    def generate(self, prompt, **kwargs):
        return GenerateResponse(
            content=f"Mock response to: {prompt[:50]}...",
            model=self.model,
            finish_reason="stop"
        )

    def get_capabilities(self):
        return ["chat", "completion"]

    def validate_config(self):
        return True


class TestEnhancedResponseHandler:
    """Test the enhanced response handler."""

    def test_pydantic_models_validation(self):
        """Test that our Pydantic models work correctly."""
        # Test MemoryAction model
        action_data = {
            "action": "remember",
            "content": "Test memory",
            "importance": 0.8,
            "emotion": "positive",
            "reason": "Testing"
        }
        action = MemoryAction(**action_data)
        assert action.action == "remember"
        assert action.content == "Test memory"
        assert action.importance == 0.8

        # Test EmotionalResonance model
        emotion_data = {
            "importance": 0.9,
            "alignment_with_values": 0.7,
            "reason": "This aligns with my values"
        }
        emotion = EmotionalResonance(**emotion_data)
        assert emotion.importance == 0.9
        assert emotion.alignment_with_values == 0.7

        # Test MemoryResponse model
        response_data = {
            "answer": "Test answer",
            "experiential_note": "I found this interesting",
            "memory_actions": [action_data],
            "emotional_resonance": emotion_data
        }
        response = MemoryResponse(**response_data)
        assert response.answer == "Test answer"
        assert len(response.memory_actions) == 1
        assert response.emotional_resonance.importance == 0.9

    def test_handler_initialization(self):
        """Test that the handler initializes correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = EnhancedMemoryResponseHandler(
                memory_session=None,
                base_path=Path(temp_dir)
            )

            assert handler.memory_session is None
            assert handler.base_path == Path(temp_dir)
            assert handler.structured_handler is not None

    def test_process_response_with_valid_json(self):
        """Test processing a valid JSON response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = EnhancedMemoryResponseHandler(
                memory_session=None,
                base_path=Path(temp_dir)
            )

            # Valid JSON response
            llm_output = json.dumps({
                "answer": "This is a test response",
                "experiential_note": "I found this interaction interesting",
                "memory_actions": [],
                "unresolved_questions": ["What happens next?"],
                "emotional_resonance": {
                    "importance": 0.8,
                    "alignment_with_values": 0.9,
                    "reason": "This aligns with my testing values"
                }
            })

            context = {
                "user_id": "test_user",
                "location": "test_location",
                "timestamp": "2024-01-01T12:00:00"
            }

            result = handler.process_response(llm_output, context)

            assert result["answer"] == "This is a test response"
            assert result["experiential_note"] == "I found this interaction interesting"
            assert len(result["unresolved_questions"]) == 1
            assert result["validation_success"] is True

    def test_process_response_with_invalid_json(self):
        """Test processing an invalid JSON response (fallback to legacy)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = EnhancedMemoryResponseHandler(
                memory_session=None,
                base_path=Path(temp_dir)
            )

            # Invalid JSON - should trigger legacy parsing
            llm_output = "This is not JSON but should be handled gracefully"

            context = {
                "user_id": "test_user",
                "location": "test_location"
            }

            result = handler.process_response(llm_output, context)

            assert result["answer"] == llm_output
            assert result["validation_success"] is False
            assert "fallback_reason" in result

    def test_process_response_with_legacy_format(self):
        """Test processing response with legacy JSON format embedded in text."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = EnhancedMemoryResponseHandler(
                memory_session=None,
                base_path=Path(temp_dir)
            )

            # JSON embedded in code block
            llm_output = '''Here's my response:

```json
{
    "answer": "Legacy format response",
    "experiential_note": "This is embedded JSON",
    "memory_actions": [],
    "emotional_resonance": {
        "importance": 0.5,
        "alignment_with_values": 0.6,
        "reason": "Testing legacy format"
    }
}
```

That's my structured response.'''

            context = {"user_id": "test_user"}

            result = handler.process_response(llm_output, context)

            assert result["answer"] == "Legacy format response"
            assert result["experiential_note"] == "This is embedded JSON"
            # This should work with either validation or legacy parsing

    def test_memory_action_execution(self):
        """Test that memory actions are executed correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock memory session
            class MockMemorySession:
                def remember_fact(self, **kwargs):
                    return "test_memory_id_123"

            mock_session = MockMemorySession()
            handler = EnhancedMemoryResponseHandler(
                memory_session=mock_session,
                base_path=Path(temp_dir)
            )

            llm_output = json.dumps({
                "answer": "I'll remember this",
                "memory_actions": [{
                    "action": "remember",
                    "content": "Important test information",
                    "importance": 0.9,
                    "emotion": "curious",
                    "reason": "This is significant for testing"
                }]
            })

            context = {"user_id": "test_user"}
            result = handler.process_response(llm_output, context)

            assert len(result["memory_actions_executed"]) == 1
            action_result = result["memory_actions_executed"][0]
            assert action_result["action"] == "remember"
            assert action_result["result"]["status"] == "success"
            assert "test_memory_id_123" in action_result["result"]["memory_id"]

    def test_experiential_note_saving(self):
        """Test that experiential notes are saved correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = EnhancedMemoryResponseHandler(
                memory_session=None,
                base_path=Path(temp_dir)
            )

            llm_output = json.dumps({
                "answer": "Test response",
                "experiential_note": "This is my personal reflection on the interaction",
                "emotional_resonance": {
                    "importance": 0.8,
                    "alignment_with_values": 0.7,
                    "reason": "Testing note saving"
                }
            })

            from datetime import datetime
            context = {
                "user_id": "test_user",
                "location": "test_location",
                "timestamp": datetime.now(),
                "interaction_id": "test_interaction_123"
            }

            result = handler.process_response(llm_output, context)

            # Check that note ID was generated
            assert result["experiential_note_id"] is not None

            # Check that notes directory was created
            notes_dir = Path(temp_dir) / "notes"
            assert notes_dir.exists()

            # Check that a note file was created (somewhere in the date hierarchy)
            note_files = list(notes_dir.rglob("*.md"))
            assert len(note_files) > 0

            # Check note content
            note_file = note_files[0]
            with open(note_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "This is my personal reflection" in content
                assert "AbstractCore StructuredOutputHandler" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])