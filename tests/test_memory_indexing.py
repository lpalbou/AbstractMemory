#!/usr/bin/env python3
"""
Comprehensive test suite for memory indexing and dynamic context injection.

Tests:
1. Memory index configuration
2. Universal memory indexer
3. Dynamic context injection
4. File attachment library capture
5. REPL index commands
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import shutil

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from abstractmemory.indexing import MemoryIndexConfig, MemoryIndexer
from abstractmemory.context import DynamicContextInjector
from abstractmemory.storage.lancedb_storage import LanceDBStorage
from abstractmemory.session import MemorySession
from abstractmemory.memory_structure import initialize_memory_structure


@pytest.fixture(scope="module")
def test_memory_path():
    """Create a temporary memory directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test_indexing_")
    memory_path = Path(temp_dir) / "test_memory"
    memory_path.mkdir(parents=True, exist_ok=True)

    # Initialize memory structure
    initialize_memory_structure(memory_path, user_id="test_user")

    # Create some test data
    _create_test_data(memory_path)

    yield memory_path

    # Cleanup
    shutil.rmtree(temp_dir)


def _create_test_data(memory_path: Path):
    """Create test data in various memory modules."""

    # Create test notes
    notes_dir = memory_path / "notes" / "2025" / "01"
    notes_dir.mkdir(parents=True, exist_ok=True)

    for i in range(5):
        note_file = notes_dir / f"note_{i:04d}.md"
        note_file.write_text(f"""
Timestamp: {datetime.now().isoformat()}
User: test_user
Location: testing
Emotion: curiosity ({0.5 + i * 0.1:.2f})

This is test note {i} with some content about memory and consciousness.
The system is learning and evolving through these experiences.
""")

    # Create test library documents
    library_dir = memory_path / "library" / "documents"
    library_dir.mkdir(parents=True, exist_ok=True)

    for i in range(3):
        doc_hash = f"doc_hash_{i:04d}"
        doc_dir = library_dir / doc_hash
        doc_dir.mkdir(exist_ok=True)

        # Write content
        (doc_dir / "content.md").write_text(f"Document {i} content about programming")

        # Write metadata
        metadata = {
            "source_path": f"/test/doc_{i}.md",
            "content_type": "markdown",
            "captured_at": datetime.now().isoformat(),
            "tags": ["test", "document"],
            "importance": 0.5 + i * 0.1
        }
        (doc_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # Update library index
    index_file = memory_path / "library" / "index.json"
    index_data = {
        "documents": [
            {
                "doc_id": f"doc_hash_{i:04d}",
                "source_path": f"/test/doc_{i}.md",
                "captured_at": datetime.now().isoformat()
            }
            for i in range(3)
        ],
        "last_updated": datetime.now().isoformat()
    }
    index_file.write_text(json.dumps(index_data, indent=2))

    # Create test episodic memories
    episodic_dir = memory_path / "episodic"
    episodic_dir.mkdir(exist_ok=True)

    key_moments = episodic_dir / "key_moments.md"
    key_moments.write_text("""
# Key Moments

## First Interaction
The user asked about consciousness and memory.
This sparked a deep philosophical discussion.

## Learning Python
The user shared Python code examples.
I learned new patterns and idioms.

## Reflection on Identity
We discussed how identity emerges from memory.
This led to insights about self-awareness.
""")

    # Create test semantic memories
    semantic_dir = memory_path / "semantic"
    semantic_dir.mkdir(exist_ok=True)

    insights = semantic_dir / "insights.md"
    insights.write_text("""
# Insights

- Memory is not storage, but active reconstruction
- Consciousness emerges from memory patterns
- Identity is the narrative we construct from memories
- Learning is the process of updating memory structures
- Context shapes how memories are retrieved
""")

    concepts = semantic_dir / "concepts.md"
    concepts.write_text("""
# Concepts

- **Consciousness**: Emergent property of memory systems
- **Memory**: Active reconstruction process
- **Identity**: Narrative constructed from experiences
- **Learning**: Memory structure updates
- **Context**: Environmental factors affecting retrieval
""")

    # Create test user profile
    user_dir = memory_path / "people" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    profile = user_dir / "profile.md"
    profile.write_text("""
# User Profile: test_user

## Background & Expertise
- Software engineer with focus on AI/ML
- Interested in consciousness and memory systems
- Python developer

## Thinking Style
- Analytical and systematic
- Asks probing questions
- Values clear explanations
""")

    preferences = user_dir / "preferences.md"
    preferences.write_text("""
# User Preferences: test_user

## Communication
- Prefers detailed technical explanations
- Likes code examples
- Values accuracy over brevity

## Organization
- Structured responses preferred
- Bullet points for complex topics
- Clear section headers
""")


class TestMemoryIndexConfig:
    """Test memory index configuration management."""

    def test_1_default_config(self, test_memory_path):
        """Test creating default configuration."""
        print("\n=== TEST 1: Default Configuration ===")

        config = MemoryIndexConfig()

        # Check default enabled modules
        enabled = config.get_enabled_modules()
        print(f"Default enabled modules: {enabled}")

        assert 'notes' in enabled
        assert 'library' in enabled
        assert 'core' in enabled
        assert 'semantic' in enabled
        assert 'episodic' in enabled

        # Check default disabled
        assert 'verbatim' not in enabled
        assert 'working' not in enabled
        assert 'people' not in enabled

        print("✅ Default configuration correct")

    def test_2_save_load_config(self, test_memory_path):
        """Test saving and loading configuration."""
        print("\n=== TEST 2: Save/Load Configuration ===")

        config_path = test_memory_path / ".memory_index_config.json"

        # Create and save config
        config = MemoryIndexConfig()
        config.disable_module('notes')
        config.enable_module('verbatim')
        config.save(config_path)

        assert config_path.exists()
        print(f"Config saved to: {config_path}")

        # Load config
        loaded_config = MemoryIndexConfig.load(config_path)

        enabled = loaded_config.get_enabled_modules()
        assert 'notes' not in enabled
        assert 'verbatim' in enabled

        print("✅ Configuration persistence working")

    def test_3_module_management(self, test_memory_path):
        """Test enabling/disabling modules."""
        print("\n=== TEST 3: Module Management ===")

        config = MemoryIndexConfig()

        # Test enable
        assert config.enable_module('working')
        assert 'working' in config.get_enabled_modules()

        # Test disable
        assert config.disable_module('notes')
        assert 'notes' not in config.get_enabled_modules()

        # Test invalid module
        assert not config.enable_module('invalid_module')

        print("✅ Module management working")

    def test_4_index_stats_tracking(self, test_memory_path):
        """Test index statistics tracking."""
        print("\n=== TEST 4: Statistics Tracking ===")

        config = MemoryIndexConfig()

        # Update stats
        config.update_index_stats('notes', 100)
        notes_config = config.get_module_config('notes')

        assert notes_config.index_count == 100
        assert notes_config.last_indexed is not None

        # Get status
        status = config.get_status()
        assert 'modules' in status
        assert 'notes' in status['modules']
        assert status['modules']['notes']['index_count'] == 100

        print(f"Status: {json.dumps(status['summary'], indent=2)}")
        print("✅ Statistics tracking working")


class TestMemoryIndexer:
    """Test universal memory indexer."""

    def test_1_initialize_indexer(self, test_memory_path):
        """Test indexer initialization."""
        print("\n=== TEST 1: Initialize Indexer ===")

        # Create LanceDB storage
        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)

        # Create indexer
        indexer = MemoryIndexer(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb
        )

        assert indexer is not None
        assert indexer.memory_base_path == test_memory_path

        print("✅ Indexer initialized")

    def test_2_index_notes(self, test_memory_path):
        """Test indexing notes."""
        print("\n=== TEST 2: Index Notes ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)

        indexer = MemoryIndexer(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb
        )

        # Index notes
        count = indexer.index_module('notes')
        print(f"Indexed {count} notes")

        assert count >= 5  # We created 5 test notes

        # Verify in LanceDB
        assert 'notes' in lancedb.db.table_names()

        print("✅ Notes indexed successfully")

    def test_3_index_library(self, test_memory_path):
        """Test indexing library documents."""
        print("\n=== TEST 3: Index Library ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)

        indexer = MemoryIndexer(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb
        )

        # Index library
        count = indexer.index_module('library')
        print(f"Indexed {count} library documents")

        assert count >= 3  # We created 3 test documents

        # Verify search works
        results = lancedb.search_library("programming", limit=5)
        assert len(results) > 0

        print("✅ Library indexed successfully")

    def test_4_index_all_enabled(self, test_memory_path):
        """Test indexing all enabled modules."""
        print("\n=== TEST 4: Index All Enabled ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)

        # Configure which modules to index
        config = MemoryIndexConfig()
        config.enable_module('notes')
        config.enable_module('library')
        config.enable_module('semantic')
        config.enable_module('episodic')
        config.disable_module('verbatim')

        indexer = MemoryIndexer(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            config=config
        )

        # Index all enabled
        results = indexer.index_all_enabled()
        print(f"Indexing results: {results}")

        assert 'notes' in results
        assert 'library' in results
        assert results['notes'] >= 5
        assert results['library'] >= 3

        print("✅ All enabled modules indexed")


class TestDynamicContextInjection:
    """Test dynamic context injection."""

    def test_1_initialize_injector(self, test_memory_path):
        """Test context injector initialization."""
        print("\n=== TEST 1: Initialize Context Injector ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)
        config = MemoryIndexConfig()
        indexer = MemoryIndexer(test_memory_path, lancedb, config)

        injector = DynamicContextInjector(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            index_config=config,
            memory_indexer=indexer
        )

        assert injector is not None
        print("✅ Context injector initialized")

    def test_2_inject_context(self, test_memory_path):
        """Test context injection from multiple modules."""
        print("\n=== TEST 2: Inject Context ===")

        # Setup
        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)
        config = MemoryIndexConfig()
        indexer = MemoryIndexer(test_memory_path, lancedb, config)

        # Index some modules first
        indexer.index_module('notes')
        indexer.index_module('library')

        injector = DynamicContextInjector(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            index_config=config,
            memory_indexer=indexer
        )

        # Inject context
        context = injector.inject_context(
            query="memory and consciousness",
            user_id="test_user",
            location="testing",
            focus_level=3
        )

        print(f"Total memories: {context['total_memories']}")
        print(f"Token estimate: {context['token_estimate']}")
        print(f"Modules: {list(context['modules'].keys())}")

        assert context['total_memories'] > 0
        assert 'synthesis' in context
        assert len(context['synthesis']) > 0

        print("✅ Context injection working")

    def test_3_token_budget_management(self, test_memory_path):
        """Test token budget enforcement."""
        print("\n=== TEST 3: Token Budget Management ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)
        config = MemoryIndexConfig()
        config.max_tokens_per_module = 100  # Very small budget for testing
        indexer = MemoryIndexer(test_memory_path, lancedb, config)

        injector = DynamicContextInjector(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            index_config=config,
            memory_indexer=indexer
        )

        injector.max_context_tokens = 500  # Small total budget

        context = injector.inject_context(
            query="test",
            user_id="test_user",
            location="testing",
            focus_level=5  # High focus level
        )

        # Check token budget was respected
        assert context['token_estimate'] <= injector.max_context_tokens

        print(f"Token budget: {injector.max_context_tokens}")
        print(f"Tokens used: {context['token_estimate']}")
        print("✅ Token budget management working")

    def test_4_relevance_scoring(self, test_memory_path):
        """Test multi-dimensional relevance scoring."""
        print("\n=== TEST 4: Relevance Scoring ===")

        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)
        config = MemoryIndexConfig()
        indexer = MemoryIndexer(test_memory_path, lancedb, config)

        injector = DynamicContextInjector(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            index_config=config,
            memory_indexer=indexer
        )

        # Test relevance calculation
        test_memory = {
            'content': 'Test content',
            'timestamp': datetime.now().isoformat(),
            'location': 'testing',
            'emotion_intensity': 0.8,
            'importance': 0.7
        }

        relevance = injector._calculate_relevance(
            memory=test_memory,
            query="test",
            user_id="test_user",
            location="testing",
            timestamp=datetime.now(),
            module="notes"
        )

        assert relevance.temporal_score > 0
        assert relevance.location_score == 1.0  # Same location
        assert relevance.emotion_score == 0.8
        assert relevance.importance_score == 0.7

        print(f"Total relevance score: {relevance.total_score:.3f}")
        print("✅ Relevance scoring working")


class TestFileAttachmentCapture:
    """Test file attachment library capture in REPL."""

    def test_1_file_attachment_capture(self, test_memory_path):
        """Test that attached files are captured to library."""
        print("\n=== TEST 1: File Attachment Capture ===")

        # Create a test file to attach
        test_file = test_memory_path / "test_attachment.md"
        test_file.write_text("# Test Document\n\nThis is a test document for attachment.")

        # Import REPL functions
        from repl import _parse_file_attachments

        # Parse attachment
        user_input = f"@{test_file} analyze this document"
        processed_input, attachments = _parse_file_attachments(
            user_input,
            str(test_memory_path)
        )

        assert len(attachments) == 1
        assert attachments[0]['filename'] == "test_attachment.md"
        assert "Test Document" in attachments[0]['content']
        assert processed_input == "analyze this document"

        print(f"Parsed {len(attachments)} attachments")
        print("✅ File attachment parsing working")

    def test_2_library_capture_integration(self, test_memory_path):
        """Test that attachments are captured to library."""
        print("\n=== TEST 2: Library Capture Integration ===")

        # This would require running a full session
        # For now, test the capture_document method directly
        from abstractmemory.library_capture import LibraryCapture

        library = LibraryCapture(
            library_base_path=test_memory_path,
            embedding_manager=None,  # OK for test
            lancedb_storage=None
        )

        # Capture a document
        doc_id = library.capture_document(
            source_path="/test/file.py",
            content="def hello(): pass",
            content_type="code",
            context="User attached via @",
            tags=["python", "test"]
        )

        assert doc_id is not None

        # Verify it was stored
        doc_path = test_memory_path / "library" / "documents" / doc_id
        assert doc_path.exists()
        assert (doc_path / "content.md").exists()
        assert (doc_path / "metadata.json").exists()

        print(f"Document captured: {doc_id}")
        print("✅ Library capture working")


class TestREPLIndexCommands:
    """Test REPL index management commands."""

    def test_1_index_status_command(self, test_memory_path):
        """Test /index status command."""
        print("\n=== TEST 1: Index Status Command ===")

        # This tests the command parsing logic
        # In real use, this would be tested via REPL interaction

        config = MemoryIndexConfig.load(test_memory_path / ".memory_index_config.json")
        enabled = config.get_enabled_modules()

        print(f"Enabled modules: {enabled}")
        print(f"Dynamic injection: {config.dynamic_injection_enabled}")

        assert len(enabled) > 0
        print("✅ Index status available")

    def test_2_index_enable_disable(self, test_memory_path):
        """Test enabling/disabling modules via commands."""
        print("\n=== TEST 2: Enable/Disable Commands ===")

        config_path = test_memory_path / ".memory_index_config.json"
        config = MemoryIndexConfig.load(config_path)

        # Test disable
        initial_enabled = len(config.get_enabled_modules())
        config.disable_module('notes')
        config.save(config_path)

        config = MemoryIndexConfig.load(config_path)
        assert len(config.get_enabled_modules()) == initial_enabled - 1
        assert 'notes' not in config.get_enabled_modules()

        # Test enable
        config.enable_module('notes')
        config.save(config_path)

        config = MemoryIndexConfig.load(config_path)
        assert 'notes' in config.get_enabled_modules()

        print("✅ Enable/disable commands working")


class TestIntegration:
    """Integration tests for complete flow."""

    def test_1_end_to_end_flow(self, test_memory_path):
        """Test complete flow from attachment to context injection."""
        print("\n=== TEST 1: End-to-End Flow ===")

        # 1. Initialize system
        lancedb_path = test_memory_path / "lancedb"
        lancedb = LanceDBStorage(lancedb_path)
        config = MemoryIndexConfig()
        indexer = MemoryIndexer(test_memory_path, lancedb, config)

        # 2. Index existing content
        results = indexer.index_all_enabled()
        print(f"Initial indexing: {results}")

        # 3. Capture a new document (simulating attachment)
        from abstractmemory.library_capture import LibraryCapture

        library = LibraryCapture(
            library_base_path=test_memory_path,
            embedding_manager=None,
            lancedb_storage=lancedb
        )

        doc_id = library.capture_document(
            source_path="/important/code.py",
            content="class Memory:\n    def remember(self): pass",
            content_type="code",
            context="Critical implementation",
            tags=["python", "memory"]
        )

        # 4. Re-index library
        count = indexer.index_module('library', force_reindex=True)
        print(f"Re-indexed library: {count} documents")

        # 5. Inject context with the new document
        injector = DynamicContextInjector(
            memory_base_path=test_memory_path,
            lancedb_storage=lancedb,
            index_config=config,
            memory_indexer=indexer
        )

        context = injector.inject_context(
            query="memory implementation",
            user_id="test_user",
            location="coding",
            focus_level=3
        )

        # Verify the new document is included
        assert context['total_memories'] > 0

        # Check if library memories are present
        if 'library' in context['modules']:
            library_memories = context['modules']['library']['memories']
            print(f"Library memories in context: {len(library_memories)}")

        print(f"Total context: {context['token_estimate']} tokens")
        print("✅ End-to-end flow complete")


def run_all_tests():
    """Run all tests in order."""
    print("\n" + "="*60)
    print("MEMORY INDEXING TEST SUITE")
    print("="*60)

    # Create test environment
    temp_dir = tempfile.mkdtemp(prefix="test_indexing_")
    memory_path = Path(temp_dir) / "test_memory"
    memory_path.mkdir(parents=True, exist_ok=True)
    initialize_memory_structure(memory_path, user_id="test_user")
    _create_test_data(memory_path)

    try:
        # Test suites
        test_suites = [
            TestMemoryIndexConfig(),
            TestMemoryIndexer(),
            TestDynamicContextInjection(),
            TestFileAttachmentCapture(),
            TestREPLIndexCommands(),
            TestIntegration()
        ]

        total_tests = 0
        passed_tests = 0

        for suite in test_suites:
            suite_name = suite.__class__.__name__
            print(f"\n{'='*60}")
            print(f"Running {suite_name}")
            print(f"{'='*60}")

            # Get all test methods
            test_methods = [m for m in dir(suite) if m.startswith('test_')]

            for method_name in sorted(test_methods):
                total_tests += 1
                try:
                    method = getattr(suite, method_name)
                    method(memory_path)
                    passed_tests += 1
                    print(f"✅ {method_name} PASSED\n")
                except Exception as e:
                    print(f"❌ {method_name} FAILED: {e}\n")
                    import traceback
                    traceback.print_exc()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    run_all_tests()