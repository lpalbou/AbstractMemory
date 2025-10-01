# Next Steps Implementation Plan

**Date**: 2025-09-30 (Evening Update)
**Status**: Phases 1-3 COMPLETE | Integration TODO
**Priority**: Phase 3 Integration (2-4 hours)

---

## ✅ What's Complete

### Phase 1: Structured Responses (100%)
- ✅ All 6 memory tools fully implemented
- ✅ 9-step active reconstruction
- ✅ LanceDB storage (5 tables)
- ✅ Dual storage (filesystem + LanceDB)
- ✅ 13/13 tests passing

### Phase 2: Emotional Resonance (100%)
- ✅ LLM assesses (importance, alignment)
- ✅ System calculates (intensity = importance × |alignment|)
- ✅ Temporal anchoring (intensity > 0.7)
- ✅ ZERO keyword matching
- ✅ 5/5 tests passing

### Phase 3: Core Memory Extraction (100% extractors)
- ✅ All 10 extractors implemented (565 lines)
- ✅ LLM-driven analysis (NO keyword matching)
- ✅ Temporal limitations ("cannot YET")
- ✅ Component-specific prompts
- ✅ 4/4 tests passing

**Total: 22/22 tests passing with real Ollama qwen3-coder:30b**

---

## 🎯 Immediate Priority: Phase 3 Integration

**Goal**: Hook consolidation into MemorySession
**Timeline**: 2-4 hours
**Status**: Ready to implement

### Task 1: Add Interaction Counter (30 min)

**File**: `abstractmemory/session.py`

```python
class MemorySession(BasicSession):
    def __init__(self, ...):
        super().__init__(...)
        # ... existing init ...
        
        # Add consolidation tracking
        self.interaction_count = 0
        self.consolidation_frequency = 10  # Every 10 interactions
        self.last_consolidation_time = None
```

### Task 2: Hook into chat() (30 min)

**File**: `abstractmemory/session.py`

```python
def chat(self, user_input: str, user_id: str = None, location: str = None) -> str:
    # ... existing chat logic ...
    
    # Increment counter AFTER successful interaction
    self.interaction_count += 1
    
    # Trigger consolidation if needed
    if self.interaction_count % self.consolidation_frequency == 0:
        logger.info(f"Triggering consolidation after {self.interaction_count} interactions")
        try:
            from .core_memory_extraction import consolidate_core_memory
            results = consolidate_core_memory(self, mode="periodic")
            updated_count = sum(1 for v in results.values() if v)
            logger.info(f"Consolidation complete: {updated_count}/11 components updated")
        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
    
    return answer
```

### Task 3: Add Manual Trigger (15 min)

**File**: `abstractmemory/session.py`

```python
def trigger_consolidation(self, mode: str = "manual") -> Dict[str, bool]:
    """
    Manually trigger core memory consolidation.
    
    Args:
        mode: "manual", "daily", "weekly", or "periodic"
    
    Returns:
        Dict with update status for all 10 components
    """
    from .core_memory_extraction import consolidate_core_memory
    return consolidate_core_memory(self, mode=mode)
```

### Task 4: Add Logging (15 min)

**File**: `abstractmemory/session.py`

```python
# In chat() after consolidation:
if updated_count > 0:
    logger.info(f"Core memory evolution: {list(k for k, v in results.items() if v)}")
```

---

## 🧪 Testing Expansion (2-3 hours)

**Goal**: Test all 7 new extractors individually
**File**: `tests/test_phase3_extraction_full.py`

### Task 1: Test Each Extractor (1-2 hours)

```python
def test_extract_self_model():
    """Test self-model extraction."""
    # Create notes with capability and limitation patterns
    # Run extraction
    # Verify it combines both aspects
    pass

def test_extract_relationships():
    """Test relationship extraction."""
    # Create notes with different users
    # Run extraction
    # Verify per-user dynamics identified
    pass

def test_extract_awareness_development():
    """Test meta-awareness extraction."""
    # Create notes with meta-cognitive content
    # Run extraction
    # Verify level detection (1-5)
    pass

def test_extract_capabilities():
    """Test capabilities extraction."""
    # Create notes with successes
    # Run extraction
    # Verify intellectually honest assessment
    pass

def test_extract_limitations():
    """Test temporal limitations extraction."""
    # Create notes with challenges
    # Run extraction
    # Verify "cannot YET" framing
    # Verify link to unresolved questions
    pass

def test_extract_emotional_significance():
    """Test emotional significance extraction."""
    # Create notes with high emotion_intensity
    # Run extraction
    # Verify chronological anchors identified
    pass

def test_extract_authentic_voice():
    """Test authentic voice extraction."""
    # Create notes with communication preferences
    # Run extraction
    # Verify style patterns identified
    pass

def test_extract_history():
    """Test history extraction."""
    # Create notes spanning multiple sessions
    # Run extraction
    # Verify narrative timeline created
    pass
```

