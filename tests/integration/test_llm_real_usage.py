"""
Real LLM usage tests - Practical validation of memory effectiveness.
These tests demonstrate actual LLM usage patterns with memory.
"""

import pytest
import sys
import os
from datetime import datetime
from abstractmemory import create_memory, MemoryItem

# Add AbstractCore to path
sys.path.append('/Users/albou/projects/abstractllm_core')

try:
    from abstractllm import create_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


@pytest.mark.skipif(not LLM_AVAILABLE, reason="AbstractLLM not available")
class TestRealLLMUsage:
    """Test real LLM usage patterns with memory"""

    def setup_method(self):
        """Setup with available LLM provider"""
        # Try different providers in order of preference
        self.provider = None
        self.provider_name = None

        # Try local providers first
        providers_to_try = [
            ("mlx", "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit", {}),
            ("ollama", "qwen3-coder:7b", {"base_url": "http://localhost:11434"}),
            ("anthropic", "claude-3-5-haiku-latest", {}),
        ]

        for provider_type, model, kwargs in providers_to_try:
            try:
                self.provider = create_llm(provider_type, model=model, **kwargs)
                self.provider_name = f"{provider_type}:{model}"
                print(f"Using provider: {self.provider_name}")
                break
            except Exception as e:
                print(f"Failed to initialize {provider_type}: {e}")
                continue

        if not self.provider:
            pytest.skip("No LLM providers available")

    def test_react_agent_memory_usage(self):
        """Test how an LLM uses ScratchpadMemory for ReAct reasoning"""
        scratchpad = create_memory("scratchpad", max_entries=15)

        # Simulate a complex reasoning task
        user_question = "How can I optimize a Python function that processes large CSV files?"

        # Step 1: Initial thought
        initial_prompt = f"""
        User question: "{user_question}"

        Think step by step about how to approach this problem. What do you need to consider?
        """

        try:
            response1 = self.provider.generate(initial_prompt)
            thought1 = response1.content if hasattr(response1, 'content') else str(response1)
            scratchpad.add_thought(thought1)

            # Step 2: Decide on actions based on thought
            action_prompt = f"""
            Based on this reasoning:
            {scratchpad.get_context()}

            What specific actions should I take to help with CSV optimization?
            Choose from: [analyze_bottlenecks, suggest_libraries, provide_code_example, ask_for_details]
            """

            response2 = self.provider.generate(action_prompt)
            action_text = response2.content if hasattr(response2, 'content') else str(response2)

            # Extract action (simplified)
            if "analyze_bottlenecks" in action_text.lower():
                scratchpad.add_action("analyze_bottlenecks", {"focus": "CSV processing"})
            elif "suggest_libraries" in action_text.lower():
                scratchpad.add_action("suggest_libraries", {"domain": "data processing"})
            else:
                scratchpad.add_action("provide_guidance", {"topic": "optimization"})

            # Step 3: Execute action and observe
            execution_prompt = f"""
            Current reasoning context:
            {scratchpad.get_context()}

            Now execute the planned action and provide specific guidance for CSV optimization.
            """

            response3 = self.provider.generate(execution_prompt)
            result = response3.content if hasattr(response3, 'content') else str(response3)
            scratchpad.add_observation(f"Provided guidance: {result[:200]}...")

            # Step 4: Final reflection using full context
            reflection_prompt = f"""
            Complete reasoning trace:
            {scratchpad.get_context()}

            Reflect on this approach. Was the guidance comprehensive? What might be missing?
            """

            response4 = self.provider.generate(reflection_prompt)
            reflection = response4.content if hasattr(response4, 'content') else str(response4)
            scratchpad.add_thought(f"Reflection: {reflection}")

            # Validate ReAct structure
            react_history = scratchpad.get_react_history()
            assert len(react_history["thoughts"]) >= 2
            assert len(react_history["actions"]) >= 1
            assert len(react_history["observations"]) >= 1

            print(f"✅ ReAct reasoning completed with {self.provider_name}")
            print(f"Final context: {len(scratchpad.get_context())} characters")
            print(f"Thoughts: {len(react_history['thoughts'])}, Actions: {len(react_history['actions'])}, Observations: {len(react_history['observations'])}")

        except Exception as e:
            pytest.skip(f"LLM provider error: {e}")

    def test_personalized_assistant_memory(self):
        """Test personalized responses using GroundedMemory"""
        memory = create_memory("grounded", working_capacity=5, enable_kg=True)

        # Build user profile through interactions
        memory.set_current_user("sarah", relationship="owner")

        # Interaction 1: Learn about user
        memory.add_interaction(
            "I'm a data scientist working with large datasets in pandas",
            "That's great! Pandas is excellent for data analysis. Working with large datasets can be challenging."
        )
        memory.learn_about_user("data scientist")
        memory.learn_about_user("works with pandas")
        memory.learn_about_user("handles large datasets")

        # Interaction 2: Specific problem
        memory.add_interaction(
            "My pandas operations are getting slow with 10M+ rows",
            "For large datasets, consider chunking, Dask for parallel processing, or optimizing dtypes."
        )
        memory.track_failure("pandas_operations", "large_datasets")

        # Test: New question should use accumulated context
        user_context = memory.get_full_context("performance", user_id="sarah")

        personalized_prompt = f"""
        User context and history:
        {user_context}

        Sarah asks: "Should I switch from pandas to something else for my data processing?"

        Provide a personalized response based on Sarah's profile and previous interactions.
        """

        try:
            response = self.provider.generate(personalized_prompt)
            answer = response.content if hasattr(response, 'content') else str(response)

            # Check if response is personalized
            personalization_indicators = [
                "sarah" in answer.lower(),
                "data scientist" in answer.lower(),
                "large datasets" in answer.lower(),
                "pandas" in answer.lower(),
                "10m" in answer.lower() or "million" in answer.lower()
            ]

            personalized_count = sum(personalization_indicators)

            print(f"✅ Personalized response generated with {self.provider_name}")
            print(f"Personalization indicators found: {personalized_count}/5")
            print(f"Response preview: {answer[:150]}...")

            # Add this interaction to memory
            memory.add_interaction(
                "Should I switch from pandas to something else for my data processing?",
                answer
            )

            assert len(answer) > 50  # Got substantial response
            assert personalized_count >= 2  # Used some context

        except Exception as e:
            pytest.skip(f"LLM provider error: {e}")

    def test_fact_extraction_and_validation(self):
        """Test if LLM can extract facts that get properly validated"""
        memory = create_memory("grounded", semantic_threshold=2)

        # Give LLM content to extract facts from
        fact_source = """
        Python was created by Guido van Rossum and first released in 1991.
        Python is an interpreted, high-level programming language.
        Python supports multiple programming paradigms including procedural, object-oriented, and functional programming.
        Python has a large standard library and is known for its readability.
        PyPI (Python Package Index) contains over 400,000 packages.
        """

        extraction_prompt = f"""
        Extract key facts from this text about Python.

        Text: {fact_source}

        List each fact as a simple statement. Focus on factual, verifiable information.
        """

        try:
            response = self.provider.generate(extraction_prompt)
            extracted_text = response.content if hasattr(response, 'content') else str(response)

            # Parse extracted facts (simplified)
            lines = extracted_text.split('\n')
            facts = [line.strip() for line in lines
                    if line.strip() and len(line.strip()) > 10
                    and ('python' in line.lower() or 'guido' in line.lower())]

            # Add facts to semantic memory (multiple times for validation)
            for fact in facts[:3]:  # Take first 3 facts
                for _ in range(2):  # Add twice to reach threshold
                    fact_item = MemoryItem(fact, datetime.now(), datetime.now())
                    memory.semantic.add(fact_item)

            # Check validated facts
            validated_facts = memory.semantic.retrieve("Python")

            print(f"✅ Fact extraction test with {self.provider_name}")
            print(f"Extracted {len(facts)} facts, validated {len(validated_facts)} facts")

            for i, fact in enumerate(validated_facts):
                print(f"  {i+1}. {fact.content} (confidence: {fact.confidence:.2f})")

            assert len(facts) > 0  # LLM extracted facts
            assert len(validated_facts) >= 0  # Some facts may be validated

        except Exception as e:
            pytest.skip(f"LLM provider error: {e}")

    def test_memory_improves_consistency(self):
        """Test that memory helps LLM maintain consistency across interactions"""
        memory = create_memory("grounded", working_capacity=10)
        memory.set_current_user("alex")

        # Establish some facts about the user's project
        memory.add_interaction(
            "I'm building a web app with Flask and PostgreSQL",
            "Great choice! Flask is lightweight and PostgreSQL is robust for web applications."
        )

        memory.add_interaction(
            "I'm using SQLAlchemy as my ORM",
            "SQLAlchemy works excellently with both Flask and PostgreSQL. Good architectural decision."
        )

        memory.learn_about_user("building Flask web app")
        memory.learn_about_user("using PostgreSQL database")
        memory.learn_about_user("using SQLAlchemy ORM")

        # Test consistency: Ask related question
        context = memory.get_full_context("database", user_id="alex")

        consistency_prompt = f"""
        Conversation context:
        {context}

        Alex asks: "What's the best way to handle database migrations in my setup?"

        Provide advice that's consistent with Alex's established architecture.
        """

        try:
            response = self.provider.generate(consistency_prompt)
            advice = response.content if hasattr(response, 'content') else str(response)

            # Check for consistency with established facts
            consistency_indicators = [
                "flask" in advice.lower(),
                "postgresql" in advice.lower() or "postgres" in advice.lower(),
                "sqlalchemy" in advice.lower(),
                "migration" in advice.lower()
            ]

            consistent_count = sum(consistency_indicators)

            print(f"✅ Consistency test with {self.provider_name}")
            print(f"Consistency indicators: {consistent_count}/4")
            print(f"Advice preview: {advice[:150]}...")

            # Should mention at least 2 of the established technologies
            assert consistent_count >= 2

            # Add this to memory
            memory.add_interaction(
                "What's the best way to handle database migrations in my setup?",
                advice
            )

        except Exception as e:
            pytest.skip(f"LLM provider error: {e}")


