# Performance Troubleshooting Guide

**Date**: October 4, 2025

---

## 🐌 Issue: REPL is Extremely Slow (10+ minutes per response)

### Symptoms
```
user> please read and summarize @ttm.md
   📎 Attached: ttm.md (2276 chars)

🤖 Thinking...
   📚 Reconstructing context...

[Hangs here for 10+ minutes]
```

### Root Cause

**qwen3-coder:30b is TOO LARGE for CPU inference**

- Model size: **30 billion parameters**
- Inference: CPU only (extremely slow)
- With file attachments: Prompt becomes even larger
- Result: **10-60 minutes per response** on typical hardware

---

## ✅ Solution 1: Use a Smaller Model (Recommended)

### Fast Models (< 10 seconds per response)

```bash
# Option 1: Qwen 2.5 Coder 7B (RECOMMENDED)
python -m repl --model qwen2.5-coder:7b

# Option 2: Qwen 2.5 Coder 1.5B (FASTEST)
python -m repl --model qwen2.5-coder:1.5b

# Option 3: Llama 3.2 3B
python -m repl --model llama3.2:3b
```

### Pull the model first:
```bash
ollama pull qwen2.5-coder:7b
```

### Performance Comparison

| Model | Size | CPU Speed | Quality |
|-------|------|-----------|---------|
| qwen3-coder:30b | 30B | **10-60 min** | Excellent |
| qwen2.5-coder:7b | 7B | **5-15 sec** | Very good ✅ |
| qwen2.5-coder:1.5b | 1.5B | **1-3 sec** | Good ✅ |
| llama3.2:3b | 3B | **2-5 sec** | Good ✅ |

---

## ✅ Solution 2: Use GPU Acceleration

If you have a Mac with Apple Silicon (M1/M2/M3):

```bash
# Ollama automatically uses Metal GPU acceleration
# But 30B models are still slow without enough RAM

# Check if GPU is being used:
ollama ps
```

**Note**: Even with GPU, 30B models require significant VRAM (16GB+)

---

## ✅ Solution 3: Reduce Attachment Size

Large file attachments make prompts huge, slowing generation:

```bash
# Instead of:
user> please read and summarize @large_file.md  # 10,000 chars

# Do:
user> please summarize the key points from @excerpt.md  # 500 chars
```

---

## 🔍 Diagnostic: Check Where It's Hanging

### Enable Verbose Mode

```bash
python -m repl --model qwen2.5-coder:7b --verbose
```

**What you'll see**:

```
🤖 Thinking...
   📚 Reconstructing context...
   INFO: Reconstructing context: user=user, query='...', focus=3
   INFO: Step 1/9: Searching for memories...
   INFO:   → Found 0 directly relevant memories
   INFO: Step 2/9: Following memory links...
   INFO:   → Found 0 connected memories
   ...
   INFO: Step 9/9: Synthesizing context...
   INFO: 🤖 Calling LLM (prompt: ~1234 tokens)...
   INFO:    ⏳ This may take a while with large models

   [This is where it hangs - waiting for Ollama]
```

If it hangs AFTER "Calling LLM", the issue is **Ollama model inference speed**.

---

## 🧪 Test: Verify Ollama is Working

### 1. Test Ollama directly (bypass REPL)

```bash
# Test the 30B model
time ollama run qwen3-coder:30b "What is 2+2?"

# If this takes 5+ minutes, the model is too slow for your hardware
```

### 2. Test with smaller model

```bash
# Pull and test 7B model
ollama pull qwen2.5-coder:7b
time ollama run qwen2.5-coder:7b "What is 2+2?"

# Should complete in 5-15 seconds
```

### 3. Test REPL with smaller model

```bash
python -m repl --model qwen2.5-coder:7b --verbose

user> hello
# Should respond in 5-15 seconds
```

---

## 📊 Expected Performance

### Reconstruction (Fast - < 0.5 sec)

This is **instant** regardless of model size:

```
   INFO: Step 1/9: Searching for memories...
   INFO: Step 2/9: Following memory links...
   ...
   INFO: Step 9/9: Synthesizing context...
```

### LLM Generation (Variable - depends on model)

This is where slowness occurs:

```
   INFO: 🤖 Calling LLM (prompt: ~1234 tokens)...
   [Waiting for model to generate response]
```

| Model Size | Expected Time |
|------------|---------------|
| 1.5B | 1-3 seconds |
| 3B | 2-5 seconds |
| 7B | 5-15 seconds |
| 30B | **10-60 minutes** ⚠️ |

---

## 🛠️ Fixes Applied

### 1. Added Missing Tool
- Fixed: `search_memories_structured` now in ReAct detection list
- File: `abstractmemory/session.py` line 1110

### 2. Reduced Warning Noise
- Changed: "Notes table does not exist yet" from WARNING to DEBUG
- File: `abstractmemory/storage/lancedb_storage.py` line 288

### 3. Better Progress Indicators
- Added: "⏳ This may take a while with large models" warning
- File: `abstractmemory/session.py` line 318

---

## 📝 Recommendations

### For Development/Testing
```bash
# Use fast model
python -m repl --model qwen2.5-coder:7b --verbose
```

### For Production Quality
```bash
# Use balanced model (if you have GPU or patience)
python -m repl --model qwen2.5-coder:7b
```

### For Maximum Quality (if you have time)
```bash
# 30B model (only use if you have:
# - Apple Silicon M2 Ultra or higher
# - 64GB+ RAM
# - Patience for 30-60 min responses)
python -m repl --model qwen3-coder:30b
```

---

## ✅ Verification

Test that everything works:

```bash
# 1. Pull fast model
ollama pull qwen2.5-coder:7b

# 2. Start REPL with verbose mode
python -m repl --model qwen2.5-coder:7b --verbose

# 3. Test basic interaction
user> hello

# Should respond in 5-15 seconds with:
# - Reconstruction steps (instant)
# - LLM generation (5-15 sec)
# - Total time < 20 seconds

# 4. Test file attachment
user> summarize @ttm.md

# Should respond in 10-20 seconds
```

---

## 🎯 Summary

**Problem**: qwen3-coder:30b is too slow (10-60 min per response)

**Solution**: Use qwen2.5-coder:7b instead (5-15 sec per response)

**Command**:
```bash
python -m repl --model qwen2.5-coder:7b --verbose
```

**Result**: **100x faster** responses while maintaining good quality ⚡