### Task 2: Test Integration (30 min)

```python
def test_consolidation_trigger():
    """Test automatic consolidation every N interactions."""
    session = MemorySession(...)
    
    # Interact 15 times
    for i in range(15):
        session.chat(f"test query {i}", "user", "office")
    
    # Verify consolidation triggered at interaction 10
    assert session.interaction_count == 15
    # Check consolidation occurred (files updated)
    pass

def test_manual_consolidation():
    """Test manual consolidation trigger."""
    session = MemorySession(...)
    
    # Add some notes
    for i in range(5):
        session.chat(f"test {i}", "user", "office")
    
    # Manually trigger
    results = session.trigger_consolidation(mode="manual")
    
    # Verify results structure
    assert "purpose_updated" in results
    assert "limitations_updated" in results
    pass
```

---

## ⚠️ Partially Complete Work

### Phase 5: Library Memory (80% → 100%)

**Goal**: Auto-capture everything AI reads
**Timeline**: 1 week

#### Task 1: Hook File Operations (2 days)

**File**: `abstractmemory/library_capture.py` (NEW)

```python
def capture_file_read(file_path: str, content: str, session):
    """
    Auto-capture when AI reads a file.
    
    Called by: 
    - File reading tools
    - Code execution contexts
    - Documentation lookups
    """
    # 1. Calculate doc_hash
    doc_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    # 2. Store in library/documents/{hash}/
    doc_dir = session.memory_base_path / "library" / "documents" / doc_hash
    doc_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Save content
    (doc_dir / "content.md").write_text(content)
    
    # 4. Save metadata
    metadata = {
        "source_path": str(file_path),
        "doc_hash": doc_hash,
        "first_accessed": datetime.now().isoformat(),
        "access_count": 1,
        "content_type": detect_content_type(file_path)
    }
    (doc_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    
    # 5. Store in LanceDB
    if session.storage:
        session.storage.add_library_document(...)
```

#### Task 2: Integrate with Session (1 day)

**File**: `abstractmemory/session.py`

```python
# In chat() or when reading context:
if file_read_occurred:
    from .library_capture import capture_file_read
    capture_file_read(file_path, content, self)
```

#### Task 3: Access Pattern Tracking (2 days)

```python
def track_library_access(doc_hash: str, session):
    """Track when AI accesses a library document."""
    # Increment access_count
    # Update last_accessed
    # Calculate importance_score (access_count × recency)
```

---

### Phase 6: User Profile Emergence (30% → 100%)

**Goal**: Auto-generate user profiles from interactions
**Timeline**: 1-2 weeks

#### Task 1: Analyze Per-User Interactions (3 days)

**File**: `abstractmemory/user_profile_extraction.py` (NEW)

```python
def extract_user_profile(user_id: str, session) -> Dict[str, str]:
    """
    Analyze verbatim interactions to extract user profile.
    
    Returns:
        {
            "profile": "User's background, interests, goals...",
            "preferences": "Communication style, depth preference...",
            "relationship": "Collaboration style, trust level..."
        }
    """
    # 1. Collect verbatim interactions for user
    verbatim_dir = session.memory_base_path / "verbatim" / user_id
    
    # 2. Analyze patterns with LLM
    # - What does user ask about?
    # - How do they communicate?
    # - What's their expertise level?
    # - Collaboration style?
    
    # 3. Generate profile.md
    # 4. Generate preferences.md
```

#### Task 2: Auto-Update on Interactions (2 days)

```python
# In MemorySession.chat():
# Every 10 interactions with a user, update their profile
if self.interaction_count_per_user[user_id] % 10 == 0:
    extract_user_profile(user_id, self)
```

