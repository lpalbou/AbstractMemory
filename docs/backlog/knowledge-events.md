# Knowledge Events System Design

**Status**: Research & Design Phase
**Created**: 2025-09-24
**Priority**: Medium-High

## Executive Summary

This document proposes an event-driven architecture for AbstractMemory to emit structured events when knowledge and memories are created or modified. The system leverages the existing AbstractCore events framework and follows SOTA best practices for AI system observability and memory management.

## Problem Statement

Currently, AbstractMemory creates and updates various types of memory (core, semantic, episodic, working) but provides no mechanism for external systems or UX layers to be notified when significant memory changes occur. This limits:

- **User Experience**: Users cannot be informed when new knowledge is learned
- **System Integration**: External systems cannot react to memory changes
- **Observability**: No visibility into learning patterns and memory evolution
- **Debugging**: Difficult to trace when and why specific knowledge was created

## Research Findings

### Current AbstractMemory Architecture

The codebase implements a four-tier memory architecture:

1. **Core Memory** (`components/core.py`): Agent identity and persona (rarely changes)
2. **Semantic Memory** (`components/semantic.py`): Validated facts with confidence thresholds
3. **Working Memory** (`components/working.py`): Transient context (high churn)
4. **Episodic Memory** (`components/episodic.py`): Event archive (medium churn)

### AbstractCore Events System

AbstractCore provides a robust event system with:
- **EventType enum**: Standardized event types
- **Event dataclass**: Structured event data with timestamps
- **EventEmitter mixin**: For local event handling
- **GlobalEventBus**: System-wide event distribution
- **OpenTelemetry compatibility**: Industry-standard observability

### SOTA Best Practices

Research reveals several key principles:

1. **Event-Driven Architecture Benefits**:
   - Complete system visibility and traceability
   - Real-time processing and continuous learning capability
   - Enhanced observability through detailed event payloads
   - Decoupled, scalable system components

2. **Memory Update Strategies**:
   - "Hot path" updates: Memory updated during conversation flow
   - "Background" updates: Asynchronous memory processing
   - Batch processing for high-volume fact creation

3. **Observability Requirements**:
   - Full context capture with timestamps
   - Traceability of all memory operations
   - Compliance and auditability features

## Proposed Solution

### Memory Event Types

Extend AbstractCore's `EventType` enum with memory-specific events:

```python
class MemoryEventType(Enum):
    # Core memory events (low frequency, high importance)
    CORE_MEMORY_CREATED = "core_memory_created"
    CORE_MEMORY_UPDATED = "core_memory_updated"

    # Semantic memory events (medium frequency, high importance)
    SEMANTIC_FACTS_VALIDATED = "semantic_facts_validated"      # Batch of facts promoted to semantic memory
    SEMANTIC_CONCEPT_LEARNED = "semantic_concept_learned"      # New concept network created
    SEMANTIC_CONFIDENCE_UPDATED = "semantic_confidence_updated" # Confidence changed significantly

    # Episodic memory events (medium frequency, medium importance)
    EPISODIC_BATCH_STORED = "episodic_batch_stored"           # Batch of episodes added
    EPISODIC_CONSOLIDATION_COMPLETED = "episodic_consolidation_completed" # Memory consolidation finished

    # Working memory events (excluded due to high frequency)
    # Working memory changes too rapidly to emit individual events

    # Knowledge graph events (if enabled)
    KNOWLEDGE_GRAPH_UPDATED = "knowledge_graph_updated"       # Facts added to KG
    KNOWLEDGE_RELATIONSHIP_DISCOVERED = "knowledge_relationship_discovered" # New entity relationships

    # Pattern learning events
    FAILURE_PATTERN_LEARNED = "failure_pattern_learned"       # Recurring failure pattern identified
    SUCCESS_PATTERN_LEARNED = "success_pattern_learned"       # Recurring success pattern identified

    # User learning events
    USER_PROFILE_UPDATED = "user_profile_updated"             # New user information learned
    USER_PREFERENCE_LEARNED = "user_preference_learned"       # User preference identified
```

### Event Data Structure

Each memory event will include:

```python
@dataclass
class MemoryEvent(Event):
    memory_type: str                    # "core", "semantic", "episodic", "kg"
    change_type: str                    # "created", "updated", "validated", "learned"
    affected_items: List[Dict[str, Any]] # Items that changed
    confidence_change: float            # Change in confidence (-1.0 to 1.0)
    user_id: Optional[str]              # Associated user if applicable
    learning_trigger: str               # What caused this learning
    metadata: Dict[str, Any]            # Additional context
```

### Integration Points

#### 1. Semantic Memory Integration

