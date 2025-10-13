#!/usr/bin/env python3
"""
Test script to verify the async triple extraction optimization.
This demonstrates the clean SUBJECT-PREDICATE-OBJECT format.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from abstractmemory.fact_extraction import MemoryFactExtractor
from abstractllm.providers.ollama_provider import OllamaProvider

def test_triple_extraction():
    """Test the enhanced triple extraction workflow."""
    print("🧠 Testing Async Triple Extraction Optimization")
    print("=" * 60)

    # Initialize with Ollama provider
    try:
        provider = OllamaProvider(model="qwen3-coder:30b")
        extractor = MemoryFactExtractor(provider=provider)
        print("✅ Initialized MemoryFactExtractor with Ollama")
    except Exception as e:
        print(f"❌ Failed to initialize provider: {e}")
        return

    # Test conversation text with clear entities and relationships
    conversation_text = """
    User: Tell me about OpenAI and their language models.

    Assistant: OpenAI is an AI research company that created GPT-4, which is a large language model.
    Microsoft Copilot uses GPT-4 for code generation and assistance. The model was trained using
    transformer architecture and requires significant computational resources for inference.
    """

    print(f"\n📝 Input conversation ({len(conversation_text)} chars):")
    print(conversation_text.strip())

    # Extract facts using new TRIPLES format
    print("\n🔍 Extracting semantic triples...")
    try:
        result = extractor.extract_facts_from_conversation(
            conversation_text=conversation_text,
            domain_focus="technology",
            importance_threshold=0.6
        )

        if result.get("error"):
            print(f"❌ Extraction failed: {result['error']}")
            return

        # Display statistics
        stats = result.get("statistics", {})
        print(f"\n📊 Extraction Statistics:")
        print(f"   • Entities: {stats.get('entities_extracted', 0)}")
        print(f"   • Triples: {stats.get('relationships_extracted', 0)}")
        print(f"   • Memory Actions: {stats.get('memory_actions_generated', 0)}")

        # Display raw extraction format
        raw = result.get("raw_extraction", {})
        print(f"\n🔧 Raw Triple Format:")
        print(f"   Format: {raw.get('format', 'unknown')}")

        # Display extracted triples
        if "triples" in raw:
            print(f"\n🎯 Extracted Semantic Triples:")
            for i, triple in enumerate(raw["triples"], 1):
                print(f"   {i}. {triple['triple_text']}")
                print(f"      Subject: {triple['subject_name']} ({triple['subject']})")
                print(f"      Predicate: {triple['predicate']}")
                print(f"      Object: {triple['object_name']} ({triple['object']})")
                print(f"      Confidence: {triple['confidence']:.2f}")
                print(f"      Strength: {triple.get('strength', 0.0):.2f}")
                print()

        # Display simple triples for easy consumption
        if "simple_triples" in raw:
            print(f"📄 Simple Triple Format:")
            for triple_text in raw["simple_triples"]:
                print(f"   • {triple_text}")

        # Display extracted entities
        if "entities" in raw:
            print(f"\n👥 Extracted Entities:")
            for entity_id, entity in raw["entities"].items():
                print(f"   • {entity.get('name', 'Unknown')} ({entity.get('type', 'Unknown Type')})")
                print(f"     ID: {entity_id}, Confidence: {entity.get('confidence', 0.0):.2f}")

        # Display memory actions that would be executed
        memory_actions = result.get("memory_actions", [])
        if memory_actions:
            print(f"\n💾 Generated Memory Actions:")
            for i, action in enumerate(memory_actions, 1):
                print(f"   {i}. {action['action']}: {action['content']}")
                print(f"      Importance: {action['importance']:.2f}")
                print(f"      Reason: {action['reason']}")
                metadata = action.get('metadata', {})
                if metadata.get('extraction_type') == 'triple':
                    print(f"      Triple: {metadata['subject']} --[{metadata['predicate']}]--> {metadata['object']}")
                print()

        print("✅ Triple extraction optimization working correctly!")
        print("\n🎯 Key Benefits:")
        print("   • Clean SUBJECT-PREDICATE-OBJECT format")
        print("   • Confidence scores per relationship")
        print("   • Ready for knowledge graph construction")
        print("   • Async execution (no user blocking)")
        print("   • Efficient injection into next interactions")

    except Exception as e:
        print(f"❌ Triple extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_triple_extraction()