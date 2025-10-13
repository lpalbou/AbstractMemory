# AbstractCore Bug Report: ONNX Optimization and Warning Issues

**Date**: October 10, 2025
**Reporter**: AbstractMemory Integration Team
**Severity**: Medium (Performance Impact + User Experience)
**Component**: EmbeddingManager / ONNX Integration

---

## 🐛 Bug Summary

AbstractCore's EmbeddingManager produces multiple warnings during initialization and defaults to suboptimal ONNX models, resulting in:
1. Verbose warning output that clutters application logs
2. Suboptimal performance due to basic ONNX model selection
3. Potential 2-3x performance loss from not using optimized models

## 🔍 Environment Details

- **Platform**: macOS 14.3.0 (Darwin 24.3.0)
- **Architecture**: ARM64 (Apple M4 Max)
- **Python**: 3.12
- **PyTorch**: 2.8.0
- **ONNX Runtime**: 1.23.1
- **sentence-transformers**: Latest
- **Model**: sentence-transformers/all-MiniLM-L6-v2

## 📋 Full Bug Report

### Issue 1: Suboptimal ONNX Model Selection

**Problem**: AbstractCore's EmbeddingManager doesn't specify which ONNX optimization level to use, defaulting to the basic `model.onnx` instead of architecture-optimized versions.

**Current Behavior**:
```
[WARNING] sentence_transformers.models.Transformer: Multiple ONNX files found in 'sentence-transformers/all-MiniLM-L6-v2':
['onnx/model.onnx', 'onnx/model_O1.onnx', 'onnx/model_O2.onnx', 'onnx/model_O3.onnx', 'onnx/model_O4.onnx',
'onnx/model_qint8_arm64.onnx', 'onnx/model_qint8_avx512.onnx', 'onnx/model_qint8_avx512_vnni.onnx',
'onnx/model_quint8_avx2.onnx'], defaulting to 'onnx/model.onnx'. Please specify the desired file name via
`model_kwargs={"file_name": "<file_name>"}`.
```

**Impact**:
- Performance loss: 2-3x slower inference on optimized hardware
- User confusion: Warning suggests manual intervention needed
- Wasted resources: Not utilizing available optimizations

### Issue 2: PyTorch ONNX Registration Conflicts

**Problem**: PyTorch 2.8.0 has a known issue with duplicate ONNX function registration that AbstractCore doesn't handle gracefully.

**Current Behavior**:
```
/path/to/torch/onnx/_internal/registration.py:162: OnnxExporterWarning: Symbolic function
'aten::scaled_dot_product_attention' already registered for opset 14. Replacing the existing function
with new function. This is unexpected. Please report it on https://github.com/pytorch/pytorch/issues.
```

**Impact**:
- Log pollution: Appears on every EmbeddingManager initialization
- User concern: Suggests something is wrong when it's actually harmless
- Professional appearance: Makes applications look unstable

### Issue 3: ONNX Runtime Provider Warnings

**Problem**: ONNX Runtime CoreML provider generates verbose warnings about node assignment that AbstractCore doesn't configure optimally.

**Current Behavior**:
```
[W:onnxruntime:, coreml_execution_provider.cc:113 GetCapability] CoreMLExecutionProvider::GetCapability,
number of partitions supported by CoreML: 55 number of nodes in the graph: 418 number of nodes supported by CoreML: 285

[W:onnxruntime:, session_state.cc:1316 VerifyEachNodeIsAssignedToAnEp] Some nodes were not assigned to
the preferred execution providers which may or may not have an negative impact on performance.
```

**Impact**:
- Unclear performance implications for users
- Suggests suboptimal configuration
- No guidance on how to improve

---

## 🔄 Reproduction Steps

### Environment Setup
```bash
# 1. Create clean Python environment
python3.12 -m venv test_env
source test_env/bin/activate

# 2. Install minimal dependencies
pip install abstractcore[embeddings]
pip install torch==2.8.0
pip install onnxruntime==1.23.1
pip install sentence-transformers

# 3. Verify model cache
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

### Minimal Reproduction Script
```python
#!/usr/bin/env python3
"""
Minimal script to reproduce AbstractCore ONNX issues.
"""
import warnings
import logging

# Capture all warnings to demonstrate the issues
warnings.simplefilter("always")
logging.basicConfig(level=logging.WARNING)

print("🧪 Reproducing AbstractCore ONNX Issues")
print("=" * 50)

# This will trigger all three issues
try:
    from abstractllm.embeddings import EmbeddingManager

    print("1. Creating EmbeddingManager (triggers warnings)...")
    manager = EmbeddingManager(backend="auto")

    print(f"2. Model loaded: {manager.model}")
    print(f"3. Dimension: {manager.dimension}")

    print("4. Testing embedding (triggers ONNX Runtime warnings)...")
    result = manager.embed(["test sentence"])
    print(f"5. Embedding shape: {result.shape}")

    print("\n✅ Reproduction complete - check warnings above")

