#!/usr/bin/env python3
"""
Demonstration of AbstractMemory's dual storage system.

This example shows:
1. Verbatim interaction storage
2. AI experiential notes generation
3. Bidirectional linking
4. Search capabilities
5. Observable AI memory evolution

Run this script to see how AbstractMemory saves and organizes
both raw interactions and AI reflections.
"""

import tempfile
from datetime import datetime
from pathlib import Path

# Import AbstractMemory
from abstractmemory import create_memory


class MockEmbeddingProvider:
    """Mock embedding provider simulating AbstractCore integration"""

    def generate_embedding(self, text: str):
        """Generate a simple mock embedding based on text hash"""
        # In real usage, this would be AbstractCore's embedding generation
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()

        # Convert hex to floats (simplified mock)
        embedding = []
        for i in range(0, min(32, len(hash_hex)), 2):
            byte_val = int(hash_hex[i:i+2], 16)
            embedding.append(byte_val / 255.0)  # Normalize to 0-1

        # Pad to standard size
        while len(embedding) < 384:
            embedding.append(0.0)

        return embedding[:384]


def demonstrate_markdown_storage():
    """Demonstrate observable markdown storage"""
    print("🗂️  MARKDOWN STORAGE DEMONSTRATION")
    print("=" * 50)

    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Storage location: {temp_dir}")

    # Create memory with markdown storage
    memory = create_memory(
        "grounded",
        storage_backend="markdown",
        storage_path=temp_dir,
        working_capacity=5
    )

    print("\n1️⃣  Setting up users and interactions...")

    # Set up different users
    memory.set_current_user("alice", relationship="owner")

    # Add interactions that trigger different types of reflections
    interactions = [
        ("I'm a Python developer and I prefer detailed explanations",
         "Perfect! I'll make sure to provide comprehensive, detailed explanations in our discussions."),

        ("I usually work with machine learning models",
         "Excellent! Machine learning is a fascinating field. What type of models do you typically work with?"),

        ("The last approach failed, but this usually works better for data preprocessing",
         "I understand. Let's focus on the preprocessing approach that has worked well for you in the past."),

        ("By the way, switching topics - what about web development frameworks?",
         "Great transition! There are many excellent web frameworks. Are you interested in any particular language?")
    ]

    for i, (user_input, agent_response) in enumerate(interactions, 1):
        print(f"   💬 Interaction {i}: {user_input[:50]}...")
        memory.add_interaction(user_input, agent_response)

    # Switch to different user
    memory.set_current_user("bob", relationship="colleague")
    memory.add_interaction(
        "I'm new to programming and need simple explanations",
        "Welcome to programming! I'll make sure to break things down into simple, easy-to-follow steps."
    )

    print(f"\n2️⃣  Examining generated storage structure...")

    # Show directory structure
    storage_path = Path(temp_dir)

    print(f"\n📋 Directory structure:")
    for item in sorted(storage_path.rglob("*")):
        if item.is_file():
            relative_path = item.relative_to(storage_path)
            size = item.stat().st_size
            print(f"   📄 {relative_path} ({size} bytes)")

    # Show some file contents
    print(f"\n3️⃣  Sample file contents:")

    # Find a verbatim interaction file
    verbatim_files = list((storage_path / "verbatim").rglob("*.md"))
    if verbatim_files:
        sample_file = verbatim_files[0]
        print(f"\n📝 Verbatim interaction ({sample_file.name}):")
        with open(sample_file, 'r') as f:
            content = f.read()
            print("   " + "\n   ".join(content.split("\n")[:15]))
            if len(content.split("\n")) > 15:
                print("   ...")

    # Find an experiential note file
    exp_files = list((storage_path / "experiential").rglob("*.md"))
    if exp_files:
        sample_exp = exp_files[0]
        print(f"\n🧠 AI Experiential Note ({sample_exp.name}):")
        with open(sample_exp, 'r') as f:
            content = f.read()
            print("   " + "\n   ".join(content.split("\n")[:15]))
            if len(content.split("\n")) > 15:
                print("   ...")

    # Show search capabilities
    print(f"\n4️⃣  Search capabilities:")

    results = memory.search_stored_interactions("python")
    print(f"   🔍 Search 'python': {len(results)} results")

    alice_results = memory.search_stored_interactions("python", user_id="alice")
    print(f"   🔍 Search 'python' for alice: {len(alice_results)} results")

    # Show storage statistics
    stats = memory.get_storage_stats()
    print(f"\n📊 Storage statistics:")
    if "markdown_stats" in stats:
        md_stats = stats["markdown_stats"]
        print(f"   📈 Total interactions: {md_stats['total_interactions']}")
        print(f"   📈 Total notes: {md_stats['total_notes']}")
        print(f"   📈 Unique users: {md_stats['unique_users']}")
        print(f"   📈 Unique topics: {md_stats['unique_topics']}")
        print(f"   📈 Storage size: {md_stats['storage_size_mb']:.2f} MB")

    print(f"\n✅ Markdown storage demonstration complete!")
    print(f"   📁 Explore the files at: {temp_dir}")

    return temp_dir


