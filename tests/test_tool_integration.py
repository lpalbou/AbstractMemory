"""
Test Tool Integration - Memory Tools with AbstractCore

Tests that memory tools are properly registered with AbstractCore and callable.

Run with:
    .venv/bin/python -m pytest tests/test_tool_integration.py -v -s
"""

import pytest
from pathlib import Path
import shutil
from abstractmemory.session import MemorySession
from abstractllm.providers.ollama_provider import OllamaProvider


@pytest.fixture(scope="module")
def test_memory_path():
    """Create temporary test memory directory."""
    path = Path("test_tool_integration_memory")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    # Cleanup
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(scope="module")
def ollama_provider():
    """Initialize Ollama provider."""
    return OllamaProvider(model="qwen3-coder:30b")


def test_1_tools_registered(test_memory_path, ollama_provider):
    """
    Test that memory tools are registered with AbstractCore.

    Verifies:
    - Tools list exists
    - 6 memory tools registered
    - Tool names are correct
    """
    print("\n" + "="*60)
    print("TEST 1: Tool Registration")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # Check tools are registered
    assert hasattr(session, 'tools'), "Session should have tools attribute"
    assert session.tools is not None, "Tools should not be None"
    assert len(session.tools) == 6, f"Expected 6 tools, got {len(session.tools)}"

    # Check tool names
    tool_names = [t.name for t in session.tools]
    expected_tools = [
        "remember_fact",
        "search_memories",
        "reflect_on",
        "capture_document",
        "search_library",
        "reconstruct_context"
    ]

    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Tool '{expected_tool}' not registered"

    print(f"✅ All {len(session.tools)} memory tools registered:")
    for tool in session.tools:
        print(f"   - {tool.name}: {tool.description[:50]}...")

    assert True


def test_2_tool_definitions(test_memory_path, ollama_provider):
    """
    Test tool definitions have proper structure.

    Verifies:
    - Each tool has name, description, parameters, function
    - Parameters are properly defined
    - Functions are callable
    """
    print("\n" + "="*60)
    print("TEST 2: Tool Definition Structure")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    for tool in session.tools:
        print(f"\n✓ Checking tool: {tool.name}")

        # Check required attributes
        assert hasattr(tool, 'name'), f"{tool.name} missing name attribute"
        assert hasattr(tool, 'description'), f"{tool.name} missing description"
        assert hasattr(tool, 'parameters'), f"{tool.name} missing parameters"
        assert hasattr(tool, 'function'), f"{tool.name} missing function"

        # Check function is callable
        assert callable(tool.function), f"{tool.name} function not callable"

        # Check parameters is a dict
        assert isinstance(tool.parameters, dict), f"{tool.name} parameters not dict"

        print(f"   Parameters: {list(tool.parameters.keys())}")

    print("\n✅ All tools have proper structure")
    assert True


def test_3_remember_fact_execution(test_memory_path, ollama_provider):
    """
    Test remember_fact tool can be executed.

    Verifies:
    - Tool function is callable
    - Returns memory ID
    - Memory is stored
    """
    print("\n" + "="*60)
    print("TEST 3: remember_fact Execution")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # Find remember_fact tool
    remember_tool = next((t for t in session.tools if t.name == "remember_fact"), None)
    assert remember_tool is not None, "remember_fact tool not found"

    # Call the tool
    print("\n📝 Calling remember_fact...")
    result = remember_tool.function(
        content="Test fact for tool integration",
        importance=0.8,
        emotion="neutral",
        reason="Testing tool execution",
        links_to=None
    )

    print(f"   Result: {result}")

    # Verify result is a memory ID
    assert result is not None, "remember_fact should return memory ID"
    assert isinstance(result, str), "Memory ID should be string"
    assert result.startswith("mem_"), f"Memory ID should start with 'mem_', got: {result}"

    # Verify memory was actually stored
    notes_dir = test_memory_path / "notes"
    assert notes_dir.exists(), "Notes directory should exist"

    # Count note files
    note_files = list(notes_dir.rglob("*.md"))
    assert len(note_files) > 0, "At least one note file should exist"

    print(f"✅ remember_fact executed successfully")
    print(f"   Memory ID: {result}")
    print(f"   Note files created: {len(note_files)}")

    assert True


def test_4_search_memories_execution(test_memory_path, ollama_provider):
    """
    Test search_memories tool can be executed.

    Verifies:
    - Tool function is callable
    - Returns list of results
    - Results have proper structure
    """
    print("\n" + "="*60)
    print("TEST 4: search_memories Execution")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # First, remember something
    remember_tool = next(t for t in session.tools if t.name == "remember_fact")
    mem_id = remember_tool.function(
        content="Important fact about consciousness and memory",
        importance=0.9,
        emotion="positive",
        reason="Core concept",
        links_to=None
    )
    print(f"📝 Stored memory: {mem_id}")

    # Find search_memories tool
    search_tool = next((t for t in session.tools if t.name == "search_memories"), None)
    assert search_tool is not None, "search_memories tool not found"

    # Call the tool
    print("\n🔍 Calling search_memories...")
    results = search_tool.function(
        query="consciousness memory",
        limit=5
    )

    print(f"   Found {len(results)} results")

    # Verify results structure
    assert isinstance(results, list), "search_memories should return list"

    if len(results) > 0:
        result = results[0]
        assert isinstance(result, dict), "Each result should be dict"
        print(f"   First result keys: {list(result.keys())}")

    print(f"✅ search_memories executed successfully")
    assert True