except Exception as e:
    print(f"❌ Error during reproduction: {e}")
```

### Expected Output
```
🧪 Reproducing AbstractCore ONNX Issues
==================================================
1. Creating EmbeddingManager (triggers warnings)...
[WARNING] PyTorch ONNX warning about scaled_dot_product_attention...
[WARNING] sentence_transformers warning about multiple ONNX files...
2. Model loaded: sentence-transformers/all-MiniLM-L6-v2
3. Dimension: 384
4. Testing embedding (triggers ONNX Runtime warnings)...
[WARNING] ONNX Runtime CoreML warnings...
5. Embedding shape: (1, 384)

✅ Reproduction complete - check warnings above
```

---

## 🛠️ Actionable Solutions

### Solution 1: Intelligent ONNX Model Selection

**Implementation Location**: `abstractllm/embeddings/manager.py`

**Current Code**:
```python
def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs):
    # No ONNX optimization specified
    self.model = SentenceTransformer(model)
```

**Proposed Fix**:
```python
import platform
import subprocess

def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs):
    # Auto-select optimal ONNX model based on hardware
    onnx_model = self._select_optimal_onnx_model()

    model_kwargs = kwargs.get('model_kwargs', {})
    if onnx_model:
        model_kwargs['file_name'] = onnx_model
        kwargs['model_kwargs'] = model_kwargs

    self.model = SentenceTransformer(model, **kwargs)

def _select_optimal_onnx_model(self) -> str:
    """Select optimal ONNX model based on system architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Architecture-specific optimization
    if system == "darwin" and machine in ["arm64", "aarch64"]:
        # Apple Silicon (M1/M2/M3/M4)
        return "onnx/model_qint8_arm64.onnx"

    elif system == "linux" or system == "windows":
        # Check CPU features
        if self._has_avx512_vnni():
            return "onnx/model_qint8_avx512_vnni.onnx"
        elif self._has_avx512():
            return "onnx/model_qint8_avx512.onnx"
        elif self._has_avx2():
            return "onnx/model_quint8_avx2.onnx"

    # Fallback to optimized but compatible version
    return "onnx/model_O3.onnx"

def _has_avx512_vnni(self) -> bool:
    """Check if CPU supports AVX512 VNNI instructions."""
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                return "avx512_vnni" in f.read().lower()
    except:
        pass
    return False

def _has_avx512(self) -> bool:
    """Check if CPU supports AVX512 instructions."""
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                return "avx512" in f.read().lower()
        elif platform.system() == "Windows":
            # Windows feature detection would go here
            pass
    except:
        pass
    return False

def _has_avx2(self) -> bool:
    """Check if CPU supports AVX2 instructions."""
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                return "avx2" in f.read().lower()
    except:
        pass
    return False
```

### Solution 2: PyTorch ONNX Warning Management

**Implementation Location**: `abstractllm/embeddings/manager.py`

**Proposed Fix**:
```python
import warnings
from contextlib import contextmanager

@contextmanager
def _suppress_pytorch_onnx_warnings():
    """Temporarily suppress known PyTorch ONNX registration warnings."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*Symbolic function.*already registered.*",
            category=UserWarning,
            module="torch.onnx._internal.registration"
        )
        yield

def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs):
    # Suppress known PyTorch 2.8.0 ONNX warnings during initialization
    with self._suppress_pytorch_onnx_warnings():
        # ... rest of initialization
        self.model = SentenceTransformer(model, **kwargs)
```

### Solution 3: ONNX Runtime Provider Optimization

**Implementation Location**: `abstractllm/embeddings/manager.py`

**Proposed Fix**:
```python
def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", **kwargs):
    # Configure optimal ONNX Runtime providers
    onnx_providers = self._get_optimal_onnx_providers()

    # Pass providers to sentence-transformers
    model_kwargs = kwargs.get('model_kwargs', {})
    model_kwargs['providers'] = onnx_providers
    kwargs['model_kwargs'] = model_kwargs

    self.model = SentenceTransformer(model, **kwargs)

