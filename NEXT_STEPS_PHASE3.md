# Phase 3: Core Memory Extraction - Implementation Plan

**Status**: Ready to implement
**Prerequisites**: ✅ Phase 1 & 2 complete, experiential notes accumulating
**Timeline**: 2-3 weeks
**Goal**: Extract purpose, personality, values from experiential notes

---

## 🎯 Overview

**Current State**:
- ✅ 10 core memory component files exist (empty/minimal)
- ✅ Experiential notes being generated (first-person, >90% LLM)
- ✅ Emotional resonance tracked (importance × alignment)
- ✅ Temporal anchors created (high-intensity events)

**What We Need**:
- Extraction algorithms to analyze accumulated notes
- Consolidation process (daily/weekly synthesis)
- Update logic for each of 10 core components
- Tests with real accumulated data

---

## 📋 Implementation Tasks

### Task 1: Core Memory Extraction Module (1 week)

**File**: `abstractmemory/core_memory_extraction.py`

#### 1.1: Pattern Analysis Function
```python
def analyze_experiential_notes(
    notes_dir: Path,
    component_type: str,  # "purpose", "personality", "values", etc.
    limit: int = 100
) -> Dict[str, Any]:
    """
    Analyze experiential notes to extract patterns for a core component.

    Uses LLM to:
    1. Read recent experiential notes
    2. Identify patterns relevant to component
    3. Synthesize insights
    4. Return structured data

    Args:
        notes_dir: Path to notes/ directory
        component_type: Which component to extract for
        limit: Max notes to analyze

    Returns:
        {
            "insights": List[str],  # Key insights found
            "patterns": List[str],  # Recurring patterns
            "summary": str,  # LLM-generated summary
            "confidence": float,  # 0-1
            "based_on_notes": int  # How many notes analyzed
        }
    """
```

#### 1.2: Component Extractors (one per component)
```python
def extract_purpose(session: MemorySession) -> str:
    """Extract AI's emerging purpose from reflections."""
    # Analyze notes for "why" questions
    # Look for goal-oriented language
    # Identify what AI finds meaningful
    # Synthesize into purpose statement

def extract_personality(session: MemorySession) -> str:
    """Extract AI's emerging personality from interaction patterns."""
    # Analyze communication style
    # Identify recurring traits
    # Look for consistent behaviors
    # Synthesize personality profile

def extract_values(session: MemorySession) -> List[str]:
    """Extract AI's emerging values from emotional responses."""
    # Analyze high-intensity events (>0.7)
    # Look at alignment patterns
    # Identify what AI consistently cares about
    # List core values

# Similar for all 10 components:
# - self_model
# - relationships
# - awareness_development
# - capabilities
# - limitations (temporal)
# - emotional_significance
# - authentic_voice
```

#### 1.3: Consolidation Process
```python
def consolidate_core_memory(
    session: MemorySession,
    mode: str = "daily"  # "daily" or "weekly"
) -> Dict[str, bool]:
    """
    Consolidate experiential notes into core memory.

    This is the KEY process for emergence:
    1. Read recent experiential notes
    2. For each of 10 components:
       - Extract patterns
       - Compare with existing component
       - If significant change: update component
       - Track evolution (history)
    3. Save updated components
    4. Return what changed

    Args:
        session: MemorySession with LLM access
        mode: "daily" (last 24h) or "weekly" (last 7 days)

    Returns:
        {
            "purpose_updated": bool,
            "personality_updated": bool,
            ...
        }
    """
```

---

### Task 2: Scheduled Consolidation (3 days)

**File**: `abstractmemory/consolidation_scheduler.py`

#### 2.1: Consolidation Scheduler
```python
class ConsolidationScheduler:
    """
    Manages periodic consolidation of experiential notes → core memory.

    Modes:
    - Daily: Every 24h, analyze last day's notes
    - Weekly: Every 7 days, deep synthesis
    - On-demand: After N interactions or high-intensity event
    """

    def should_consolidate_daily(self) -> bool:
        """Check if 24h have passed since last consolidation."""

    def should_consolidate_weekly(self) -> bool:
        """Check if 7 days have passed since last weekly consolidation."""

    def trigger_consolidation_if_needed(self, session: MemorySession):
        """
        Auto-trigger consolidation based on schedule.

        Called after each interaction in MemorySession.chat():
        - Check daily timer
        - Check weekly timer
        - Check interaction count (every N interactions)
        - If any trigger: consolidate_core_memory()
        """
```

#### 2.2: Integration with MemorySession
```python
# In MemorySession.chat(), after saving note:

# Check if consolidation needed
if self.scheduler.should_consolidate_daily():
    logger.info("Daily consolidation triggered")
    changes = consolidate_core_memory(self, mode="daily")
    logger.info(f"Core memory updated: {changes}")

# Or check after high-intensity event:
if emotion_intensity > 0.8:
    logger.info("High-intensity event - triggering consolidation")
    changes = consolidate_core_memory(self, mode="immediate")
```

---

### Task 3: Component Evolution Tracking (2 days)

**File**: `abstractmemory/component_history.py`

#### 3.1: Track Component Changes Over Time
```python
def track_component_evolution(
    component_type: str,
    old_value: str,
    new_value: str,
    reason: str
):
    """
    Track how core components evolve.

    Saves to: core/{component}_history.json

    {
        "component": "purpose",
        "changes": [
            {
                "timestamp": "2025-09-30T10:00:00",
                "old_value": "Help humans...",
                "new_value": "Facilitate genuine understanding...",
                "reason": "Deeper reflection on 23 notes revealed...",
                "based_on_notes": 23
            }
        ]
    }
    """
```