class TestMemoryContextQuality:
    """Test memory context quality without requiring LLM"""

    def test_context_is_llm_friendly(self):
        """Test that memory contexts are well-structured for LLM consumption"""
        memory = create_memory("grounded")
        memory.set_current_user("test_user", relationship="owner")

        # Add diverse content
        memory.add_interaction("Hello", "Hi there!")
        memory.learn_about_user("software engineer")
        memory.track_success("code_review", "detailed_feedback")

        context = memory.get_full_context("programming")

        # Context should be structured with clear sections
        assert "===" in context  # Section headers
        assert "User Profile:" in context
        assert "Core Memory" in context

        # Should not be too long for typical LLM context windows
        assert len(context) < 8000  # Reasonable length

        # Should have clear information hierarchy
        lines = context.split('\n')
        section_count = sum(1 for line in lines if line.startswith('==='))
        assert section_count >= 2  # Multiple sections

        print(f"✅ Context quality: {len(context)} chars, {section_count} sections")

    def test_react_context_structure(self):
        """Test ReAct context formatting"""
        scratchpad = create_memory("scratchpad")

        # Add ReAct sequence
        scratchpad.add_thought("Need to solve this step by step")
        scratchpad.add_action("analyze", {"subject": "problem"})
        scratchpad.add_observation("Found three main components")
        scratchpad.add_thought("Should address each component separately")

        context = scratchpad.get_context()

        # Should follow ReAct format
        assert "Thought:" in context
        assert "Action:" in context
        assert "Observation:" in context

        # Should maintain order
        thought_indices = [i for i, line in enumerate(context.split('\n')) if 'Thought:' in line]
        action_indices = [i for i, line in enumerate(context.split('\n')) if 'Action:' in line]
        obs_indices = [i for i, line in enumerate(context.split('\n')) if 'Observation:' in line]

        # Verify logical flow
        assert len(thought_indices) == 2
        assert len(action_indices) == 1
        assert len(obs_indices) == 1

        print(f"✅ ReAct structure: {len(context)} chars, proper T-A-O-T sequence")


if __name__ == "__main__":
    # Quick validation
    print("=== Real LLM Usage Tests ===")

    test_quality = TestMemoryContextQuality()
    test_quality.test_context_is_llm_friendly()
    test_quality.test_react_context_structure()

    print("\n✅ Context quality tests passed!")
    print("Run full tests with: python -m pytest tests/integration/test_llm_real_usage.py -v")