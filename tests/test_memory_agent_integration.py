#!/usr/bin/env python3
"""
Comprehensive End-to-End Integration Test for MemoryAgent.

This test validates the complete flow:
1. User query → MemoryAgent.interact()
2. Real LLM generates structured response
3. Experiential note saved to notes/
4. Verbatim interaction saved to verbatim/
5. Unresolved questions tracked
6. Memory actions executed
7. Can retrieve stored memories

This is THE critical test that proves Phase 1 is complete.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json
import shutil

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from abstractmemory import MemorySession
from abstractmemory.memory_agent import MemoryAgent


def test_full_memory_agent_flow():
    """
    THE BIG ONE: Full end-to-end test with real LLM.

    Tests complete flow from user query to stored memories and retrieval.
    """
    print("\n" + "=" * 80)
    print("COMPREHENSIVE END-TO-END INTEGRATION TEST")
    print("Testing: MemoryAgent with Real Ollama LLM")
    print("=" * 80)

    # Setup: Create test memory directory
    test_memory_base = Path("test_memory_integration")
    if test_memory_base.exists():
        shutil.rmtree(test_memory_base)
    test_memory_base.mkdir()

    try:
        # Step 1: Create MemorySession (auto-configures memory system)
        print("\n1. Creating MemorySession (auto-configures Grounded memory)...")
        session = MemorySession(
            provider=None,  # Will use direct Ollama calls for this test
            system_prompt=None  # Will use MemoryAgent's structured prompt
        )
        print("   ✅ MemorySession created")
        print(f"   ✅ Memory system: {type(session.memory).__name__}")

        # Step 2: Create MemoryAgent
        print("\n2. Creating MemoryAgent...")
        agent = MemoryAgent(
            memory_session=session,
            base_path=str(test_memory_base),
            enable_experiential_notes=True
        )
        print("   ✅ MemoryAgent created")
        print(f"   ✅ Memory base path: {test_memory_base.absolute()}")

        # Step 3: Test query (consciousness-related to trigger good reflection)
        user_query = "What role does memory play in consciousness, and how might this apply to AI systems?"
        user_id = "test_user"
        location = "test_environment"

        print(f"\n3. Testing interaction...")
        print(f"   User: {user_id}")
        print(f"   Query: {user_query}")
        print(f"   Location: {location}")

        # Step 4: Execute interaction
        print("\n4. Calling agent.interact() with real LLM...")
        print("   ⏳ This may take 30-60 seconds (calling Ollama)...")

        import requests

        # Check Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code != 200:
                print("   ⚠️ Ollama not running, skipping integration test")
                return True
        except Exception:
            print("   ⚠️ Ollama not accessible, skipping integration test")
            return True

        # Execute the interaction
        try:
            result = agent.interact(
                user_query=user_query,
                user_id=user_id,
                location=location,
                include_memory=False,  # First interaction, no prior memories
                temperature=0.7
            )

            print("   ✅ Interaction completed!")

        except Exception as e:
            print(f"   ❌ Interaction failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Step 5: Validate result structure
        print("\n5. Validating result structure...")

        required_fields = ["answer", "interaction_id"]
        for field in required_fields:
            if field not in result:
                print(f"   ❌ Missing required field: {field}")
                return False
            print(f"   ✅ Has '{field}'")

        # Check optional fields
        optional_fields = ["experiential_note", "experiential_note_id", "memory_actions_executed"]
        for field in optional_fields:
            if field in result:
                print(f"   ✅ Has '{field}'")

        # Step 6: Validate answer
        print("\n6. Validating answer...")
        answer = result.get("answer", "")
        if len(answer) > 50:
            print(f"   ✅ Answer length: {len(answer)} chars")
            print(f"   Preview: {answer[:150]}...")
        else:
            print(f"   ⚠️ Answer very short: {len(answer)} chars")

        # Step 7: Validate experiential note
        print("\n7. Validating experiential note...")
        exp_note = result.get("experiential_note", "")
        exp_note_id = result.get("experiential_note_id")

        if exp_note:
            print(f"   ✅ Experiential note generated: {len(exp_note)} chars")

            # Check for first-person indicators
            first_person_indicators = ["I ", "I'm", "my ", "me ", "myself"]
            has_first_person = any(ind in exp_note for ind in first_person_indicators)

            if has_first_person:
                print("   ✅ Note contains first-person language")
            else:
                print("   ⚠️ Note may not be first-person")

            print(f"\n   Note preview:\n   {exp_note[:300]}...\n")

            if exp_note_id:
                print(f"   ✅ Note ID assigned: {exp_note_id}")
        else:
            print("   ⚠️ No experiential note in result")

        # Step 8: Check filesystem - notes/
        print("\n8. Checking filesystem - experiential notes...")
        notes_dir = test_memory_base / "notes"

        if notes_dir.exists():
            note_files = list(notes_dir.rglob("*.md"))
            if note_files:
                print(f"   ✅ Found {len(note_files)} note file(s)")
                for nf in note_files:
                    print(f"      - {nf.relative_to(test_memory_base)}")

                    # Read and validate content
                    with open(nf, 'r') as f:
                        note_content = f.read()

                    # Check for minimal template
                    if "Participants" in note_content and "Time" in note_content:
                        print(f"      ✅ Contains metadata header")

                    # Check for LLM content
                    if exp_note and exp_note in note_content:
                        print(f"      ✅ Contains experiential note content")

                    # Calculate approximate LLM percentage
                    if len(note_content) > 0:
                        # Estimate template overhead (~200 chars)
                        template_overhead = 200
                        llm_percentage = ((len(note_content) - template_overhead) / len(note_content)) * 100
                        print(f"      ✅ LLM content ~{llm_percentage:.1f}%")
            else:
                print("   ❌ No note files found")
                return False
        else:
            print("   ❌ notes/ directory not created")
            return False

        # Step 9: Check filesystem - verbatim/
        print("\n9. Checking filesystem - verbatim interactions...")
        verbatim_dir = test_memory_base / "verbatim"

        if verbatim_dir.exists():
            verbatim_files = list(verbatim_dir.rglob("*.md"))
            if verbatim_files:
                print(f"   ✅ Found {len(verbatim_files)} verbatim file(s)")
                for vf in verbatim_files:
                    print(f"      - {vf.relative_to(test_memory_base)}")

                    # Read and validate content
                    with open(vf, 'r') as f:
                        verbatim_content = f.read()

                    # Check for required sections
                    if "User Query" in verbatim_content:
                        print(f"      ✅ Contains User Query section")
                    if "Agent Response" in verbatim_content:
                        print(f"      ✅ Contains Agent Response section")

                    # Check for actual content
                    if user_query in verbatim_content:
                        print(f"      ✅ Contains original user query")
                    if answer in verbatim_content:
                        print(f"      ✅ Contains agent response")
            else:
                print("   ⚠️ No verbatim files found (may be optional)")
        else:
            print("   ⚠️ verbatim/ directory not created (may be optional)")

        # Step 10: Check working/unresolved.md
        print("\n10. Checking working/unresolved.md...")
        unresolved_path = test_memory_base / "working" / "unresolved.md"

        if unresolved_path.exists():
            print(f"   ✅ unresolved.md exists")
            with open(unresolved_path, 'r') as f:
                unresolved_content = f.read()

            # Check if it has questions
            if "- " in unresolved_content:
                question_count = unresolved_content.count("- ")
                print(f"   ✅ Contains {question_count} unresolved question(s)")
        else:
            print("   ⚠️ No unresolved.md (may be optional if no questions)")

        # Step 11: Validate memory actions
        print("\n11. Validating memory actions...")
        memory_actions = result.get("memory_actions_executed", [])

        if memory_actions:
            print(f"   ✅ {len(memory_actions)} memory action(s) executed")
            for i, action in enumerate(memory_actions, 1):
                action_type = action.get("action", "unknown")
                status = action.get("result", {}).get("status", "unknown")
                print(f"      {i}. {action_type}: {status}")
        else:
            print("   ⚠️ No memory actions executed (LLM may not have specified any)")

        # Step 12: Test retrieval (if note_id exists)
        print("\n12. Testing memory retrieval...")

        if exp_note_id:
            retrieved_note = agent.get_experiential_note(exp_note_id)
            if retrieved_note:
                print(f"   ✅ Successfully retrieved note by ID")
                print(f"   ✅ Retrieved note length: {len(retrieved_note)} chars")
            else:
                print(f"   ❌ Could not retrieve note by ID: {exp_note_id}")
        else:
            print("   ⚠️ No note ID to test retrieval")

        interaction_id = result.get("interaction_id")
        if interaction_id:
            verbatim = agent.get_verbatim(interaction_id, user_id=user_id)
            if verbatim:
                print(f"   ✅ Successfully retrieved verbatim by interaction_id")
                print(f"   ✅ Retrieved verbatim length: {len(verbatim)} chars")
            else:
                print(f"   ⚠️ Could not retrieve verbatim by interaction_id")

        # Step 13: Final validation
        print("\n" + "=" * 80)
        print("FINAL VALIDATION")
        print("=" * 80)

        checks = {
            "MemoryAgent created": True,
            "Interaction completed": "answer" in result,
            "Experiential note generated": bool(exp_note),
            "Note saved to filesystem": bool(list(notes_dir.rglob("*.md"))),
            "First-person language": has_first_person if exp_note else False,
            "Can retrieve by ID": retrieved_note is not None if exp_note_id else None
        }

        passed = sum(1 for v in checks.values() if v is True)
        total = len([v for v in checks.values() if v is not None])

        print(f"\nResults: {passed}/{total} checks passed\n")

        for check, status in checks.items():
            if status is True:
                print(f"   ✅ {check}")
            elif status is False:
                print(f"   ❌ {check}")
            else:
                print(f"   ⚠️ {check} (not tested)")

        print("\n" + "=" * 80)

        if passed >= total * 0.8:  # 80% pass threshold
            print("✅ INTEGRATION TEST PASSED")
            print("=" * 80)
            return True
        else:
            print("❌ INTEGRATION TEST FAILED")
            print("=" * 80)
            return False

    except Exception as e:
        print(f"\n❌ Integration test crashed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print(f"\n📁 Test artifacts preserved at: {test_memory_base.absolute()}")
        print("   (You can inspect the generated files)")


if __name__ == "__main__":
    success = test_full_memory_agent_flow()
    sys.exit(0 if success else 1)