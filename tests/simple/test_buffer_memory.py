"""
Tests for BufferMemory - Simple conversation buffer.
"""

import pytest
from datetime import datetime
from abstractmemory.simple import BufferMemory


class TestBufferMemory:
    """Test BufferMemory for simple chatbots"""

    def setup_method(self):
        """Setup test environment"""
        self.buffer = BufferMemory(max_messages=5)

    def test_initialization(self):
        """Test proper initialization"""
        assert len(self.buffer.messages) == 0

    def test_add_message(self):
        """Test adding messages to buffer"""
        self.buffer.add_message("user", "Hello")
        self.buffer.add_message("assistant", "Hi there!")

        assert len(self.buffer.messages) == 2
        messages = list(self.buffer.messages)
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"

    def test_message_timestamps(self):
        """Test that messages include timestamps"""
        self.buffer.add_message("user", "Test message")

        message = list(self.buffer.messages)[0]
        assert "timestamp" in message
        # Verify timestamp is recent (within last minute)
        timestamp_str = message["timestamp"]
        timestamp = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        assert (now - timestamp).total_seconds() < 60

    def test_get_messages_for_llm(self):
        """Test getting messages in LLM format"""
        self.buffer.add_message("user", "What's the weather?")
        self.buffer.add_message("assistant", "I don't have weather data")

        llm_messages = self.buffer.get_messages()

        assert len(llm_messages) == 2
        assert llm_messages[0]["role"] == "user"
        assert llm_messages[0]["content"] == "What's the weather?"
        assert "timestamp" not in llm_messages[0]  # Cleaned for LLM

    def test_get_context_formatting(self):
        """Test conversation context formatting"""
        self.buffer.add_message("user", "Hi")
        self.buffer.add_message("assistant", "Hello!")
        self.buffer.add_message("user", "How are you?")

        context = self.buffer.get_context()
        lines = context.split('\n')

        assert len(lines) == 3
        assert "user: Hi" in lines
        assert "assistant: Hello!" in lines
        assert "user: How are you?" in lines

    def test_get_context_with_limit(self):
        """Test context with message limit"""
        for i in range(4):
            self.buffer.add_message("user", f"Message {i}")

        context = self.buffer.get_context(last_n=2)
        lines = context.split('\n')

        assert len(lines) == 2
        assert "Message 2" in context
        assert "Message 3" in context
        assert "Message 0" not in context

    def test_clear_functionality(self):
        """Test clearing message buffer"""
        self.buffer.add_message("user", "Test")
        self.buffer.add_message("assistant", "Response")

        assert len(self.buffer.messages) == 2

        self.buffer.clear()

        assert len(self.buffer.messages) == 0

    def test_bounded_buffer_overflow(self):
        """Test buffer respects size limits"""
        buffer = BufferMemory(max_messages=3)

        # Add more messages than capacity
        for i in range(5):
            buffer.add_message("user", f"Message {i}")

        # Should only keep last 3 messages
        assert len(buffer.messages) == 3
        messages = buffer.get_messages()

        # Verify it kept the most recent messages
        assert any("Message 2" in msg["content"] for msg in messages)
        assert any("Message 3" in msg["content"] for msg in messages)
        assert any("Message 4" in msg["content"] for msg in messages)
        assert not any("Message 0" in msg["content"] for msg in messages)
        assert not any("Message 1" in msg["content"] for msg in messages)

    def test_conversation_flow(self):
        """Test realistic conversation flow"""
        # Simulate chatbot conversation
        conversation = [
            ("user", "What is Python?"),
            ("assistant", "Python is a programming language"),
            ("user", "What makes it popular?"),
            ("assistant", "It's simple and versatile"),
            ("user", "Can you give an example?"),
            ("assistant", "print('Hello, World!')")
        ]

        for role, content in conversation:
            self.buffer.add_message(role, content)

        # Test full context (only shows last 5 messages due to capacity)
        context = self.buffer.get_context()
        # First message dropped due to capacity (max_messages=5)
        assert "What makes it popular?" in context
        assert "print('Hello, World!')" in context

        # Test LLM messages format
        llm_messages = self.buffer.get_messages()
        assert len(llm_messages) == 5  # 5 because buffer has max_messages=5, first message dropped

        # Verify messages are the last 5
        contents = [msg["content"] for msg in llm_messages]
        assert "What is Python?" not in contents  # First message was dropped
        assert "print('Hello, World!')" in contents