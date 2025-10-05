#!/bin/bash
# Test Commands for Memory Indexing System
# Run these commands to verify the implementation

echo "=========================================="
echo "Memory Indexing System - Test Commands"
echo "=========================================="
echo ""

# Test 1: Run the complete test suite
echo "1️⃣  Running complete test suite..."
echo "Command: .venv/bin/python -m pytest tests/test_memory_indexing.py -v"
echo ""
.venv/bin/python -m pytest tests/test_memory_indexing.py -v
echo ""
echo "✅ Expected: 17/17 tests passing"
echo ""

# Test 2: Run just configuration tests
echo "=========================================="
echo "2️⃣  Running configuration tests only..."
echo "Command: .venv/bin/python -m pytest tests/test_memory_indexing.py::TestMemoryIndexConfig -v"
echo ""
.venv/bin/python -m pytest tests/test_memory_indexing.py::TestMemoryIndexConfig -v
echo ""
echo "✅ Expected: 4/4 tests passing"
echo ""

# Test 3: Run just indexer tests
echo "=========================================="
echo "3️⃣  Running indexer tests only..."
echo "Command: .venv/bin/python -m pytest tests/test_memory_indexing.py::TestMemoryIndexer -v"
echo ""
.venv/bin/python -m pytest tests/test_memory_indexing.py::TestMemoryIndexer -v
echo ""
echo "✅ Expected: 4/4 tests passing"
echo ""

# Test 4: Run dynamic context injection tests
echo "=========================================="
echo "4️⃣  Running dynamic context injection tests..."
echo "Command: .venv/bin/python -m pytest tests/test_memory_indexing.py::TestDynamicContextInjection -v"
echo ""
.venv/bin/python -m pytest tests/test_memory_indexing.py::TestDynamicContextInjection -v
echo ""
echo "✅ Expected: 4/4 tests passing"
echo ""

# Test 5: Check file structure
echo "=========================================="
echo "5️⃣  Checking created files..."
echo ""
echo "New indexing module:"
ls -lh abstractmemory/indexing/*.py
echo ""
echo "New context module:"
ls -lh abstractmemory/context/*.py
echo ""
echo "Test suite:"
ls -lh tests/test_memory_indexing.py
echo ""

# Test 6: Quick integration test
echo "=========================================="
echo "6️⃣  Quick integration test..."
echo "Command: .venv/bin/python -c 'from abstractmemory.indexing import MemoryIndexConfig; config = MemoryIndexConfig(); print(f\"Default enabled modules: {config.get_enabled_modules()}\")'"
echo ""
.venv/bin/python -c "from abstractmemory.indexing import MemoryIndexConfig; config = MemoryIndexConfig(); print(f'Default enabled modules: {config.get_enabled_modules()}')"
echo ""
echo "✅ Expected: ['notes', 'library', 'links', 'core', 'episodic', 'semantic']"
echo ""

# Test 7: Check LanceDB storage enhancements
echo "=========================================="
echo "7️⃣  Checking LanceDB storage methods..."
echo "Command: .venv/bin/python -c 'from abstractmemory.storage.lancedb_storage import LanceDBStorage; print([m for m in dir(LanceDBStorage) if \"add_\" in m])'"
echo ""
.venv/bin/python -c "from abstractmemory.storage.lancedb_storage import LanceDBStorage; print([m for m in dir(LanceDBStorage) if 'add_' in m and not m.startswith('_')])"
echo ""
echo "✅ Expected methods: add_core_memory, add_working_memory, add_episodic_memory, add_semantic_memory, add_people"
echo ""

echo "=========================================="
echo "🎉 All tests complete!"
echo ""
echo "📖 For detailed documentation, see:"
echo "   - docs/summary.md (complete overview)"
echo "   - docs/detailed-actionable-plan.md (original plan)"
echo "   - CLAUDE.md (project status)"
echo ""
echo "🚀 To try in REPL:"
echo "   python -m repl"
echo "   > /index                   # Show index status"
echo "   > /index enable working    # Enable working memory"
echo "   > @filename.py query       # Attach and capture file"
echo "=========================================="
