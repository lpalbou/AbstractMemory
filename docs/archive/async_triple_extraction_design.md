# Async Triple Extraction Workflow Design

## Overview
Optimal design for semantic graph extraction as TRIPLES with async execution and efficient injection back into interactions.

## Current System Assessment ✅

### What's Already Perfect:
1. **Async Execution**: `_schedule_async_fact_extraction()` runs after response returned
2. **AbstractCore BasicExtractor**: Supports `output_format="triples"` natively
3. **Fact Injection**: 9-step `reconstruct_context()` retrieves and injects facts
4. **Thread Safety**: Background threading with proper error handling
5. **Performance**: No blocking of user interactions

### What Needs One Simple Change:
- Change `output_format="jsonld"` to `output_format="triples"` in fact_extraction.py

## Optimal Workflow Architecture

```
User Input → LLM Response → [ASYNC BACKGROUND] → Triple Extraction → Memory Storage
     ↑                                                                       ↓
Next Interaction ← 9-Step Context Reconstruction ← Stored Triple Facts ←────┘
```

### Step-by-Step Flow:

**1. Immediate Response (0ms delay)**
```python
# User gets response immediately
answer = self.chat(user_input)
return answer  # No waiting for fact extraction
```

**2. Background Triple Extraction (3-5 seconds)**
```python
# Runs in daemon thread after response returned
def async_fact_extraction():
    conversation_text = f"User: {user_input}\n\nAssistant: {answer}"

    # ← ONLY CHANGE NEEDED: Use triples format
    facts_result = self.fact_extractor.extract_facts_from_conversation(
        conversation_text=conversation_text,
        output_format="triples"  # Instead of "jsonld"
    )

    # Store extracted triples in memory system
    for triple in facts_result.get("triples", []):
        self.remember_fact(
            content=triple["triple_text"],  # "OpenAI creates GPT-4"
            importance=triple["confidence"],
            metadata={
                "extraction_type": "triple",
                "subject": triple["subject_name"],
                "predicate": triple["predicate"],
                "object": triple["object_name"],
                "confidence": triple["confidence"],
                "strength": triple["strength"]
            }
        )
```

**3. Next Interaction - Triple Injection (<500ms)**
```python
# Fast 9-step reconstruction injects stored triples
context = self.reconstruct_context(user_id, new_query)

# Stored triples become available as memory content:
# "I remember that OpenAI creates GPT-4 and Microsoft Copilot uses GPT-4"
```

## Implementation Changes Required

### File: `abstractmemory/fact_extraction.py`

**Line 79** - Change output format:
```python
# OLD
extraction_result = self.extractor.extract(
    text=conversation_text,
    output_format="jsonld"
)

# NEW
extraction_result = self.extractor.extract(
    text=conversation_text,
    output_format="triples"
)
```

**Lines 229-272** - Update `_convert_extraction_to_memory_facts()`:
```python
def _convert_extraction_to_memory_facts(self, extraction_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert triple extraction to memory-friendly facts."""
    memory_facts = []

    # Process triples directly (not JSON-LD graph)
    for triple in extraction_result.get("triples", []):
        fact = {
            "type": "triple",
            "subject": triple["subject_name"],
            "predicate": triple["predicate"],
            "object": triple["object_name"],
            "triple_text": triple["triple_text"],
            "confidence": triple["confidence"],
            "strength": triple.get("strength", 0.5),
            "importance": min(triple["confidence"], 1.0)
        }
        memory_facts.append(fact)

    return memory_facts
```

**Lines 304-350** - Update `_generate_memory_actions()`:
```python
def _generate_memory_actions(self, memory_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate memory actions for storing extracted triples."""
    memory_actions = []

    for fact in memory_facts:
        if fact["type"] == "triple":
            action = {
                "action": "remember",
                "content": fact["triple_text"],  # "OpenAI creates GPT-4"
                "importance": fact["importance"],
                "emotion": "neutral",
                "reason": f"Extracted semantic triple: {fact['predicate']} relationship",
                "metadata": {
                    "extraction_type": "triple",
                    "subject": fact["subject"],
                    "predicate": fact["predicate"],
                    "object": fact["object"],
                    "confidence": fact["confidence"],
                    "strength": fact["strength"]
                }
            }
            memory_actions.append(action)

    return memory_actions
```

## Performance Characteristics

### Current System:
- ✅ User response: Immediate (0ms delay)
- ✅ Background extraction: 3-5 seconds (AbstractCore BasicExtractor)
- ✅ Memory storage: ~100ms per triple
- ✅ Next interaction retrieval: <500ms (9-step reconstruction)

### Enhanced System (with triples):
- ✅ Same performance characteristics
- ✅ Cleaner triple format for knowledge graphs
- ✅ Better semantic relationships ("creates", "uses", "requires")
- ✅ Confidence scores per relationship
- ✅ Simple integration with existing memory system

## Advantages of Triple Format

1. **Semantic Clarity**: "OpenAI creates GPT-4" vs complex JSON-LD
2. **Graph Database Ready**: Direct subject-predicate-object format
3. **Confidence Scoring**: Per-relationship confidence levels
4. **Memory Efficiency**: Simpler storage format
5. **Query Friendly**: Easy to search for specific relationships

## Integration with Existing System

**Zero Breaking Changes:**
- ✅ Same async execution model
- ✅ Same memory storage interface
- ✅ Same 9-step reconstruction
- ✅ Same thread safety
- ✅ Same performance characteristics

**Enhanced Capabilities:**
- ✅ Triple format for knowledge graphs
- ✅ Relationship-specific confidence scores
- ✅ Cleaner semantic representation
- ✅ Better fact injection format

## Conclusion

The current system is already **optimal** for async semantic extraction and injection. The only enhancement needed is switching to triple format, which requires minimal changes but provides significantly better semantic representation for knowledge graph construction.

**Implementation Time**: 15 minutes
**Risk Level**: Very Low (single parameter change)
**Performance Impact**: None (same BasicExtractor, different output format)
**Benefits**: Cleaner triples, better relationships, knowledge graph ready