def demonstrate_dual_storage():
    """Demonstrate dual storage with mock embedding provider"""
    print("\n\n🔄 DUAL STORAGE DEMONSTRATION")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp()
    print(f"📁 Storage location: {temp_dir}")

    # Create mock embedding provider
    embedding_provider = MockEmbeddingProvider()

    # Create memory with dual storage (markdown only for demo - LanceDB requires installation)
    memory = create_memory(
        "grounded",
        storage_backend="markdown",  # Would be "dual" with both markdown and LanceDB
        storage_path=temp_dir,
        embedding_provider=embedding_provider,
        working_capacity=3
    )

    print("\n1️⃣  Testing with embedding provider integration...")

    memory.set_current_user("charlie", relationship="client")

    # Add interactions that would benefit from vector search
    memory.add_interaction(
        "I need help with neural network architectures for computer vision",
        "I can help you with CNN architectures! Let's start with the basics and move to advanced patterns."
    )

    memory.add_interaction(
        "What about transformer models for NLP tasks?",
        "Transformers are excellent for NLP! They've revolutionized the field since the 'Attention is All You Need' paper."
    )

    memory.add_interaction(
        "I failed at implementing attention mechanisms correctly",
        "Attention mechanisms can be tricky to implement. Let's break down the key components step by step."
    )

    # Show that embedding provider was called (in real implementation)
    print(f"   🧮 Embedding provider available: {memory.get_storage_stats()['embedding_provider']}")

    # Demonstrate search
    ml_results = memory.search_stored_interactions("neural network")
    print(f"   🔍 Search 'neural network': {len(ml_results)} results")

    nlp_results = memory.search_stored_interactions("transformer")
    print(f"   🔍 Search 'transformer': {len(nlp_results)} results")

    print(f"\n✅ Dual storage demonstration complete!")

    return temp_dir


def demonstrate_reflection_system():
    """Demonstrate AI reflection and experiential note generation"""
    print("\n\n🧠 AI REFLECTION SYSTEM DEMONSTRATION")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp()
    memory = create_memory(
        "grounded",
        storage_backend="markdown",
        storage_path=temp_dir
    )

    print("\n1️⃣  Testing different reflection triggers...")

    memory.set_current_user("diana", relationship="student")

    # Trigger: User learning detection
    print("   🧠 User learning trigger...")
    memory.add_interaction(
        "I am a beginner in machine learning and I think neural networks are too complex",
        "Not to worry! Let's start with simpler concepts and build up gradually to neural networks."
    )

    # Trigger: Pattern learning detection
    print("   📊 Pattern learning trigger...")
    memory.add_interaction(
        "That approach failed for me before, but linear regression usually works well",
        "Good insight! Linear regression is indeed a reliable starting point for many problems."
    )

    # Trigger: Topic shift detection
    print("   🔄 Topic shift trigger...")
    memory.add_interaction(
        "Actually, moving on to a different topic - what about data visualization?",
        "Great transition! Data visualization is crucial for understanding your data and communicating results."
    )

    # Trigger: High confidence interaction
    print("   ⬆️ Confidence change trigger...")
    memory.add_interaction(
        "That explanation was perfect and exactly what I needed",
        "Excellent! I'm glad that explanation was helpful and clear for you."
    )

    # Check what reflections were generated
    stats = memory.get_storage_stats()
    if "markdown_stats" in stats:
        print(f"\n📊 Reflection results:")
        print(f"   💬 Interactions stored: {stats['markdown_stats']['total_interactions']}")
        print(f"   🧠 Experiential notes: {stats['markdown_stats']['total_notes']}")
        print(f"   🔗 Links created: {stats['markdown_stats']['total_links']}")

    # Show sample reflection if any were generated
    exp_files = list(Path(temp_dir).rglob("experiential/**/*.md"))
    if exp_files:
        print(f"\n🧠 Sample AI reflection:")
        with open(exp_files[0], 'r') as f:
            lines = f.read().split('\n')
            for line in lines[:10]:
                if line.strip():
                    print(f"   {line}")
            if len(lines) > 10:
                print("   ...")

    print(f"\n✅ Reflection system demonstration complete!")

    return temp_dir


def main():
    """Run all demonstrations"""
    print("🚀 ABSTRACTMEMORY STORAGE SYSTEM DEMO")
    print("=" * 60)
    print()
    print("This demonstration shows AbstractMemory's new storage capabilities:")
    print("• Verbatim interaction storage")
    print("• AI experiential notes and reflections")
    print("• Bidirectional linking between interactions and notes")
    print("• Search and retrieval capabilities")
    print("• Observable AI memory evolution")
    print()

    # Run demonstrations
    markdown_dir = demonstrate_markdown_storage()
    dual_dir = demonstrate_dual_storage()
    reflection_dir = demonstrate_reflection_system()

    print("\n\n🎉 DEMONSTRATION COMPLETE!")
    print("=" * 60)
    print()
    print("Generated storage directories:")
    print(f"📁 Markdown demo: {markdown_dir}")
    print(f"📁 Dual storage demo: {dual_dir}")
    print(f"📁 Reflection demo: {reflection_dir}")
    print()
    print("💡 Explore the generated markdown files to see:")
    print("   • How AI interactions are stored verbatim")
    print("   • How AI generates experiential notes about interactions")
    print("   • How bidirectional links connect interactions to reflections")
    print("   • How topics are automatically extracted and organized")
    print()
    print("🔗 These directories demonstrate the complete observability")
    print("   of AI memory evolution over time!")


if __name__ == "__main__":
    main()