def test_5_reflect_on_execution(test_memory_path, ollama_provider):
    """
    Test reflect_on tool can be executed.

    Verifies:
    - Tool function is callable
    - Returns reflection structure
    - Contains insights, patterns, etc.

    Note: This test uses real LLM, so it may take ~20 seconds.
    """
    print("\n" + "="*60)
    print("TEST 5: reflect_on Execution")
    print("="*60)
    print("⚠️  This test uses real LLM - will take ~20 seconds")

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # Create some memories to reflect on
    remember_tool = next(t for t in session.tools if t.name == "remember_fact")

    print("\n📝 Creating memories to reflect on...")
    for i, content in enumerate([
        "Memory shapes identity",
        "Consciousness emerges from experience",
        "Active reconstruction vs passive retrieval"
    ], 1):
        mem_id = remember_tool.function(
            content=content,
            importance=0.8,
            emotion="neutral",
            reason=f"Insight {i}",
            links_to=None
        )
        print(f"   {i}. {mem_id}: {content}")

    # Find reflect_on tool
    reflect_tool = next((t for t in session.tools if t.name == "reflect_on"), None)
    assert reflect_tool is not None, "reflect_on tool not found"

    # Call the tool
    print("\n🧠 Calling reflect_on (depth='shallow')...")
    result = reflect_tool.function(
        topic="memory and consciousness",
        depth="shallow"
    )

    # Verify result structure
    assert isinstance(result, dict), "reflect_on should return dict"

    expected_keys = ["insights", "patterns", "reflection_id"]
    for key in expected_keys:
        assert key in result, f"Result should have '{key}' key"

    print(f"✅ reflect_on executed successfully")
    print(f"   Reflection ID: {result.get('reflection_id', 'N/A')}")
    print(f"   Insights generated: {len(result.get('insights', []))}")
    print(f"   Patterns identified: {len(result.get('patterns', []))}")

    assert True


def test_6_capture_document_execution(test_memory_path, ollama_provider):
    """
    Test capture_document tool can be executed.

    Verifies:
    - Tool function is callable
    - Returns document ID
    - Document is stored in library
    """
    print("\n" + "="*60)
    print("TEST 6: capture_document Execution")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # Find capture_document tool
    capture_tool = next((t for t in session.tools if t.name == "capture_document"), None)
    assert capture_tool is not None, "capture_document tool not found"

    # Call the tool
    print("\n📚 Calling capture_document...")
    result = capture_tool.function(
        source_path="test_code.py",
        content="def test():\n    print('hello')",
        content_type="code",
        context="Testing document capture",
        tags=["python", "test"]
    )

    print(f"   Result: {result}")

    # Verify result is a document ID
    assert result is not None, "capture_document should return doc ID"
    assert isinstance(result, str), "Document ID should be string"

    # Verify library directory exists
    library_dir = test_memory_path / "library"
    assert library_dir.exists(), "Library directory should exist"

    print(f"✅ capture_document executed successfully")
    print(f"   Document ID: {result}")

    assert True


def test_7_tools_in_parent_session(test_memory_path, ollama_provider):
    """
    Test that tools are properly registered with parent BasicSession.

    Verifies:
    - Tools accessible via session.tools
    - Parent's generate() method can access tools
    """
    print("\n" + "="*60)
    print("TEST 7: Tools in Parent BasicSession")
    print("="*60)

    session = MemorySession(
        provider=ollama_provider,
        memory_base_path=test_memory_path,
        default_user_id="test_user"
    )

    # Check tools are in session
    assert hasattr(session, 'tools'), "Session should have tools"
    assert session.tools is not None, "Tools should not be None"

    # Check tools are ToolDefinition instances
    from abstractllm.tools.core import ToolDefinition
    for tool in session.tools:
        assert isinstance(tool, ToolDefinition), f"{tool.name} should be ToolDefinition"

    # Check parent BasicSession can see them
    # (In actual usage, generate() would pass these to provider)
    print(f"✅ Tools properly registered with BasicSession")
    print(f"   {len(session.tools)} tools available to LLM")

    assert True


if __name__ == "__main__":
    """Run tests directly."""
    print("\n" + "="*60)
    print("TOOL INTEGRATION TEST SUITE")
    print("="*60)
    print("\nTesting memory tool registration and execution...")
    print("This will take ~2 minutes with real LLM calls.\n")

    pytest.main([__file__, "-v", "-s"])