**Location**: `abstractmemory/components/semantic.py:37-50`

```python
def add(self, item: MemoryItem) -> str:
    """Add potential fact - only stored after validation"""
    fact_key = str(item.content).lower()
    self.pending_facts[fact_key] += 1

    if self.pending_facts[fact_key] >= self.validation_threshold:
        fact_id = f"fact_{len(self.facts)}_{datetime.now().timestamp()}"
        occurrence_count = self.pending_facts[fact_key]

        # Create fact entry
        self.facts[fact_id] = {
            'content': item.content,
            'confidence': min(1.0, occurrence_count * 0.1 + 0.3),
            'first_seen': item.event_time,
            'validated_at': datetime.now(),
            'occurrence_count': occurrence_count,
            'original_metadata': item.metadata or {}
        }

        # EMIT EVENT: Semantic fact validated
        if hasattr(self, 'emit'):  # EventEmitter mixin
            self.emit(MemoryEventType.SEMANTIC_FACTS_VALIDATED, {
                "facts_validated": [fact_id],
                "content": item.content,
                "confidence": self.facts[fact_id]['confidence'],
                "occurrence_count": occurrence_count,
                "validation_time": datetime.now().isoformat()
            }, learning_trigger="threshold_reached")

        del self.pending_facts[fact_key]
        return fact_id

    return ""
```

#### 2. Core Memory Integration

**Location**: `abstractmemory/components/core.py:60-66`

```python
def update_block(self, block_id: str, content: str, reasoning: str = "") -> bool:
    """Agent updates a core memory block (self-editing capability)"""
    if block_id in self.blocks:
        if len(content) <= self.max_tokens_per_block * 4:
            old_content = self.blocks[block_id].content
            self.blocks[block_id].update(content, reasoning)

            # EMIT EVENT: Core memory updated
            if hasattr(self, 'emit'):  # EventEmitter mixin
                self.emit(MemoryEventType.CORE_MEMORY_UPDATED, {
                    "block_id": block_id,
                    "old_content": old_content,
                    "new_content": content,
                    "reasoning": reasoning,
                    "edit_count": self.blocks[block_id].edit_count
                }, learning_trigger="self_modification")

            return True
    return False
```

#### 3. GroundedMemory Pattern Learning

**Location**: `abstractmemory/__init__.py:701-719`

```python
def track_failure(self, action: str, context: str):
    """Track a failed action to learn from mistakes"""
    failure_key = f"{action}:{context}"
    self.failure_patterns[failure_key] = self.failure_patterns.get(failure_key, 0) + 1

    if self.failure_patterns[failure_key] >= 3:
        fact = f"Action '{action}' tends to fail in context: {context}"
        # ... existing logic ...

        # EMIT EVENT: Failure pattern learned
        if hasattr(self, 'emit'):
            self.emit(MemoryEventType.FAILURE_PATTERN_LEARNED, {
                "action": action,
                "context": context,
                "failure_count": self.failure_patterns[failure_key],
                "learned_constraint": fact
            }, learning_trigger="pattern_recognition")
```

### Implementation Strategy

#### Phase 1: Core Integration
1. Add `EventEmitter` mixin to memory components
2. Implement events for semantic fact validation
3. Implement events for core memory updates
4. Add configuration option to enable/disable memory events

#### Phase 2: Enhanced Events
1. Add episodic memory batch events
2. Implement knowledge graph events
3. Add pattern learning events
4. Implement user learning events

#### Phase 3: Advanced Features
1. Event filtering and aggregation
2. Background event processing
3. Event persistence and replay
4. Integration with external systems

### Configuration

```python
@dataclass
class MemoryEventConfig:
    enabled: bool = True
    emit_semantic_events: bool = True
    emit_core_events: bool = True
    emit_episodic_events: bool = True
    emit_pattern_events: bool = True
    emit_user_events: bool = True
    batch_semantic_events: bool = True      # Batch multiple facts into single event
    min_confidence_change: float = 0.1      # Minimum confidence change to emit event
    event_buffer_size: int = 10             # Buffer events before emission
    background_processing: bool = False     # Process events asynchronously
```

### Usage Examples

#### 1. UX Notifications

```python
def setup_memory_notifications(memory: GroundedMemory):
    """Setup UI notifications for memory events"""

    def on_new_knowledge(event: Event):
        if event.type == MemoryEventType.SEMANTIC_FACTS_VALIDATED:
            notify_user(f"💡 Learned: {event.data['content']}")

    def on_pattern_learned(event: Event):
        if event.type == MemoryEventType.FAILURE_PATTERN_LEARNED:
            notify_user(f"⚠️ Pattern identified: {event.data['learned_constraint']}")

    memory.on(MemoryEventType.SEMANTIC_FACTS_VALIDATED, on_new_knowledge)
    memory.on(MemoryEventType.FAILURE_PATTERN_LEARNED, on_pattern_learned)
```

