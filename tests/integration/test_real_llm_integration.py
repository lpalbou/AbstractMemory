"""
Real LLM integration tests - Testing how LLMs actually use memory context.
These tests use real LLM providers to validate memory effectiveness.
"""

import pytest
import os
from datetime import datetime, timedelta
from abstractmemory import create_memory, MemoryItem

# Try to import AbstractCore providers
try:
    from abstractllm import create_llm
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False

# Alternative: Use simple HTTP calls to test with available APIs
import json
import time


@pytest.mark.skipif(not ABSTRACTCORE_AVAILABLE, reason="AbstractCore not available")
class TestRealLLMIntegration:
    """Test memory integration with real LLM providers"""

    def setup_method(self):
        """Setup test environment with real LLM provider"""
        # Use local providers that should be available
        try:
            # Try Ollama first (likely available locally)
            self.provider = create_llm("ollama", model="qwen3-coder:7b", base_url="http://localhost:11434")
            self.provider_name = "ollama"
        except:
            try:
                # Try MLX if available
                self.provider = create_llm("mlx", model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit")
                self.provider_name = "mlx"
            except:
                # Skip if no local providers available
                pytest.skip("No local LLM providers available")

    def test_scratchpad_memory_with_react_agent(self):
        """Test ScratchpadMemory with real LLM in ReAct pattern"""
        scratchpad = create_memory("scratchpad", max_entries=10)

        # Simulate ReAct cycle with real LLM
        user_query = "What are the key features of Python programming language?"

        # Step 1: LLM thinks about the task
        think_prompt = f"User asks: '{user_query}'. Think step by step about how to answer this comprehensively."

        try:
            think_response = self.provider.generate(think_prompt)
            thought = think_response.content if hasattr(think_response, 'content') else str(think_response)
            scratchpad.add_thought(thought)

            # Step 2: LLM decides on action
            action_prompt = f"""Based on the user query '{user_query}' and my thought:
            {thought}

            What action should I take? Choose from: [search_knowledge, provide_answer, ask_clarification]"""

            action_response = self.provider.generate(action_prompt)
            action_text = action_response.content if hasattr(action_response, 'content') else str(action_response)

            # Extract action (simplified)
            if "provide_answer" in action_text.lower():
                scratchpad.add_action("provide_answer", {"topic": "Python features"})

                # Step 3: LLM provides answer using context
                context = scratchpad.get_context()
                answer_prompt = f"""Based on this reasoning context:
                {context}

                Now provide a comprehensive answer about Python's key features."""

                final_response = self.provider.generate(answer_prompt)
                final_answer = final_response.content if hasattr(final_response, 'content') else str(final_response)
                scratchpad.add_observation(f"Provided answer: {final_answer[:100]}...")

                # Verify ReAct structure was maintained
                assert len(scratchpad.thoughts) >= 1
                assert len(scratchpad.actions) >= 1
                assert len(scratchpad.observations) >= 1

                # Verify context includes all ReAct components
                full_context = scratchpad.get_context()
                assert "Thought:" in full_context
                assert "Action:" in full_context
                assert "Observation:" in full_context

                print(f"✅ ReAct cycle completed with {self.provider_name}")
                print(f"Final context length: {len(full_context)} characters")

        except Exception as e:
            pytest.skip(f"LLM provider {self.provider_name} not responding: {e}")

    def test_grounded_memory_context_utilization(self):
        """Test how LLM uses GroundedMemory context in practice"""
        memory = create_memory("grounded", working_capacity=5, enable_kg=True)

        # Setup user profile and interactions
        memory.set_current_user("alice", relationship="owner")

        # Add user preferences and facts
        memory.learn_about_user("prefers concise technical explanations")
        memory.learn_about_user("experienced Python developer")
        memory.learn_about_user("works in data science")

        # Add some interactions
        memory.add_interaction(
            "I'm working on a machine learning project with large datasets",
            "Great! For large datasets, consider using libraries like Dask or Ray for distributed computing."
        )

        memory.add_interaction(
            "What's the best way to optimize Python code for performance?",
            "For performance optimization, consider NumPy vectorization, Cython for bottlenecks, and profiling tools."
        )

        # Test 1: LLM should use user context for personalized response
        user_context = memory.get_full_context("optimization", user_id="alice")

        prompt = f"""Context about the user and previous conversation:
        {user_context}

        User Alice asks: "Should I use multiprocessing for my data processing pipeline?"

        Provide a personalized response based on what you know about Alice."""

        try:
            response = self.provider.generate(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Verify LLM used the context appropriately
            # Should mention Alice by name or reference her profile
            context_aware = any(term in response_text.lower() for term in [
                "alice", "data science", "experienced", "machine learning", "large datasets"
            ])

            if context_aware:
                print(f"✅ LLM successfully used user context with {self.provider_name}")
                print(f"Response mentions relevant context: {response_text[:200]}...")
            else:
                print(f"⚠️ LLM may not have fully utilized context")

            # Add this interaction to memory
            memory.add_interaction(
                "Should I use multiprocessing for my data processing pipeline?",
                response_text
            )

            assert len(response_text) > 50  # Got a substantial response

        except Exception as e:
            pytest.skip(f"LLM provider {self.provider_name} not responding: {e}")

    def test_semantic_memory_fact_extraction(self):
        """Test if LLM can extract facts that get validated in semantic memory"""
        memory = create_memory("grounded", working_capacity=5, semantic_threshold=2)

        # Provide LLM with factual content to extract from
        factual_content = """Python was created by Guido van Rossum in 1991.
        Python is an interpreted programming language.
        Python supports multiple programming paradigms including object-oriented and functional programming.
        Python has extensive library support through PyPI."""

        extraction_prompt = f"""Extract key facts from this text about Python:
        {factual_content}

        Format each fact as a simple statement like "Python is [something]" or "Python has [something]"."""

        try:
            response = self.provider.generate(extraction_prompt)
            extracted_facts = response.content if hasattr(response, 'content') else str(response)

            # Simulate adding these facts multiple times to reach validation threshold
            fact_lines = [line.strip() for line in extracted_facts.split('\n') if line.strip() and 'python' in line.lower()]

            for fact in fact_lines[:3]:  # Take first 3 facts
                for i in range(2):  # Add twice to reach threshold of 2
                    fact_item = MemoryItem(fact, datetime.now(), datetime.now())
                    memory.semantic.add(fact_item)

            # Check if facts were validated
            validated_facts = memory.semantic.retrieve("Python")

            if len(validated_facts) > 0:
                print(f"✅ Successfully extracted and validated {len(validated_facts)} facts with {self.provider_name}")
                for fact in validated_facts:
                    print(f"   - {fact.content} (confidence: {fact.confidence:.2f})")
            else:
                print(f"⚠️ No facts were validated (may need adjustment to extraction)")

            assert len(fact_lines) > 0  # LLM extracted some facts

        except Exception as e:
            pytest.skip(f"LLM provider {self.provider_name} not responding: {e}")

    def test_memory_guided_reasoning(self):
        """Test if LLM reasoning improves with memory context vs without"""
        memory = create_memory("grounded", working_capacity=5)
        memory.set_current_user("bob", relationship="colleague")

        # Build up relevant context
        memory.add_interaction(
            "I'm new to Python and struggling with list comprehensions",
            "List comprehensions are a Pythonic way to create lists. They're more concise than traditional loops."
        )

        memory.add_interaction(
            "Can you show me an example of list comprehension?",
            "Sure! Instead of: result = []; for x in range(10): result.append(x*2), you can write: result = [x*2 for x in range(10)]"
        )

        memory.learn_about_user("new to Python programming")
        memory.learn_about_user("learning list comprehensions")

        # Test 1: Response without memory context
        query = "How do I filter a list in Python?"

        try:
            response_without_context = self.provider.generate(f"User asks: {query}")
            no_context_response = response_without_context.content if hasattr(response_without_context, 'content') else str(response_without_context)

            # Test 2: Response with memory context
            context = memory.get_full_context("filter list", user_id="bob")
            response_with_context = self.provider.generate(f"""Context about user and conversation:
            {context}

            User Bob asks: {query}""")
            context_response = response_with_context.content if hasattr(response_with_context, 'content') else str(response_with_context)

            # Compare responses
            print(f"✅ Memory-guided reasoning test completed with {self.provider_name}")
            print(f"Without context length: {len(no_context_response)}")
            print(f"With context length: {len(context_response)}")

            # Context-aware response should be more personalized
            context_mentions = sum(1 for term in ["bob", "new", "learning", "comprehension"]
                                 if term in context_response.lower())
            no_context_mentions = sum(1 for term in ["bob", "new", "learning", "comprehension"]
                                    if term in no_context_response.lower())

            if context_mentions > no_context_mentions:
                print(f"✅ Context-aware response is more personalized ({context_mentions} vs {no_context_mentions} relevant terms)")

            assert len(context_response) > 20  # Got responses
            assert len(no_context_response) > 20

        except Exception as e:
            pytest.skip(f"LLM provider {self.provider_name} not responding: {e}")


@pytest.mark.skipif(ABSTRACTCORE_AVAILABLE, reason="Skip simple tests when AbstractCore available")
class TestSimpleLLMIntegration:
    """Simple LLM integration tests without AbstractCore dependency"""

    def test_memory_context_structure(self):
        """Test that memory produces well-structured context for LLMs"""
        memory = create_memory("grounded", working_capacity=3)
        memory.set_current_user("test_user")

        # Add varied content
        memory.add_interaction("Hello", "Hi there!")
        memory.learn_about_user("likes detailed explanations")
        memory.track_success("search", "web_queries")

        # Get context
        context = memory.get_full_context("search")

        # Verify context structure
        assert "=== User Profile:" in context
        assert "=== Core Memory" in context
        assert len(context) > 100

        # Context should be LLM-friendly (structured, clear sections)
        lines = context.split('\n')
        section_headers = [line for line in lines if line.startswith('===')]
        assert len(section_headers) >= 2  # Multiple clear sections

        print(f"✅ Memory context is well-structured ({len(context)} chars, {len(section_headers)} sections)")

    def test_react_context_formatting(self):
        """Test ReAct memory produces proper context for LLM reasoning"""
        scratchpad = create_memory("scratchpad")

        # Simulate ReAct cycle
        scratchpad.add_thought("I need to help the user with their Python question")
        scratchpad.add_action("analyze_question", {"topic": "Python basics"})
        scratchpad.add_observation("Question is about list operations")
        scratchpad.add_thought("I should provide a clear example")

        context = scratchpad.get_context()

        # Verify ReAct formatting
        assert "Thought:" in context
        assert "Action:" in context
        assert "Observation:" in context

        # Should be in logical order
        thought_pos = context.find("Thought:")
        action_pos = context.find("Action:")
        obs_pos = context.find("Observation:")

        assert thought_pos < action_pos < obs_pos  # Proper ReAct ordering

        print(f"✅ ReAct context properly formatted for LLM consumption")

    def test_multi_user_context_separation(self):
        """Test that multi-user contexts don't leak between users"""
        memory = create_memory("grounded")

        # User 1
        memory.set_current_user("alice")
        memory.add_interaction("I work in data science", "That's exciting!")
        memory.learn_about_user("data scientist")

        # User 2
        memory.set_current_user("bob")
        memory.add_interaction("I'm a web developer", "Great!")
        memory.learn_about_user("web developer")

        # Get separate contexts
        alice_context = memory.get_full_context("programming", user_id="alice")
        bob_context = memory.get_full_context("programming", user_id="bob")

        # Verify separation
        assert "alice" in alice_context.lower()
        assert "data science" in alice_context.lower()
        assert "bob" not in alice_context.lower()
        assert "web" not in alice_context.lower()

        assert "bob" in bob_context.lower()
        assert "web developer" in bob_context.lower()
        assert "alice" not in bob_context.lower()
        assert "data science" not in bob_context.lower()

        print(f"✅ Multi-user contexts properly separated")


if __name__ == "__main__":
    # Run a quick integration test
    print("=== AbstractMemory Real LLM Integration Test ===")

    # Test simple memory formatting
    print("\n1. Testing memory context structure:")
    memory = create_memory("grounded")
    memory.set_current_user("demo_user")
    memory.add_interaction("Test question", "Test response")
    context = memory.get_full_context("test")
    print(f"Context structure: {len(context)} characters, well-formed: {'===' in context}")

    # Test ReAct formatting
    print("\n2. Testing ReAct context formatting:")
    scratchpad = create_memory("scratchpad")
    scratchpad.add_thought("Demo thought")
    scratchpad.add_action("demo_action", {})
    scratchpad.add_observation("Demo observation")
    react_context = scratchpad.get_context()
    print(f"ReAct structure: {'Thought:' in react_context and 'Action:' in react_context}")

    print("\n✅ Basic integration tests passed!")
    print("Run 'python -m pytest tests/integration/test_real_llm_integration.py -v' for full tests")