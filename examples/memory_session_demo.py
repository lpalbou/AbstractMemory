#!/usr/bin/env python3
"""
MemorySession Demo - Drop-in BasicSession replacement with memory.

This example demonstrates the key features of MemorySession:
- Drop-in BasicSession replacement
- Automatic memory management
- Multi-user support
- Persistent storage
"""

import os
import tempfile
from datetime import datetime

# Mock provider for demonstration (replace with real provider)
class MockProvider:
    """Mock LLM provider for demo purposes"""

    def __init__(self):
        self.call_count = 0

    def generate(self, prompt, system_prompt=None, **kwargs):
        self.call_count += 1

        # Mock response based on system prompt content
        if system_prompt and "alice" in system_prompt.lower():
            response_content = f"I remember you're Alice and love Python! ({prompt})"
        elif system_prompt and "bob" in system_prompt.lower():
            response_content = f"I remember you're Bob and prefer Java! ({prompt})"
        elif system_prompt and "python" in system_prompt.lower():
            response_content = "I see you've mentioned Python before - it's a great language!"
        else:
            response_content = f"Hello! ({prompt})"

        # Mock response object
        class MockResponse:
            def __init__(self, content):
                self.content = content

        return MockResponse(response_content)


def demo_basic_usage():
    """Demo 1: Basic MemorySession usage"""
    print("=" * 60)
    print("Demo 1: Basic MemorySession Usage")
    print("=" * 60)

    from abstractmemory import MemorySession

    # Create session with mock provider
    provider = MockProvider()
    session = MemorySession(provider, system_prompt="You are a helpful assistant.")

    print("🧠 Created MemorySession (same API as BasicSession)")
    print(f"📊 Initial stats: {session.get_memory_stats()}")
    print()

    # First interaction
    print("👤 User: Hi, I'm Alice and I love Python programming")
    response1 = session.generate("Hi, I'm Alice and I love Python programming")
    print(f"🤖 Assistant: {response1.content}")
    print()

    # Second interaction - memory should kick in
    print("👤 User: What do you remember about me?")
    response2 = session.generate("What do you remember about me?")
    print(f"🤖 Assistant: {response2.content}")
    print()

    print(f"📊 Final stats: {session.get_memory_stats()}")
    print()


def demo_multi_user():
    """Demo 2: Multi-user context separation"""
    print("=" * 60)
    print("Demo 2: Multi-User Context Separation")
    print("=" * 60)

    from abstractmemory import MemorySession

    provider = MockProvider()
    session = MemorySession(provider)

    # Conversation with Alice
    print("👤 Alice: I love Python and work on ML projects")
    alice_intro = session.generate("I love Python and work on ML projects", user_id="alice")
    print(f"🤖 Assistant to Alice: {alice_intro.content}")
    session.learn_about_user("Python ML developer", user_id="alice")
    print()

    # Conversation with Bob
    print("👤 Bob: I prefer Java and work on web applications")
    bob_intro = session.generate("I prefer Java and work on web applications", user_id="bob")
    print(f"🤖 Assistant to Bob: {bob_intro.content}")
    session.learn_about_user("Java web developer", user_id="bob")
    print()

    # Later conversations - different contexts
    print("--- Later conversations ---")
    print("👤 Alice: Tell me about programming")
    alice_context = session.generate("Tell me about programming", user_id="alice")
    print(f"🤖 Assistant to Alice: {alice_context.content}")
    print()

    print("👤 Bob: Tell me about programming")
    bob_context = session.generate("Tell me about programming", user_id="bob")
    print(f"🤖 Assistant to Bob: {bob_context.content}")
    print()

    print(f"📊 Final stats: {session.get_memory_stats()}")
    print()


def demo_persistent_storage():
    """Demo 3: Persistent storage configuration"""
    print("=" * 60)
    print("Demo 3: Persistent Storage")
    print("=" * 60)

    from abstractmemory import MemorySession

    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary storage: {temp_dir}")

        # Session with storage
        memory_config = {"path": temp_dir}
        provider = MockProvider()
        session = MemorySession(provider, memory_config=memory_config)

        print("🧠 Created MemorySession with persistent storage")
        print()

        # Add some interactions
        print("👤 User: I work with machine learning models")
        response1 = session.generate("I work with machine learning models")
        print(f"🤖 Assistant: {response1.content}")

        print("👤 User: My favorite framework is TensorFlow")
        response2 = session.generate("My favorite framework is TensorFlow")
        print(f"🤖 Assistant: {response2.content}")
        print()

        # Check storage stats
        storage_stats = session.get_memory_stats()
        print(f"📊 Storage stats: {storage_stats}")

        # List files created
        print("\n📂 Files created:")
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, temp_dir)
                print(f"  - {rel_path}")
        print()


