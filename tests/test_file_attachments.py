#!/usr/bin/env python3
"""
Test file attachment functionality in REPL.

Tests the @filename feature that allows attaching file contents to chat input.
"""

import pytest
from pathlib import Path
import tempfile
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repl import _parse_file_attachments, _format_input_with_attachments


def test_1_parse_single_attachment():
    """Test parsing a single @filename reference."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("Test content\nLine 2")
        temp_path = f.name

    try:
        # Test with absolute path
        user_input = f"Please read this @{temp_path}"
        processed_input, attachments = _parse_file_attachments(
            user_input,
            memory_base_path="/tmp"
        )

        assert processed_input == "Please read this"
        assert len(attachments) == 1
        assert attachments[0]['content'] == "Test content\nLine 2"
        assert attachments[0]['filename'] == Path(temp_path).name
        print("✅ test_1_parse_single_attachment passed")

    finally:
        os.unlink(temp_path)


def test_2_parse_multiple_attachments():
    """Test parsing multiple @filename references."""
    # Create two temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f1:
        f1.write("File 1 content")
        temp_path1 = f1.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        f2.write("File 2 content")
        temp_path2 = f2.name

    try:
        user_input = f"Compare @{temp_path1} and @{temp_path2}"
        processed_input, attachments = _parse_file_attachments(
            user_input,
            memory_base_path="/tmp"
        )

        assert processed_input == "Compare  and"
        assert len(attachments) == 2
        assert attachments[0]['content'] == "File 1 content"
        assert attachments[1]['content'] == "File 2 content"
        print("✅ test_2_parse_multiple_attachments passed")

    finally:
        os.unlink(temp_path1)
        os.unlink(temp_path2)


def test_3_parse_memory_relative_path():
    """Test parsing @filename relative to memory_base_path."""
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = Path(tmpdir)
        test_file = memory_path / "core" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Memory content")

        user_input = "Read @core/test.md"
        processed_input, attachments = _parse_file_attachments(
            user_input,
            memory_base_path=str(memory_path)
        )

        assert processed_input == "Read"
        assert len(attachments) == 1
        assert attachments[0]['content'] == "Memory content"
        assert attachments[0]['filename'] == "test.md"
        print("✅ test_3_parse_memory_relative_path passed")


def test_4_parse_nonexistent_file():
    """Test parsing @filename that doesn't exist."""
    user_input = "Read @/nonexistent/file.md"
    processed_input, attachments = _parse_file_attachments(
        user_input,
        memory_base_path="/tmp"
    )

    # Should still process input but with empty attachments
    assert processed_input == "Read"
    assert len(attachments) == 0
    print("✅ test_4_parse_nonexistent_file passed")


def test_5_format_with_attachments():
    """Test formatting input with attached file contents."""
    attachments = [
        {
            'filename': 'test1.md',
            'path': '/tmp/test1.md',
            'content': 'Content 1',
            'size': 9
        },
        {
            'filename': 'test2.txt',
            'path': '/tmp/test2.txt',
            'content': 'Content 2',
            'size': 9
        }
    ]

    enhanced_input = _format_input_with_attachments(
        "User query here",
        attachments
    )

    assert "User query here" in enhanced_input
    assert "--- Attached Files ---" in enhanced_input
    assert "[File: test1.md]" in enhanced_input
    assert "[File: test2.txt]" in enhanced_input
    assert "Content 1" in enhanced_input
    assert "Content 2" in enhanced_input
    print("✅ test_5_format_with_attachments passed")


def test_6_format_without_attachments():
    """Test formatting input without attachments."""
    enhanced_input = _format_input_with_attachments(
        "User query here",
        []
    )

    assert enhanced_input == "User query here"
    assert "--- Attached Files ---" not in enhanced_input
    print("✅ test_6_format_without_attachments passed")


def test_7_end_to_end():
    """Test end-to-end file attachment flow."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("Important information\nThat needs context")
        temp_path = f.name

    try:
        # Parse attachments
        user_input = f"Analyze this document @{temp_path}"
        processed_input, attachments = _parse_file_attachments(
            user_input,
            memory_base_path="/tmp"
        )

        # Format with attachments
        enhanced_input = _format_input_with_attachments(
            processed_input,
            attachments
        )

        # Verify complete flow
        assert "Analyze this document" in enhanced_input
        assert "--- Attached Files ---" in enhanced_input
        assert "Important information" in enhanced_input
        assert "That needs context" in enhanced_input
        print("✅ test_7_end_to_end passed")

    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing File Attachment Functionality")
    print("="*60 + "\n")

    test_1_parse_single_attachment()
    test_2_parse_multiple_attachments()
    test_3_parse_memory_relative_path()
    test_4_parse_nonexistent_file()
    test_5_format_with_attachments()
    test_6_format_without_attachments()
    test_7_end_to_end()

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED (7/7)")
    print("="*60)
