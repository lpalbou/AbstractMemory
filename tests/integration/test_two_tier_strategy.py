"""
Integration test for the two-tier memory strategy.
Tests the complete memory selection based on agent purpose.
"""

import pytest
from datetime import datetime
from abstractmemory import create_memory


class TestTwoTierMemoryStrategy:
    """Test the two-tier memory strategy for different agent types"""

    def test_react_agent_scratchpad_memory(self):
        """Test ScratchpadMemory for ReAct agents"""
        # For a ReAct agent doing web search
        scratchpad = create_memory("scratchpad", max_entries=20)

        # Simulate ReAct cycle: Thought → Action → Observation → Thought
        scratchpad.add_thought("User wants to know about Python memory management")
        scratchpad.add_action("search", {"query": "Python garbage collection"})
        scratchpad.add_observation("Found info about reference counting and gc module")
        scratchpad.add_thought("Should explain both reference counting and cyclic GC")
        scratchpad.add_action("explain", {"topic": "Python memory management"})

        # Verify ReAct structure
        history = scratchpad.get_react_history()
        assert len(history["thoughts"]) == 2
        assert len(history["actions"]) == 2
        assert len(history["observations"]) == 1

        # Get context for next iteration
        context = scratchpad.get_context()
        assert "memory management" in context
        assert "Thought:" in context
        assert "Action:" in context
        assert "Observation:" in context

    def test_simple_chatbot_buffer_memory(self):
        """Test BufferMemory for simple chatbots"""
        # For a simple Q&A chatbot
        buffer = create_memory("buffer", max_messages=50)

        # Simulate conversation
        conversation = [
            ("user", "What is Python?"),
            ("assistant", "Python is a high-level programming language"),
            ("user", "What makes it popular?"),
            ("assistant", "Python is popular for its simplicity and versatility"),
            ("user", "Can you give an example?"),
            ("assistant", "print('Hello, World!')")
        ]

        for role, content in conversation:
            buffer.add_message(role, content)

        # Get messages for LLM
        llm_messages = buffer.get_messages()
        assert len(llm_messages) == 6
        assert all("timestamp" not in msg for msg in llm_messages)  # Clean format

        # Get conversation context
        context = buffer.get_context()
        assert "What is Python?" in context
        assert "print('Hello, World!')" in context

    def test_autonomous_agent_grounded_memory(self):
        """Test GroundedMemory for autonomous agents with user tracking"""
        # For a personal assistant with multi-user support
        grounded = create_memory("grounded", working_capacity=10, enable_kg=True)

        # Test multi-user scenarios
        # User 1: Alice (owner)
        grounded.set_current_user("alice", relationship="owner")
        grounded.add_interaction(
            "My name is Alice and I love Python programming",
            "Nice to meet you, Alice! Python is excellent for many applications."
        )
        grounded.learn_about_user("loves Python programming")

        # User 2: Bob (colleague)
        grounded.set_current_user("bob", relationship="colleague")
        grounded.add_interaction(
            "I'm Bob and I prefer Java for enterprise development",
            "Java is indeed powerful for enterprise applications, Bob."
        )
        grounded.learn_about_user("prefers Java for enterprise")

        # Test user-specific context
        alice_context = grounded.get_full_context("programming", user_id="alice")
        bob_context = grounded.get_full_context("programming", user_id="bob")

        # Alice's context should mention Python
        assert "alice" in alice_context.lower()
        assert "python" in alice_context.lower()

        # Bob's context should mention Java
        assert "bob" in bob_context.lower()
        assert "java" in bob_context.lower()

        # Contexts should be different (personalized)
        assert alice_context != bob_context

    def test_memory_type_selection_based_on_purpose(self):
        """Test that memory selection matches agent purpose"""

        # Simple task agent → ScratchpadMemory
        task_memory = create_memory("scratchpad")
        from abstractmemory.simple import ScratchpadMemory
        assert isinstance(task_memory, ScratchpadMemory)

        # Simple chatbot → BufferMemory
        chat_memory = create_memory("buffer")
        from abstractmemory.simple import BufferMemory
        assert isinstance(chat_memory, BufferMemory)

        # Autonomous agent → GroundedMemory
        autonomous_memory = create_memory("grounded")
        from abstractmemory import GroundedMemory
        assert isinstance(autonomous_memory, GroundedMemory)

    def test_no_over_engineering_for_simple_agents(self):
        """Test that simple agents don't have unnecessary complexity"""

        # ReAct agent: minimal, efficient
        react_memory = create_memory("scratchpad", max_entries=10)

        # Should be lightweight
        assert hasattr(react_memory, 'add_thought')
        assert hasattr(react_memory, 'add_action')
        assert hasattr(react_memory, 'add_observation')
        assert hasattr(react_memory, 'get_context')

        # Should NOT have complex features
        assert not hasattr(react_memory, 'consolidate_memories')
        assert not hasattr(react_memory, 'track_failure')
        assert not hasattr(react_memory, 'kg')  # No knowledge graph

        # Chatbot: simple conversation tracking
        chat_memory = create_memory("buffer", max_messages=20)

        # Should have basic message management
        assert hasattr(chat_memory, 'add_message')
        assert hasattr(chat_memory, 'get_messages')
        assert hasattr(chat_memory, 'get_context')

        # Should NOT have complex features
        assert not hasattr(chat_memory, 'set_current_user')
        assert not hasattr(chat_memory, 'episodic')
        assert not hasattr(chat_memory, 'semantic')

    def test_full_features_for_autonomous_agents(self):
        """Test that autonomous agents get full memory capabilities"""

        autonomous_memory = create_memory("grounded", enable_kg=True)

        # Should have all memory tiers
        assert hasattr(autonomous_memory, 'core')  # Core memory (identity)
        assert hasattr(autonomous_memory, 'semantic')  # Validated facts
        assert hasattr(autonomous_memory, 'working')  # Recent context
        assert hasattr(autonomous_memory, 'episodic')  # Event archive
        assert hasattr(autonomous_memory, 'kg')  # Knowledge graph

        # Should have relational grounding
        assert hasattr(autonomous_memory, 'set_current_user')
        assert hasattr(autonomous_memory, 'user_profiles')
        assert hasattr(autonomous_memory, 'get_user_context')

        # Should have learning capabilities
        assert hasattr(autonomous_memory, 'track_failure')
        assert hasattr(autonomous_memory, 'track_success')
        assert hasattr(autonomous_memory, 'learn_about_user')
        assert hasattr(autonomous_memory, 'consolidate_memories')

        # Should have temporal grounding
        assert hasattr(autonomous_memory, 'add_interaction')
        assert hasattr(autonomous_memory, 'get_full_context')

    def test_performance_characteristics(self):
        """Test performance characteristics of different memory types"""
        import time

        # Simple memory should be very fast
        scratchpad = create_memory("scratchpad")

        start_time = time.time()
        for i in range(100):
            scratchpad.add_thought(f"Thought {i}")
        scratchpad_time = time.time() - start_time

        # Buffer memory should also be fast
        buffer = create_memory("buffer")

        start_time = time.time()
        for i in range(100):
            buffer.add_message("user", f"Message {i}")
        buffer_time = time.time() - start_time

        # Both should be very fast (under 1 second for 100 operations)
        assert scratchpad_time < 1.0
        assert buffer_time < 1.0

        # Complex memory operations should still be reasonable
        grounded = create_memory("grounded", enable_kg=True)

        start_time = time.time()
        for i in range(10):  # Fewer operations for complex memory
            grounded.add_interaction(f"Input {i}", f"Response {i}")
        grounded_time = time.time() - start_time

        # Should complete 10 operations in reasonable time
        assert grounded_time < 5.0

    def test_memory_capacity_and_consolidation(self):
        """Test memory capacity management across types"""

        # Simple memories have capacity limits
        scratchpad = create_memory("scratchpad", max_entries=5)

        # Add more than capacity
        for i in range(10):
            scratchpad.add_thought(f"Thought {i}")

        # Should respect capacity (bounded deque)
        assert len(scratchpad) == 5

        # Buffer memory also bounded
        buffer = create_memory("buffer", max_messages=3)

        for i in range(6):
            buffer.add_message("user", f"Message {i}")

        assert len(buffer.messages) == 3

        # Grounded memory has intelligent consolidation
        grounded = create_memory("grounded", working_capacity=3)

        # Fill working memory
        for i in range(5):
            grounded.add_interaction(f"Input {i}", f"Response {i}")

        # Should have triggered consolidation
        assert len(grounded.working.items) <= 3

    def test_real_world_usage_patterns(self):
        """Test realistic usage patterns for each memory type"""

        # Summarizer agent (task-specific)
        summarizer_memory = create_memory("scratchpad")

        # Simulate document summarization task
        summarizer_memory.add_thought("Need to summarize research paper")
        summarizer_memory.add_action("read_document", {"file": "paper.pdf"})
        summarizer_memory.add_observation("Paper discusses machine learning techniques")
        summarizer_memory.add_thought("Focus on key findings and methodology")
        summarizer_memory.add_action("extract_key_points", {"sections": ["results", "conclusions"]})

        context = summarizer_memory.get_context()
        assert "summarize" in context
        assert "key findings" in context

        # Customer service chatbot (simple)
        service_memory = create_memory("buffer")

        # Simulate customer interaction
        service_memory.add_message("user", "I have a problem with my order")
        service_memory.add_message("assistant", "I'd be happy to help. What's your order number?")
        service_memory.add_message("user", "Order #12345")
        service_memory.add_message("assistant", "Let me look that up for you")

        messages = service_memory.get_messages()
        assert len(messages) == 4
        assert "order" in str(messages)

        # Personal assistant (autonomous)
        assistant_memory = create_memory("grounded", enable_kg=True)

        # Simulate personal assistant learning about user
        assistant_memory.set_current_user("john", relationship="owner")
        assistant_memory.add_interaction(
            "Schedule a meeting with the dev team for tomorrow at 2pm",
            "I've scheduled a meeting with the development team for tomorrow at 2:00 PM."
        )
        assistant_memory.learn_about_user("works in software development")
        assistant_memory.track_success("schedule_meeting", "calendar_access_available")

        # Later interaction
        context = assistant_memory.get_full_context("meeting")
        assert "john" in context.lower()
        assert "development" in context.lower() or "dev" in context.lower()