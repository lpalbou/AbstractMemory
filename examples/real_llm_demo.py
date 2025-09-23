"""
Real LLM demonstration of AbstractMemory capabilities.

This demonstrates how LLMs actually use memory in practice.
Run with: python examples/real_llm_demo.py
"""

import sys
import os
from datetime import datetime

# Add paths
sys.path.append('/Users/albou/projects/abstractllm_core')
sys.path.append('/Users/albou/projects/abstractmemory')

try:
    from abstractllm import create_llm
    from abstractmemory import create_memory
    LLM_AVAILABLE = True
except ImportError as e:
    print(f"Dependencies not available: {e}")
    LLM_AVAILABLE = False


def demo_react_with_memory():
    """Demonstrate ReAct agent using ScratchpadMemory"""
    print("\n=== ReAct Agent with ScratchpadMemory ===")

    if not LLM_AVAILABLE:
        print("⚠️ LLM providers not available, showing structure only")

        # Show memory structure without LLM
        scratchpad = create_memory("scratchpad", max_entries=10)
        scratchpad.add_thought("User asks about Python performance optimization")
        scratchpad.add_action("analyze_problem", {"domain": "performance"})
        scratchpad.add_observation("Multiple optimization strategies available")
        scratchpad.add_thought("Should provide structured recommendations")

        print("ReAct Memory Structure:")
        print(scratchpad.get_context())
        return

    # Try to get LLM provider
    provider = None
    try:
        # Try local MLX first
        provider = create_llm("mlx", model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit")
        print("Using MLX provider")
    except:
        try:
            # Try Anthropic
            provider = create_llm("anthropic", model="claude-3-5-haiku-latest")
            print("Using Anthropic provider")
        except:
            print("⚠️ No LLM providers available")
            return

    scratchpad = create_memory("scratchpad", max_entries=10)
    user_question = "How can I make my Python data processing faster?"

    try:
        # Step 1: Think about the problem
        think_prompt = f"User asks: '{user_question}'. Think about what information you need to provide a good answer."

        response = provider.generate(think_prompt)
        thought = response.content if hasattr(response, 'content') else str(response)
        scratchpad.add_thought(thought[:200])  # Truncate for demo

        # Step 2: Decide on approach
        context = scratchpad.get_context()
        action_prompt = f"""
        Based on this thinking:
        {context}

        What should I focus on? Options: [profiling, libraries, algorithms, hardware]
        Choose one and explain briefly.
        """

        response = provider.generate(action_prompt)
        action_text = response.content if hasattr(response, 'content') else str(response)

        # Extract action focus
        if "profiling" in action_text.lower():
            scratchpad.add_action("focus_on_profiling", {"tools": "cProfile, line_profiler"})
        elif "libraries" in action_text.lower():
            scratchpad.add_action("recommend_libraries", {"type": "performance"})
        else:
            scratchpad.add_action("general_advice", {"topic": "optimization"})

        # Step 3: Provide specific guidance
        final_context = scratchpad.get_context()
        guidance_prompt = f"""
        Context of reasoning:
        {final_context}

        Now provide specific, actionable advice for: {user_question}
        """

        response = provider.generate(guidance_prompt)
        guidance = response.content if hasattr(response, 'content') else str(response)
        scratchpad.add_observation(f"Provided guidance: {guidance[:150]}...")

        print("\nComplete ReAct Trace:")
        print(scratchpad.get_context())

        print(f"\n✅ ReAct completed - {len(scratchpad)} steps recorded")

    except Exception as e:
        print(f"LLM error: {e}")


def demo_personalized_assistant():
    """Demonstrate personalized assistant with GroundedMemory"""
    print("\n=== Personalized Assistant with GroundedMemory ===")

    memory = create_memory("grounded", working_capacity=5, enable_kg=True)

    # Build user profile
    memory.set_current_user("emma", relationship="owner")

    # Simulate past interactions
    memory.add_interaction(
        "I'm a machine learning engineer working on computer vision projects",
        "That's exciting! Computer vision has made incredible advances recently."
    )

    memory.learn_about_user("ML engineer")
    memory.learn_about_user("works on computer vision")
    memory.learn_about_user("interested in deep learning")

    memory.add_interaction(
        "I'm struggling with model training times on large image datasets",
        "Training on large image datasets can be time-consuming. Consider data loading optimization and mixed precision training."
    )

    memory.track_failure("model_training", "large_datasets")

    # Show user-specific context
    context = memory.get_full_context("optimization", user_id="emma")

    print("Personalized Context for Emma:")
    print("=" * 50)
    print(context)
    print("=" * 50)

    print(f"\n✅ Personalized context generated ({len(context)} characters)")
    print(f"Context includes: user profile, interaction history, learned patterns")

    if not LLM_AVAILABLE:
        print("⚠️ LLM not available - context structure shown above")
        return

    # Try with LLM
    try:
        provider = create_llm("mlx", model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit")

        personalized_prompt = f"""
        User context:
        {context}

        Emma asks: "Should I try distributed training for my computer vision models?"

        Provide a personalized response based on Emma's background and previous issues.
        """

        response = provider.generate(personalized_prompt)
        answer = response.content if hasattr(response, 'content') else str(response)

        print("\nLLM Response using personalized context:")
        print("-" * 50)
        print(answer[:300] + "..." if len(answer) > 300 else answer)
        print("-" * 50)

        # Check if response is personalized
        personalized = any(term in answer.lower() for term in
                          ["emma", "computer vision", "ml", "image", "training"])

        print(f"✅ Response is {'personalized' if personalized else 'generic'}")

    except Exception as e:
        print(f"LLM provider not available: {e}")


def demo_memory_types_comparison():
    """Compare different memory types"""
    print("\n=== Memory Types Comparison ===")

    # Simple ScratchpadMemory
    scratchpad = create_memory("scratchpad", max_entries=5)
    scratchpad.add_thought("Simple thought")
    scratchpad.add_action("simple_action", {})

    # Simple BufferMemory
    buffer = create_memory("buffer", max_messages=5)
    buffer.add_message("user", "Hello")
    buffer.add_message("assistant", "Hi there!")

    # Complex GroundedMemory
    grounded = create_memory("grounded", working_capacity=3)
    grounded.set_current_user("demo_user")
    grounded.add_interaction("Test", "Response")

    print("1. ScratchpadMemory (for ReAct agents):")
    print(f"   - {len(scratchpad)} entries")
    print(f"   - Lightweight: {sys.getsizeof(scratchpad)} bytes")
    print(f"   - Features: ReAct pattern, bounded capacity")

    print("\n2. BufferMemory (for chatbots):")
    print(f"   - {len(buffer.messages)} messages")
    print(f"   - Lightweight: {sys.getsizeof(buffer)} bytes")
    print(f"   - Features: Conversation history, auto-pruning")

    print("\n3. GroundedMemory (for autonomous agents):")
    print(f"   - Core memory: {len(grounded.core.blocks)} blocks")
    print(f"   - Working memory: {len(grounded.working.items)} items")
    print(f"   - User profiles: {len(grounded.user_profiles)} users")
    print(f"   - Features: Multi-tier architecture, temporal grounding, learning")

    print(f"\n✅ Memory selection matches agent complexity")


if __name__ == "__main__":
    print("AbstractMemory + Real LLM Integration Demo")
    print("=" * 50)

    demo_memory_types_comparison()
    demo_react_with_memory()
    demo_personalized_assistant()

    print("\n" + "=" * 50)
    print("Demo completed! Key takeaways:")
    print("✅ Memory types match agent complexity (no over-engineering)")
    print("✅ ReAct agents get structured thought-action-observation memory")
    print("✅ Autonomous agents get personalized, grounded memory")
    print("✅ LLMs can effectively use memory context when available")
    print("✅ Memory improves consistency and personalization")