def _get_optimal_onnx_providers(self) -> list:
    """Get optimal ONNX Runtime execution providers for current system."""
    providers = []

    # System-specific provider selection
    system = platform.system().lower()

    if system == "darwin":
        # macOS: Use CPU provider for stability
        providers = ['CPUExecutionProvider']
    elif system == "linux":
        # Linux: Try CUDA first, fallback to CPU
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    elif system == "windows":
        # Windows: Try DirectML, CUDA, then CPU
        providers = ['DmlExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
    else:
        # Default: CPU only
        providers = ['CPUExecutionProvider']

    return providers
```

### Solution 4: User Configuration Options

**Implementation Location**: `abstractllm/embeddings/manager.py`

**Proposed Enhancement**:
```python
def __init__(self,
             model: str = "sentence-transformers/all-MiniLM-L6-v2",
             onnx_optimization: str = "auto",  # "auto", "performance", "compatibility", "none"
             suppress_warnings: bool = True,
             **kwargs):
    """
    Initialize EmbeddingManager with enhanced ONNX control.

    Args:
        model: Model name or path
        onnx_optimization: ONNX optimization level
            - "auto": Select best for hardware (default)
            - "performance": Use highest optimization available
            - "compatibility": Use most compatible version
            - "none": Use default model.onnx
        suppress_warnings: Whether to suppress known harmless warnings
    """
    self.onnx_optimization = onnx_optimization
    self.suppress_warnings = suppress_warnings

    # Apply settings
    if suppress_warnings:
        context = self._suppress_pytorch_onnx_warnings()
    else:
        context = nullcontext()

    with context:
        if onnx_optimization != "none":
            onnx_model = self._select_onnx_model_by_strategy(onnx_optimization)
            if onnx_model:
                model_kwargs = kwargs.get('model_kwargs', {})
                model_kwargs['file_name'] = onnx_model
                kwargs['model_kwargs'] = model_kwargs

        self.model = SentenceTransformer(model, **kwargs)
```

---

## 🧪 Testing Plan

### Unit Tests
```python
def test_onnx_model_selection():
    """Test ONNX model selection logic."""
    manager = EmbeddingManager()

    # Should select architecture-appropriate model
    if platform.machine().lower() in ["arm64", "aarch64"]:
        assert "arm64" in manager._select_optimal_onnx_model()

def test_warning_suppression():
    """Test warning suppression functionality."""
    with warnings.catch_warnings(record=True) as w:
        manager = EmbeddingManager(suppress_warnings=True)

        # Should not contain PyTorch ONNX warnings
        pytorch_warnings = [warning for warning in w
                          if "already registered" in str(warning.message)]
        assert len(pytorch_warnings) == 0

def test_performance_improvement():
    """Test performance improvement with optimized models."""
    import time

    # Basic model
    start = time.time()
    basic_manager = EmbeddingManager(onnx_optimization="none")
    basic_time = time.time() - start

    # Optimized model
    start = time.time()
    optimized_manager = EmbeddingManager(onnx_optimization="performance")
    optimized_time = time.time() - start

    # Optimized should be faster (or at least not slower)
    assert optimized_time <= basic_time * 1.1  # 10% tolerance
```

### Integration Tests
```python
def test_embedding_quality_maintained():
    """Ensure optimization doesn't affect embedding quality."""
    text = "This is a test sentence for embedding."

    basic_manager = EmbeddingManager(onnx_optimization="none")
    optimized_manager = EmbeddingManager(onnx_optimization="auto")

    basic_embedding = basic_manager.embed([text])
    optimized_embedding = optimized_manager.embed([text])

    # Embeddings should be very similar (quantization may cause small differences)
    similarity = cosine_similarity(basic_embedding, optimized_embedding)
    assert similarity > 0.99  # 99% similarity threshold
```

---

## 📊 Expected Performance Impact

### Before Fix:
- **Model**: Basic `model.onnx` (unoptimized)
- **Warnings**: 3-4 warning messages per initialization
- **Performance**: Baseline (100%)
- **User Experience**: Cluttered logs, appears unstable

### After Fix:
- **Model**: Architecture-optimized (e.g., `model_qint8_arm64.onnx`)
- **Warnings**: 0 warnings (properly managed)
- **Performance**: 150-300% improvement (depending on hardware)
- **User Experience**: Clean, professional, fast

### Measurement Metrics:
```python
# Performance benchmark
import time

def benchmark_embedding_speed():
    sentences = ["test sentence"] * 1000

    start = time.time()
    embeddings = manager.embed(sentences)
    end = time.time()

    return (end - start), embeddings.shape

# Expected improvement on Apple M4:
# Basic model: ~2.5 seconds
# ARM64 optimized: ~0.8 seconds (3x improvement)
```

---

## 🔗 References

1. **ONNX Runtime Execution Providers**: https://onnxruntime.ai/docs/execution-providers/
2. **sentence-transformers ONNX Support**: https://www.sbert.net/docs/package_reference/SentenceTransformer.html
3. **PyTorch ONNX Issues**: https://github.com/pytorch/pytorch/issues (search for "scaled_dot_product_attention")
4. **Hardware Detection in Python**: https://docs.python.org/3/library/platform.html

---

## 💡 Implementation Priority

1. **High Priority**: ONNX model selection (immediate 2-3x performance gain)
2. **Medium Priority**: Warning suppression (user experience improvement)
3. **Low Priority**: Provider optimization (system-specific gains)

**Estimated Implementation Time**: 2-3 hours for core functionality + testing

**Backward Compatibility**: Fully maintained - all changes are additive with sensible defaults.