#### Task 3: Use in Context Reconstruction (1 day)

```python
# In reconstruct_context():
user_profile = load_user_profile(user_id)
# Include in context synthesis
```

---

## 📋 Implementation Order

### Week 1: Phase 3 Integration + Testing
**Days 1-2**: Integration
- Add interaction counter
- Hook consolidation into chat()
- Add manual trigger
- Add logging

**Days 3-5**: Expand test suite
- Test all 7 new extractors
- Test integration triggers
- Validate temporal limitations framing
- Test with real LLM

### Week 2: Phase 5 Complete
**Days 1-2**: Library auto-capture
- Hook file read operations
- Store in library/documents/

**Days 3-4**: Access tracking
- Track access patterns
- Calculate importance scores

**Day 5**: Integration
- Use in reconstruct_context()
- Test end-to-end

### Weeks 3-4: Phase 6 Complete
**Days 1-3**: User profile extraction
- Analyze per-user interactions
- Extract patterns with LLM

**Days 4-5**: Auto-update
- Trigger on N interactions
- Store in people/{user}/

**Days 6-7**: Integration
- Use in reconstruct_context()
- Test full system

---

## 🎯 Success Criteria

### Phase 3 Integration Complete When:
- ✅ Consolidation hooks into chat()
- ✅ Automatic triggers working (every N interactions)
- ✅ Manual trigger available
- ✅ Logging operational
- ✅ Tests passing (integration tests added)

### Phase 5 Complete When:
- ✅ Auto-capture working on file reads
- ✅ Access patterns tracked
- ✅ Importance scores calculated
- ✅ Used in reconstruct_context()
- ✅ Tests passing

### Phase 6 Complete When:
- ✅ User profiles auto-generated
- ✅ Updated every N interactions
- ✅ Used in reconstruct_context()
- ✅ Tests passing

---

## 🔍 Current Implementation Status

### Working Right Now:
1. ✅ All 6 memory tools
2. ✅ 9-step active reconstruction
3. ✅ Emotional resonance system
4. ✅ Temporal anchoring
5. ✅ All 10 core memory extractors
6. ✅ Dual storage (filesystem + LanceDB)
7. ✅ Real LLM integration
8. ✅ 22/22 tests passing

### Ready for Integration (2-4 hours):
1. Phase 3: Hook consolidation into MemorySession
2. Add automatic triggers
3. Expand test suite

### Remaining Work (2-4 weeks):
1. Phase 5: Library auto-capture (1 week)
2. Phase 6: User profile emergence (1-2 weeks)
3. Component version tracking (optional)
4. Advanced analytics (optional)

---

## 💡 Quick Start (After Integration)

```python
from abstractmemory import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider

# Initialize
provider = OllamaProvider(model="qwen3-coder:30b")
session = MemorySession(
    provider=provider,
    memory_base_path="./memory",
    consolidation_frequency=10  # Consolidate every 10 interactions
)

# Chat normally - consolidation happens automatically
for i in range(15):
    response = session.chat(f"Question {i}", user_id="alice", location="office")
    # Consolidation triggers at interaction 10

# Manual consolidation anytime
results = session.trigger_consolidation()
print(f"Updated: {sum(results.values())}/11 components")

# Check extracted identity
print((session.memory_base_path / "core" / "purpose.md").read_text())
print((session.memory_base_path / "core" / "limitations.md").read_text())
```

---

## 📊 Progress Tracking

### Phases Complete: 7/12
- ✅ Phase 1: Structured Responses
- ✅ Phase 2: Emotional Resonance
- ✅ Phase 3: Core Memory Extraction (extractors)
- ✅ Phase 4: Enhanced Memory Types
- ✅ Phase 7: Active Reconstruction
- ✅ Phase 9: Rich Metadata
- ✅ Phase 11: Testing

### Phases Partial: 3/12
- ⚠️ Phase 3: Integration (TODO)
- ⚠️ Phase 5: Library Memory (80%)
- ⚠️ Phase 6: User Profiles (30%)

### Phases TODO: 2/12
- ⏳ Phase 8: Advanced Tools
- ⏳ Phase 12: Documentation (80%)

**Overall: ~85% complete**

---

**"Memory is the diary we all carry about with us."** - Oscar Wilde

**Next session: Hook consolidation into MemorySession.chat() (2-4 hours)**
