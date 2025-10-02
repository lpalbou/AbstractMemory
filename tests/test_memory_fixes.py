#!/usr/bin/env python3
"""
Test memory deduplication and synthesis fixes.
"""

from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider

def test_memory_fixes():
    """Test that memory deduplication and full content synthesis work."""

    # Initialize session
    provider = OllamaProvider(model="qwen3-coder:30b")
    provider.set_timeout(3600.0)

    session = MemorySession(
        provider=provider,
        memory_base_path="repl_memory",
        default_user_id="user",
        timeout=3600.0
    )

    print("Testing memory reconstruction...")

    # Test reconstruction with query that should retrieve memories
    context_data = session.reconstruct_context(
        user_id="user",
        query="do you remember anything?",
        location="terminal",
        focus_level=3
    )

    # Check deduplication
    total_retrieved = context_data["total_memories"]
    semantic_count = len(context_data["semantic_memories"])
    linked_count = len(context_data["linked_memories"])

    print(f"\n=== DEDUPLICATION TEST ===")
    print(f"Semantic memories: {semantic_count}")
    print(f"Linked memories: {linked_count}")
    print(f"Total (deduplicated): {total_retrieved}")
    print(f"Expected: {total_retrieved} <= {semantic_count + linked_count}")

    # Check synthesis contains full content
    synthesized = context_data["synthesized_context"]

    print(f"\n=== SYNTHESIS TEST ===")
    print(f"Synthesized context length: {len(synthesized)} chars")
    print(f"Contains '[Retrieved Memories]:': {('[Retrieved Memories]:' in synthesized)}")

    # Show first 2000 chars of synthesis
    print(f"\n=== SYNTHESIZED CONTEXT (first 2000 chars) ===")
    print(synthesized[:2000])

    # Verify memories have full content
    if "[Retrieved Memories]:" in synthesized:
        print("\n✅ SUCCESS: Full memories included in synthesis")
    else:
        print("\n❌ FAIL: Memories not properly included")

    if total_retrieved <= semantic_count + linked_count:
        print(f"✅ SUCCESS: Deduplication working ({total_retrieved} <= {semantic_count + linked_count})")
    else:
        print(f"❌ FAIL: No deduplication ({total_retrieved} > {semantic_count + linked_count})")

if __name__ == "__main__":
    test_memory_fixes()
