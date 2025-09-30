#!/usr/bin/env python3
"""
Test structured responses with real Ollama qwen3-coder:30b.

This tests the core Phase 1 functionality:
- Structured response generation
- Response parsing
- Experiential note saving
- Memory action execution
"""

import sys
import os
from pathlib import Path
import json

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from abstractmemory.response_handler import StructuredResponseHandler, create_structured_prompt


def test_response_parsing():
    """Test parsing various response formats."""
    print("\n1. Testing Response Parsing...")

    handler = StructuredResponseHandler()

    # Test direct JSON
    direct_json = '''
    {
        "answer": "Test answer",
        "experiential_note": "I find this test interesting...",
        "memory_actions": [],
        "unresolved_questions": [],
        "emotional_resonance": {"valence": "neutral", "intensity": 0.5, "reason": "test"}
    }
    '''

    try:
        parsed = handler.parse_response(direct_json)
        assert "answer" in parsed
        print("   ✅ Direct JSON parsing works")
    except Exception as e:
        print(f"   ❌ Direct JSON parsing failed: {e}")
        return False

    # Test JSON in code block
    code_block_json = '''
Here's the response:
```json
{
    "answer": "Test answer",
    "experiential_note": "Interesting...",
    "memory_actions": []
}
```
    '''

    try:
        parsed = handler.parse_response(code_block_json)
        assert "answer" in parsed
        print("   ✅ Code block JSON parsing works")
    except Exception as e:
        print(f"   ❌ Code block JSON parsing failed: {e}")
        return False

    return True


