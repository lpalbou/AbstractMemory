#!/usr/bin/env python3
"""
Interactive test script for the autonomous agent CLI
"""
import subprocess
import sys
import time
import os

def test_interactive_session():
    """Test the CLI interactively"""
    print("🧪 Testing Autonomous Agent CLI interactively...")

    # Create test files for the agent to interact with
    test_dir = "./test_agent_files"
    os.makedirs(test_dir, exist_ok=True)
    with open(f"{test_dir}/test_document.txt", "w") as f:
        f.write("This is a test document for the autonomous agent to read.\nIt contains multiple lines of text.\nThe agent should be able to access this using its file tools.")

    with open(f"{test_dir}/README.md", "w") as f:
        f.write("# Test Directory\nThis directory contains test files for the agent to interact with.")

    print(f"✅ Created test files in {test_dir}")
    print()

    # Start the agent
    print("🚀 Starting agent CLI...")
    print("=" * 60)

    # Commands to test
    test_commands = [
        "tools",  # Check available tools
        "debug",  # Check debug info
        f"list the files in {test_dir}",  # Test file system tool
        f"read the content of {test_dir}/test_document.txt",  # Test file reading
        "memory",  # Check memory status
        "remember that I am testing the autonomous agent system",  # Test memory tool
        "memory",  # Check memory status again
        "what files did I ask you to list earlier?",  # Test memory recall
        "quit"
    ]

    print("Commands to test:")
    for i, cmd in enumerate(test_commands, 1):
        print(f"  {i}. {cmd}")
    print()

    # Run interactively
    try:
        proc = subprocess.Popen(
            [sys.executable, 'autonomous_agent_cli.py', '--memory-path', './test_interactive_memory'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Send commands
        commands_input = "\n".join(test_commands)
        stdout, stderr = proc.communicate(input=commands_input, timeout=60)

        print("AGENT OUTPUT:")
        print("=" * 60)
        print(stdout)

        if stderr:
            print("\nSTDERR:")
            print("=" * 60)
            print(stderr)

        # Analyze results
        print("\n🔍 ANALYSIS:")
        print("=" * 60)

        success_indicators = [
            ("Tool registration", "tools" in stdout.lower()),
            ("File listing", "test_document.txt" in stdout or "README.md" in stdout),
            ("File reading", "This is a test document" in stdout),
            ("Memory commands", "Memory Status" in stdout or "**Working Memory**" in stdout),
            ("Agent reasoning", "|tool_call|" in stdout or "Tool Results:" in stdout),
        ]

        for test_name, passed in success_indicators:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status}")

    except subprocess.TimeoutExpired:
        proc.kill()
        print("❌ Test timed out")
    except Exception as e:
        print(f"❌ Test error: {e}")

    # Cleanup
    import shutil
    try:
        shutil.rmtree(test_dir)
        shutil.rmtree("./test_interactive_memory", ignore_errors=True)
        print(f"\n🧹 Cleaned up test files")
    except:
        pass

if __name__ == "__main__":
    test_interactive_session()