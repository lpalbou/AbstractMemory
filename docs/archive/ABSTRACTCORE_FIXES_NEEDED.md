# AbstractCore Fixes Needed - Root Cause Solutions

## 🎯 Issues to Fix in AbstractCore

### 1. **ONNX Model Selection** (High Priority)

**Current Problem**:
```
Multiple ONNX files found in 'sentence-transformers/all-MiniLM-L6-v2':
['onnx/model.onnx', 'onnx/model_O1.onnx', 'onnx/model_O2.onnx', 'onnx/model_O3.onnx', 'onnx/model_O4.onnx', 'onnx/model_qint8_arm64.onnx', 'onnx/model_qint8_avx512.onnx', 'onnx/model_qint8_avx512_vnni.onnx', 'onnx/model_quint8_avx2.onnx'],
defaulting to 'onnx/model.onnx'. Please specify the desired file name via model_kwargs={"file_name": "<file_name>"}
```

**Root Cause**: AbstractCore's EmbeddingManager doesn't specify which ONNX optimization level to use.

**Proper Solution for AbstractCore**:

```python
# In abstractllm/embeddings/manager.py _load_model() method:

def _load_model(self):
    """Load the HuggingFace embedding model with optimal backend."""
    # ... existing code ...

    if backend == EmbeddingBackend.ONNX:
        try:
            # AUTO-SELECT BEST ONNX MODEL BASED ON SYSTEM
            import platform
            import cpuinfo  # or alternative CPU detection

            # Detect optimal ONNX model for system
            onnx_model = self._select_optimal_onnx_model()

            self.model = sentence_transformers.SentenceTransformer(
                self.model_id,
                backend="onnx",
                model_kwargs={"file_name": onnx_model},  # FIX: Specify ONNX file
                trust_remote_code=self.trust_remote_code
            )
            logger.info(f"Loaded {self.model_id} with ONNX backend ({onnx_model})")

def _select_optimal_onnx_model(self) -> str:
    """Select optimal ONNX model based on system capabilities."""
    import platform
    machine = platform.machine().lower()

    # ARM64 Mac (M1/M2/M3/M4)
    if machine in ('arm64', 'aarch64'):
        return "onnx/model_qint8_arm64.onnx"  # Quantized for ARM64

    # Intel/AMD with AVX512 support
    try:
        import cpuinfo
        cpu_flags = cpuinfo.get_cpu_info().get('flags', [])
        if 'avx512f' in cpu_flags:
            return "onnx/model_qint8_avx512_vnni.onnx"  # Best for AVX512
        elif 'avx2' in cpu_flags:
            return "onnx/model_quint8_avx2.onnx"  # Good for AVX2
    except ImportError:
        pass

    # Conservative fallback - highest optimization without quantization
    return "onnx/model_O3.onnx"  # O3 = good performance/accuracy balance
```

### 2. **PyTorch ONNX Registration Warning** (Medium Priority)

**Current Problem**:
```
OnnxExporterWarning: Symbolic function 'aten::scaled_dot_product_attention' already registered for opset 14
```

**Root Cause**: PyTorch 2.8.0 duplicate function registration in ONNX export.

**Proper Solution for AbstractCore**:

```python
# In abstractllm/embeddings/manager.py __init__ or _load_model():

def _suppress_pytorch_onnx_warnings(self):
    """Suppress known PyTorch ONNX duplicate registration warnings."""
    import warnings
    from torch.onnx import _internal

    # Suppress specific PyTorch ONNX warnings that are harmless
    warnings.filterwarnings(
        "ignore",
        category=torch.jit._warnings.OnnxExporterWarning,
        message=".*Symbolic function.*already registered.*"
    )
```

### 3. **ONNX Runtime CoreML Warnings** (Low Priority)

**Current Problem**:
```
CoreMLExecutionProvider::GetCapability, number of partitions supported by CoreML: 55 number of nodes in the graph: 418 number of nodes supported by CoreML: 285
```

**Root Cause**: ONNX Runtime trying to use CoreML on Mac but falling back to CPU for some ops.

**Proper Solution for AbstractCore**:

```python
# In abstractllm/embeddings/manager.py:

def _configure_onnx_providers(self):
    """Configure ONNX Runtime providers based on system."""
    import platform

    if platform.system() == "Darwin":  # macOS
        # Prioritize CPU over CoreML to avoid warnings about partial support
        providers = ["CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]

    return providers

# Then in model loading:
self.model = sentence_transformers.SentenceTransformer(
    self.model_id,
    backend="onnx",
    model_kwargs={
        "file_name": onnx_model,
        "providers": self._configure_onnx_providers()
    },
    trust_remote_code=self.trust_remote_code
)
```

## 🎯 **Implementation Priority**

1. **High**: ONNX model selection - Immediate performance improvement
2. **Medium**: PyTorch warning suppression - Clean logs
3. **Low**: ONNX Runtime provider config - System-specific optimization

## 📋 **Why These Fixes Belong in AbstractCore**

1. **Architectural Separation**: AbstractMemory uses embeddings, AbstractCore provides them
2. **System Optimization**: AbstractCore should handle hardware-specific optimizations
3. **Upstream Fixes**: These warnings affect all AbstractCore users, not just AbstractMemory
4. **Maintainability**: Fixes in one place benefit entire ecosystem

## 🔧 **Temporary Workaround (AbstractMemory)**

Until AbstractCore implements these fixes, AbstractMemory could specify the ONNX model:

```python
# Temporary workaround in session.py:
self.embedding_manager = EmbeddingManager(
    backend="onnx",
    model_kwargs={"file_name": "onnx/model_O3.onnx"}  # Specify optimization level
)
```

But the **proper solution** is implementing these fixes in AbstractCore.