def demo_memory_context_inspection():
    """Demo 4: Memory context inspection"""
    print("=" * 60)
    print("Demo 4: Memory Context Inspection")
    print("=" * 60)

    from abstractmemory import MemorySession

    provider = MockProvider()
    session = MemorySession(provider)

    # Build up some context
    session.generate("I'm learning Python", user_id="student")
    session.generate("I find functions confusing", user_id="student")
    session.learn_about_user("beginner programmer", user_id="student")
    session.learn_about_user("struggles with functions", user_id="student")

    print("🧠 Built up memory context for student")
    print()

    # Inspect memory context
    context = session.get_memory_context("Python programming", user_id="student")
    print("🔍 Memory context for 'Python programming':")
    print("-" * 40)
    print(context)
    print("-" * 40)
    print()

    # Search memory
    search_results = session.search_memory("functions")
    print(f"🔎 Search results for 'functions': {len(search_results)} items")
    for i, result in enumerate(search_results[:2], 1):
        print(f"  {i}. {result}")
    print()


def demo_advanced_configuration():
    """Demo 5: Advanced configuration options"""
    print("=" * 60)
    print("Demo 5: Advanced Configuration")
    print("=" * 60)

    from abstractmemory import MemorySession

    # Advanced configuration
    advanced_config = {
        "working_capacity": 20,      # More working memory
        "enable_kg": True,           # Knowledge graph
        "semantic_threshold": 2      # Lower validation threshold
    }

    provider = MockProvider()
    session = MemorySession(
        provider,
        memory_config=advanced_config,
        default_user_id="power_user"
    )

    print("🔧 Created MemorySession with advanced configuration:")
    print(f"   - Working capacity: {advanced_config['working_capacity']}")
    print(f"   - Knowledge graph: {advanced_config['enable_kg']}")
    print(f"   - Semantic threshold: {advanced_config['semantic_threshold']}")
    print()

    # Test configuration
    session.generate("Python is a programming language")
    session.generate("TensorFlow is a ML framework")
    session.generate("Neural networks are powerful")

    stats = session.get_memory_stats()
    print(f"📊 Session stats: {stats}")
    print()

    # Test knowledge graph if available
    if hasattr(session.memory, 'kg') and session.memory.kg:
        print("🕸️  Knowledge graph is enabled and active")
    else:
        print("❌ Knowledge graph not available")
    print()


def demo_streaming_response():
    """Demo 6: Streaming response handling"""
    print("=" * 60)
    print("Demo 6: Streaming Response Handling")
    print("=" * 60)

    # Mock streaming provider
    class MockStreamingProvider:
        def generate(self, prompt, system_prompt=None, **kwargs):
            chunks = ["Hello", " there", "! I'm", " streaming", " a response", "."]
            for chunk_text in chunks:
                class MockChunk:
                    def __init__(self, content):
                        self.content = content
                yield MockChunk(chunk_text)

    from abstractmemory import MemorySession

    streaming_provider = MockStreamingProvider()
    session = MemorySession(streaming_provider)

    print("📡 Testing streaming response handling...")
    response_gen = session.generate("Tell me a story")

    print("🤖 Assistant: ", end="", flush=True)
    full_response = ""
    for chunk in response_gen:
        print(chunk.content, end="", flush=True)
        full_response += chunk.content
    print()  # New line
    print()

    print(f"✅ Full response collected: '{full_response}'")
    print(f"📊 Memory stats: {session.get_memory_stats()}")
    print()


def main():
    """Run all demos"""
    print("🚀 MemorySession Comprehensive Demo")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # Run all demos
        demo_basic_usage()
        demo_multi_user()
        demo_persistent_storage()
        demo_memory_context_inspection()
        demo_advanced_configuration()
        demo_streaming_response()

        print("=" * 60)
        print("✅ All demos completed successfully!")
        print("=" * 60)
        print()
        print("🎯 Key takeaways:")
        print("   • MemorySession is a drop-in BasicSession replacement")
        print("   • Memory context is automatically injected")
        print("   • Multi-user support with context separation")
        print("   • Persistent storage with minimal configuration")
        print("   • Advanced features available when needed")
        print()
        print("📚 Next steps:")
        print("   • Try with a real LLM provider (AbstractCore)")
        print("   • Experiment with different memory configurations")
        print("   • Build a conversational application")
        print("   • Explore advanced memory features")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()