#### 2. System Integration

```python
def setup_analytics_tracking(memory: GroundedMemory):
    """Track learning analytics"""

    def track_learning_rate(event: Event):
        analytics.track_event("memory_learning", {
            "memory_type": event.data.get("memory_type"),
            "confidence": event.data.get("confidence"),
            "learning_trigger": event.data.get("learning_trigger"),
            "timestamp": event.timestamp
        })

    # Track all memory events
    for event_type in MemoryEventType:
        memory.on(event_type, track_learning_rate)
```

#### 3. Debugging and Development

```python
class MemoryEventDebugger:
    """Debug memory learning in development"""

    def __init__(self):
        self.events = []

    def log_all_events(self, event: Event):
        self.events.append(event)
        print(f"[MEMORY] {event.type.value}: {event.data}")

    def get_learning_timeline(self) -> List[Event]:
        return sorted(self.events, key=lambda e: e.timestamp)
```

## Rationale for Event Selection

### Events to Include:

1. **Semantic Facts Validated**: Critical for UX - users want to know when AI learns something new
2. **Core Memory Updates**: Rare but important - agent identity changes are significant
3. **Pattern Learning**: Valuable for debugging - understanding AI failure/success patterns
4. **User Learning**: Important for personalization - tracking what AI learns about users
5. **Knowledge Graph Updates**: If enabled, shows relationship learning

### Events to Exclude:

1. **Working Memory Changes**: Too frequent (dozens per interaction) - would overwhelm system
2. **Individual Fact Attempts**: Before validation threshold - creates noise
3. **Low-Confidence Updates**: Below minimum threshold - not significant enough

### Batch Processing Strategy:

- **Semantic Facts**: Batch multiple facts validated in same interaction
- **Episodic Episodes**: Batch episodes created in same time window
- **Knowledge Graph**: Batch relationship updates

## Technical Considerations

### Performance Impact

1. **Memory Overhead**: Event objects are lightweight (~200 bytes each)
2. **CPU Impact**: Minimal - event emission is microsecond-scale
3. **I/O Impact**: Optional persistence - can be disabled for performance-critical use cases

### Thread Safety

- Events emitted synchronously within memory component thread
- Global event bus handles concurrent access automatically
- Background processing option for async handling

### Error Handling

- Event emission failures don't block memory operations
- Failed event handlers are logged but don't stop processing
- Circuit breaker pattern for problematic event handlers

### Backwards Compatibility

- Event system is opt-in via configuration
- Existing memory components work unchanged
- New events extend existing AbstractCore types

## Future Enhancements

### 1. Event Streaming
Integration with Apache Kafka or similar for enterprise deployments:

```python
class KafkaMemoryEventHandler:
    def handle_event(self, event: Event):
        kafka_producer.send('memory-events', event.to_dict())
```

### 2. Event Replay
Ability to replay memory events for debugging:

```python
class MemoryEventStore:
    def replay_events(self, start_time: datetime, end_time: datetime):
        # Replay events to reconstruct memory state
        pass
```

### 3. Machine Learning on Events
Use event patterns to optimize memory strategies:

```python
class MemoryOptimizer:
    def analyze_learning_patterns(self, events: List[Event]):
        # Analyze which learning triggers are most effective
        pass
```

## Implementation Checklist

- [ ] Extend AbstractCore EventType with MemoryEventType
- [ ] Add EventEmitter mixin to memory components
- [ ] Implement semantic memory events
- [ ] Implement core memory events
- [ ] Add configuration system
- [ ] Create event batching logic
- [ ] Add comprehensive tests
- [ ] Update documentation
- [ ] Create usage examples
- [ ] Performance testing

## Conclusion

The proposed memory events system provides a clean, efficient way to observe and react to memory changes in AbstractMemory. By leveraging the existing AbstractCore events framework and following SOTA best practices, this system enables:

- **Enhanced User Experience**: Real-time learning notifications
- **Better System Integration**: Event-driven architecture for external systems
- **Improved Observability**: Complete visibility into memory evolution
- **Debugging Capabilities**: Trace memory changes and learning patterns

The design balances completeness with performance, emitting events for significant memory changes while avoiding noise from high-frequency operations like working memory updates. The opt-in configuration ensures backwards compatibility while providing flexibility for different deployment scenarios.

This foundational capability opens the door for advanced features like adaptive learning strategies, intelligent memory management, and sophisticated user interfaces that can visualize and interact with AI memory systems in real-time.