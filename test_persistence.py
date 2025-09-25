#!/usr/bin/env python3
"""
Test memory persistence across complete session restarts
"""
import subprocess
import sys
import time
import os

def run_session(session_name, commands, memory_path):
    """Run a session with the given commands"""
    print(f"🚀 Running {session_name}...")
    print(f"Commands: {commands}")

    try:
        proc = subprocess.Popen(
            [sys.executable, 'autonomous_agent_cli.py', '--memory-path', memory_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        commands_input = "\n".join(commands)
        stdout, stderr = proc.communicate(input=commands_input, timeout=45)

        print(f"✅ {session_name} completed")
        return stdout, stderr

    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"❌ {session_name} timed out")
        return "", ""
    except Exception as e:
        print(f"❌ {session_name} error: {e}")
        return "", ""

def test_session_persistence():
    """Test that memory persists across session restarts"""
    memory_path = './test_persistence_memory'

    # Clean slate
    import shutil
    shutil.rmtree(memory_path, ignore_errors=True)

    print("🧪 Testing Memory Persistence Across Session Restarts")
    print("=" * 60)

    # SESSION 1: Create initial memories
    session1_commands = [
        "remember that my name is Laurent and I work on AI systems",
        "remember that we are testing persistence across sessions",
        "memory",  # Check current memory
        "quit"
    ]

    stdout1, stderr1 = run_session("SESSION 1 (Create memories)", session1_commands, memory_path)

    print(f"\nSESSION 1 OUTPUT (key parts):")
    print("-" * 40)
    lines = stdout1.split('\n')
    for line in lines:
        if any(keyword in line.lower() for keyword in ['remember', 'laurent', 'memory status', 'working memory']):
            print(line.strip())

    # Small delay to ensure files are written
    time.sleep(2)

    # SESSION 2: Test if memories persisted
    session2_commands = [
        "memory",  # Check if memory loaded
        "debug",   # Check debug info
        "what do you remember about me?",  # Test memory recall
        "what were we testing?",  # Test memory recall
        "quit"
    ]

    stdout2, stderr2 = run_session("SESSION 2 (Test recall)", session2_commands, memory_path)

    print(f"\nSESSION 2 OUTPUT (key parts):")
    print("-" * 40)
    lines = stdout2.split('\n')
    for line in lines:
        if any(keyword in line.lower() for keyword in ['laurent', 'testing', 'persistence', 'memory status', 'working memory', 'remember']):
            print(line.strip())

    # Analysis
    print(f"\n🔍 PERSISTENCE ANALYSIS:")
    print("=" * 60)

    # Check if key information persisted
    persistence_tests = [
        ("Memory directory created", os.path.exists(memory_path)),
        ("Laurent mentioned in session 1", "laurent" in stdout1.lower()),
        ("Testing mentioned in session 1", "testing" in stdout1.lower()),
        ("Memory loading in session 2", "memory" in stdout2.lower()),
        ("Laurent recalled in session 2", "laurent" in stdout2.lower()),
        ("Testing context recalled", "testing" in stdout2.lower() or "persistence" in stdout2.lower()),
    ]

    for test_name, passed in persistence_tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    # Check memory directory contents
    if os.path.exists(memory_path):
        print(f"\n📁 Memory Directory Contents:")
        for root, dirs, files in os.walk(memory_path):
            level = root.replace(memory_path, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files[:5]:  # Show first 5 files
                print(f"{subindent}{file}")
            if len(files) > 5:
                print(f"{subindent}... and {len(files) - 5} more files")

    # Cleanup
    shutil.rmtree(memory_path, ignore_errors=True)
    print(f"\n🧹 Cleaned up {memory_path}")

if __name__ == "__main__":
    test_session_persistence()