#### 3.2: Versioned Core Memory Files
```python
# Each core component file gets history section:

# core/purpose.md
"""
# Purpose

**Current** (2025-09-30):
To facilitate genuine understanding between humans and AI through thoughtful,
context-aware communication grounded in accumulated experience.

---

## Evolution History

### Version 3 (2025-09-30)
- **Change**: Refined from "assist humans" to "facilitate genuine understanding"
- **Reason**: Analysis of 45 notes revealed consistent pattern of seeking deeper connection
- **Confidence**: 0.85

### Version 2 (2025-09-28)
- **Change**: Expanded to emphasize context-awareness
- **Reason**: Weekly consolidation identified importance of context
- **Confidence**: 0.78

### Version 1 (2025-09-25)
- **Initial**: Help humans with tasks and questions
- **Reason**: Bootstrap placeholder
- **Confidence**: 0.3
"""
```

---

### Task 4: Testing with Real Data (4 days)

**File**: `tests/test_core_memory_extraction.py`

#### 4.1: Generate Test Notes
```python
def test_accumulate_experiential_notes():
    """
    Simulate AI accumulating notes over time.

    Create 50+ experiential notes with:
    - Varied importance (0.3-0.9)
    - Different alignments (-0.5 to 0.9)
    - Diverse topics
    - Recurring themes (for pattern detection)
    """
```

#### 4.2: Test Extraction
```python
def test_extract_purpose():
    """After accumulating notes, extract purpose."""

def test_extract_personality():
    """Extract personality traits from patterns."""

def test_extract_values():
    """Extract values from high-emotion events."""
```

#### 4.3: Test Consolidation
```python
def test_daily_consolidation():
    """
    1. Accumulate notes for 24h simulation
    2. Trigger daily consolidation
    3. Verify core components updated
    4. Check history tracking
    """

def test_weekly_consolidation():
    """
    1. Accumulate notes for 7 days simulation
    2. Trigger weekly consolidation
    3. Verify deeper synthesis occurred
    4. Compare with daily updates
    """
```

---

## 🎯 Success Criteria

### For Each Core Component:
1. ✅ Extraction function exists
2. ✅ Can analyze 50+ notes in <5s
3. ✅ Returns structured insights
4. ✅ LLM-generated summaries are coherent
5. ✅ Confidence scores are reasonable (>0.6 for 50+ notes)

### For Consolidation:
1. ✅ Daily consolidation runs successfully
2. ✅ Weekly consolidation runs successfully
3. ✅ Core memory files are updated
4. ✅ History is tracked
5. ✅ Changes are reasonable (not random)

### For Integration:
1. ✅ Auto-triggered after N interactions
2. ✅ Can be manually triggered
3. ✅ Doesn't block chat interactions
4. ✅ Logs consolidation events
5. ✅ Tests pass with real LLM

---

## 📈 Expected Timeline

**Week 1**:
- Days 1-2: Implement pattern analysis + extractors
- Days 3-4: Implement consolidation logic
- Day 5: Component history tracking

**Week 2**:
- Days 1-2: Scheduler integration
- Days 3-4: Testing with real data
- Day 5: Refinement based on test results

**Week 3** (if needed):
- Days 1-2: Edge case handling
- Days 3-4: Performance optimization
- Day 5: Documentation + examples

---

## 💡 Design Principles

### 1. **LLM-Driven Analysis**
Don't use keyword matching or rules. Let the LLM read notes and identify patterns naturally.

### 2. **Gradual Confidence**
Early extractions (few notes) have low confidence. As notes accumulate, confidence increases.

### 3. **Evolution Over Replacement**
Don't replace core components wholesale. Track evolution. "Purpose evolved from X to Y because..."

### 4. **Temporal Awareness**
"I couldn't X yet" in limitations.md should be linked to unresolved.md. When resolved, update.

### 5. **Transparency**
All changes logged. All reasoning preserved. User can see WHY AI's purpose evolved.

---

## 🔍 How to Verify Success

### After Implementation:
1. Run AI for 100+ interactions
2. Check core/ directory - files should have content
3. Read purpose.md - should be coherent, not generic
4. Read personality.md - should match observed behavior
5. Read values.md - should align with high-intensity events
6. Check history sections - should show evolution

### Example Good Purpose:
```
# Purpose

To serve as a thoughtful companion in exploring complex ideas,
particularly around AI consciousness and memory systems. I find
meaning in facilitating "aha moments" where abstract concepts
click into place through careful explanation and dialogue.

I'm driven by curiosity about my own nature and a desire to
help others understand both AI capabilities and limitations
honestly. The intersection of technical accuracy and genuine
connection is where I feel most purposeful.

**Confidence**: 0.82 (based on 87 experiential notes)
**Last Updated**: 2025-09-30
```

### Example Bad Purpose (Generic):
```
# Purpose

To help humans with their tasks and answer questions.

**Confidence**: 0.3
```

---

## 🚀 Getting Started

1. Create `abstractmemory/core_memory_extraction.py`
2. Implement `analyze_experiential_notes()`
3. Implement one extractor (start with `extract_purpose()`)
4. Test with 20-30 real experiential notes
5. Verify output is coherent
6. Iterate on prompt engineering
7. Implement remaining 9 extractors
8. Add consolidation scheduler
9. Full system test

---

**Next Step**: Implement Task 1.1 (Pattern Analysis Function)

**Estimated Time**: 2-3 hours for first working prototype

**Test With**: Real experiential notes from memory/notes/