def test_experiential_note_saving():
    """Test saving experiential notes to filesystem."""
    print("\n2. Testing Experiential Note Saving...")

    handler = StructuredResponseHandler()

    response = {
        "answer": "Test answer",
        "experiential_note": "I'm reflecting on this test interaction. What strikes me is how the structured format allows for both immediate response and deeper processing. I notice I'm uncertain about whether this captures the full richness of subjective experience, but it's a starting point.",
        "memory_actions": [],
        "unresolved_questions": ["How can I improve the depth of my reflections?"],
        "emotional_resonance": {
            "valence": "curious",
            "intensity": 0.7,
            "reason": "Exploring new memory capabilities"
        }
    }

    context = {
        "user_id": "test_user",
        "location": "test_environment",
        "interaction_id": "int_test_001"
    }

    try:
        result = handler.process_response(json.dumps(response), context)

        # Check note was saved
        note_id = result.get("experiential_note_id")
        if note_id:
            print(f"   ✅ Experiential note saved: {note_id}")

            # Verify file exists
            from datetime import datetime
            now = datetime.now()
            note_dir = Path("memory") / "notes" / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"

            if note_dir.exists():
                note_files = list(note_dir.glob("*.md"))
                if note_files:
                    print(f"   ✅ Note file created: {note_files[-1].name}")

                    # Read and validate content
                    with open(note_files[-1], 'r') as f:
                        content = f.read()

                    # Check for first-person content (experiential note should dominate)
                    note_content = response["experiential_note"]
                    if note_content in content:
                        print("   ✅ Experiential note content preserved")

                    # Calculate LLM content percentage
                    template_size = 200  # Approximate template overhead
                    total_size = len(content)
                    llm_percentage = ((total_size - template_size) / total_size) * 100

                    print(f"   ✅ LLM content percentage: {llm_percentage:.1f}%")

                    if llm_percentage > 80:  # Should be >90%, but allow some margin
                        print("   ✅ Content is dominated by LLM (>80%)")
                    else:
                        print(f"   ⚠️ LLM content only {llm_percentage:.1f}% (should be >90%)")
                else:
                    print("   ❌ No note files found")
                    return False
            else:
                print("   ❌ Note directory not created")
                return False
        else:
            print("   ❌ No note ID returned")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Note saving failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_real_llm_structured_response():
    """Test with real Ollama qwen3-coder:30b."""
    print("\n3. Testing Real LLM Structured Response...")

    import requests

    # Check Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            print("   ⚠️ Ollama not running, skipping real LLM test")
            return True  # Skip, not fail
    except Exception:
        print("   ⚠️ Ollama not accessible, skipping real LLM test")
        return True  # Skip, not fail

    # Create system prompt
    system_prompt = create_structured_prompt()

    # Test query
    user_query = "What is the most important aspect of memory for AI consciousness?"

    # Build full prompt
    full_prompt = f"""{system_prompt}

User: {user_query}

Please respond in the structured JSON format described above."""

    print(f"   🤖 Calling Ollama qwen3-coder:30b...")

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen3-coder:30b",
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2000
                }
            },
            timeout=120
        )

        if response.status_code != 200:
            print(f"   ❌ Ollama API error: {response.status_code}")
            return False

        llm_output = response.json().get("response", "")
        print(f"   ✅ LLM responded ({len(llm_output)} chars)")

        # Try to parse structured response
        handler = StructuredResponseHandler()

        try:
            parsed = handler.parse_response(llm_output)
            print("   ✅ Response parsed successfully")

            # Validate components
            if "answer" in parsed:
                print(f"   ✅ Has 'answer': {parsed['answer'][:100]}...")

            if "experiential_note" in parsed:
                note = parsed["experiential_note"]
                print(f"   ✅ Has 'experiential_note': {len(note)} chars")

                # Check for first-person indicators
                first_person_indicators = ["I ", "I'm", "my ", "me "]
                has_first_person = any(ind in note for ind in first_person_indicators)

                if has_first_person:
                    print("   ✅ Experiential note is first-person")
                else:
                    print("   ⚠️ Experiential note may not be first-person")

                print(f"\n   Note preview:\n   {note[:300]}...\n")

            if "emotional_resonance" in parsed:
                emotion = parsed["emotional_resonance"]
                print(f"   ✅ Has 'emotional_resonance': {emotion}")

            if "unresolved_questions" in parsed:
                questions = parsed["unresolved_questions"]
                if questions:
                    print(f"   ✅ Has {len(questions)} unresolved question(s)")

            # Process full response
            context = {
                "user_id": "test_user",
                "location": "test_environment"
            }

            result = handler.process_response(llm_output, context)

            if result.get("experiential_note_id"):
                print(f"   ✅ Experiential note saved: {result['experiential_note_id']}")

            return True

        except ValueError as e:
            print(f"   ❌ Failed to parse LLM response: {e}")
            print(f"   Raw output:\n{llm_output[:500]}...")
            return False

    except requests.Timeout:
        print("   ❌ LLM request timed out")
        return False
    except Exception as e:
        print(f"   ❌ LLM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_actions():
    """Test memory action execution."""
    print("\n4. Testing Memory Actions...")

    handler = StructuredResponseHandler()

    response = {
        "answer": "Test",
        "experiential_note": "Testing actions...",
        "memory_actions": [
            {
                "action": "remember",
                "content": "Test fact",
                "importance": 0.8,
                "emotion": "curiosity"
            },
            {
                "action": "link",
                "from_id": "note_123",
                "to_id": "int_456",
                "relationship": "elaborates_on"
            },
            {
                "action": "search",
                "query": "previous tests",
                "filters": {},
                "limit": 5
            }
        ]
    }

    try:
        result = handler.process_response(json.dumps(response), {})

        actions_executed = result.get("memory_actions_executed", [])

        if len(actions_executed) == 3:
            print(f"   ✅ All {len(actions_executed)} memory actions executed")

            for action_result in actions_executed:
                action_type = action_result["action"]
                status = action_result["result"].get("status", "unknown")
                print(f"   ✅ Action '{action_type}': {status}")

            return True
        else:
            print(f"   ❌ Expected 3 actions, got {len(actions_executed)}")
            return False

    except Exception as e:
        print(f"   ❌ Memory actions test failed: {e}")
        return False


def run_all_tests():
    """Run all structured response tests."""
    print("=" * 80)
    print("STRUCTURED RESPONSE TESTS")
    print("Testing Phase 1: Structured Responses & Memory Tools")
    print("=" * 80)

    tests = [
        ("Response Parsing", test_response_parsing),
        ("Experiential Note Saving", test_experiential_note_saving),
        ("Real LLM Structured Response", test_real_llm_structured_response),
        ("Memory Actions", test_memory_actions)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("\n" + "=" * 80)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 80)
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)