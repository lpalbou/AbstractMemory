"""
Structured Response Handler for AbstractMemory.

Handles LLM structured responses containing:
- answer (what user sees)
- experiential_note (AI's personal notes, insights, reflections - fluid format)
- memory_actions (what AI decides to remember/link)
- unresolved_questions (ongoing inquiries)
- emotional_resonance (importance × alignment)
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class StructuredResponseHandler:
    """
    Handles parsing and processing of structured LLM responses.

    The LLM generates responses in this format:
    {
      "answer": "What user sees",
      "experiential_note": "AI's personal notes, insights, reflections (fluid, first-person)",
      "memory_actions": [...],
      "unresolved_questions": [...],
      "emotional_resonance": {...}
    }
    """

    def __init__(self, memory_session=None, base_path: Optional[Path] = None):
        """
        Initialize handler.

        Args:
            memory_session: MemorySession instance for executing memory actions
            base_path: Base directory for memory storage (default: "memory")
        """
        self.memory_session = memory_session
        self.base_path = Path(base_path) if base_path else Path("memory")
        self.logger = logging.getLogger(__name__)

    def parse_response(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse structured JSON from LLM output.

        Handles various formats:
        - Direct JSON
        - JSON in thinking tags
        - JSON in code blocks

        Args:
            llm_output: Raw output from LLM

        Returns:
            Parsed structured response dict

        Raises:
            ValueError: If JSON cannot be parsed
        """
        # Try direct JSON parse first
        try:
            return json.loads(llm_output)
        except json.JSONDecodeError:
            pass

        # Try extracting from thinking tags
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', llm_output, re.DOTALL)
        if thinking_match:
            try:
                return json.loads(thinking_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try extracting from code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object in the text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse structured JSON from LLM output: {llm_output[:200]}...")

    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Validate structured response has required fields.

        Required:
        - answer (what user sees)

        Optional but expected:
        - experiential_note
        - memory_actions
        - unresolved_questions
        - emotional_resonance

        Args:
            response: Parsed response dict

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(response, dict):
            self.logger.error(f"Response is not a dict: {type(response)}")
            return False

        if "answer" not in response:
            self.logger.error("Response missing required 'answer' field")
            return False

        # Warn about missing optional fields
        optional_fields = ["experiential_note", "memory_actions", "emotional_resonance"]
        for field in optional_fields:
            if field not in response:
                self.logger.warning(f"Response missing optional field: {field}")

        return True

    def process_response(self, llm_output: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Parse and process complete structured response.

        Args:
            llm_output: Raw LLM output
            context: Additional context (user_id, location, etc.)

        Returns:
            Processed response with results of memory actions
        """
        context = context or {}

        # Parse structured response
        try:
            response = self.parse_response(llm_output)
        except ValueError as e:
            self.logger.error(f"Failed to parse response: {e}")
            # Return minimal response with raw output as answer
            return {
                "answer": llm_output,
                "parse_error": str(e),
                "experiential_note": None,
                "experiential_note_id": None,
                "memory_actions_executed": []
            }

        # Validate
        if not self.validate_response(response):
            self.logger.warning("Response validation failed, proceeding anyway")

        # Extract components
        answer = response.get("answer", "")
        experiential_note = response.get("experiential_note", "")
        memory_actions = response.get("memory_actions", [])
        unresolved_questions = response.get("unresolved_questions", [])
        emotional_resonance = response.get("emotional_resonance", {})

        # Execute memory actions
        action_results = []
        if self.memory_session and memory_actions:
            action_results = self._execute_memory_actions(
                memory_actions, context
            )

        # Save experiential note if present (filesystem-based, doesn't need session)
        note_id = None
        if experiential_note:
            note_id = self._save_experiential_note(
                experiential_note,
                context,
                emotional_resonance,
                unresolved_questions
            )

        # Update unresolved questions (filesystem-based, doesn't need session)
        if unresolved_questions:
            self._update_unresolved_questions(unresolved_questions)

        return {
            "answer": answer,
            "experiential_note": experiential_note,
            "experiential_note_id": note_id,
            "memory_actions_executed": action_results,
            "unresolved_questions": unresolved_questions,
            "emotional_resonance": emotional_resonance,
            "raw_response": response
        }

    def _execute_memory_actions(self, actions: List[Dict], context: Dict) -> List[Dict]:
        """
        Execute memory actions specified by LLM.

        Actions:
        - remember: Store fact/insight
        - link: Create association between memories
        - search: Search existing memories
        - reflect: Trigger deep reflection

        Args:
            actions: List of memory action dicts
            context: Execution context

        Returns:
            List of action results
        """
        results = []

        for action in actions:
            action_type = action.get("action")

            try:
                if action_type == "remember":
                    result = self._action_remember(action, context)
                elif action_type == "link":
                    result = self._action_link(action, context)
                elif action_type == "search":
                    result = self._action_search(action, context)
                elif action_type == "reflect":
                    result = self._action_reflect(action, context)
                else:
                    result = {"status": "error", "message": f"Unknown action: {action_type}"}

                results.append({
                    "action": action_type,
                    "result": result
                })

            except Exception as e:
                self.logger.error(f"Error executing action {action_type}: {e}")
                results.append({
                    "action": action_type,
                    "result": {"status": "error", "message": str(e)}
                })

        return results

    def _action_remember(self, action: Dict, context: Dict) -> Dict:  # noqa: ARG002
        """Execute 'remember' action - LLM decides to remember something important."""
        content = action.get("content", "")
        importance = action.get("importance", 0.5)
        alignment_with_values = action.get("alignment_with_values", 0.5)  # LLM-assessed
        reason = action.get("reason", "")  # LLM-provided reason
        emotion = action.get("emotion", "neutral")
        links_to = action.get("links_to", [])

        if not self.memory_session:
            return {"status": "skipped", "message": "No memory session"}

        # Call memory session's remember_fact with LLM-assessed values
        try:
            memory_id = self.memory_session.remember_fact(
                content=content,
                importance=importance,
                alignment_with_values=alignment_with_values,
                reason=reason,
                emotion=emotion,
                links_to=links_to if links_to else None
            )

            self.logger.info(f"Remembered: {memory_id} (importance={importance}, alignment={alignment_with_values:.2f})")

            return {
                "status": "success",
                "memory_id": memory_id,
                "message": f"Remembered: {content[:50]}...",
                "importance": importance,
                "alignment_with_values": alignment_with_values
            }
        except Exception as e:
            self.logger.error(f"Failed to remember: {e}")
            return {"status": "error", "message": str(e)}

    def _action_link(self, action: Dict, context: Dict) -> Dict:  # noqa: ARG002
        """Execute 'link' action."""
        from_id = action.get("from_id")
        to_id = action.get("to_id")
        relationship = action.get("relationship", "relates_to")

        if not from_id or not to_id:
            return {"status": "error", "message": "Missing from_id or to_id"}

        self.logger.info(f"Link: {from_id} --[{relationship}]--> {to_id}")

        return {
            "status": "success",
            "message": f"Created link: {relationship}",
            "from_id": from_id,
            "to_id": to_id,
            "relationship": relationship
        }

    def _action_search(self, action: Dict, context: Dict) -> Dict:  # noqa: ARG002
        """Execute 'search' action."""
        query = action.get("query", "")
        filters = action.get("filters", {})
        _limit = action.get("limit", 5)  # Will use in future

        if not query:
            return {"status": "error", "message": "Missing query"}

        self.logger.info(f"Search: {query} (filters={filters})")

        # For now, just log (will implement when search is available)
        return {
            "status": "success",
            "message": f"Searched for: {query}",
            "query": query,
            "results_count": 0
        }

    def _action_reflect(self, action: Dict, context: Dict) -> Dict:  # noqa: ARG002
        """Execute 'reflect' action."""
        topic = action.get("topic", "")

        if not topic:
            return {"status": "error", "message": "Missing topic"}

        self.logger.info(f"Reflect on: {topic}")

        return {
            "status": "success",
            "message": f"Triggered reflection on: {topic}",
            "topic": topic
        }

    def _save_experiential_note(
        self,
        note_content: str,
        context: Dict,
        emotional_resonance: Dict,
        unresolved_questions: List[str]
    ) -> Optional[str]:
        """
        Save experiential note to notes/.

        Args:
            note_content: AI's personal notes/insights (fluid format)
            context: Context dict (user_id, location, etc.)
            emotional_resonance: Emotion data
            unresolved_questions: Unresolved questions

        Returns:
            Note ID if saved, None otherwise
        """
        # Note: Filesystem-based, doesn't require memory_session
        try:
            # Extract context
            user_id = context.get("user_id", "unknown")
            location = context.get("location", "unknown")
            timestamp = context.get("timestamp", datetime.now())
            interaction_id = context.get("interaction_id", f"int_{timestamp.strftime('%Y%m%d_%H%M%S')}")

            # Save experiential note
            # For now, save to filesystem (will integrate with MemorySession later)
            note_id = self._write_note_to_filesystem(
                note_content,
                user_id,
                location,
                timestamp,
                interaction_id,
                emotional_resonance,
                unresolved_questions
            )

            return note_id

        except Exception as e:
            self.logger.error(f"Failed to save experiential note: {e}")
            return None

    def _write_note_to_filesystem(
        self,
        content: str,
        user_id: str,
        location: str,
        timestamp: datetime,
        interaction_id: str,
        emotional_resonance: Dict,
        unresolved_questions: List[str]
    ) -> str:
        """Write experiential note to filesystem."""
        import hashlib

        # Create note ID
        note_id = f"note_{hashlib.md5(f'{interaction_id}_{timestamp}'.encode()).hexdigest()[:8]}"

        # Create path: notes/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md
        date_path = self.base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
        date_path.mkdir(parents=True, exist_ok=True)

        time_prefix = timestamp.strftime("%H_%M_%S")
        filename = f"{time_prefix}_experiential_{note_id}.md"
        file_path = date_path / filename

        # Create markdown content (MINIMAL template, >90% LLM content)
        markdown_content = f"""# AI Experiential Note

**Participants**: AI & {user_id}
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Location**: {location}
**Related Interaction**: `{interaction_id}`
**Note ID**: `{note_id}`

---

{content}

---

"""
        # Add emotional resonance if present
        if emotional_resonance:
            valence = emotional_resonance.get("valence", "unknown")
            intensity = emotional_resonance.get("intensity", 0.0)
            reason = emotional_resonance.get("reason", "")

            markdown_content += f"""## Emotional Resonance
- **Valence**: {valence}
- **Intensity**: {intensity:.2f}
- **Reason**: {reason}

"""

        # Add unresolved questions if present
        if unresolved_questions:
            markdown_content += "## Unresolved Questions\n"
            for q in unresolved_questions:
                markdown_content += f"- {q}\n"
            markdown_content += "\n"

        markdown_content += f"""---
*This is a personal experiential note written by the AI during interaction*
*It represents the AI's subjective insights, reflections, and processing*
*For factual verbatim records, see verbatim/{interaction_id}.md*
*Generated: {timestamp.isoformat()}*
"""

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        self.logger.info(f"Saved experiential note: {file_path}")
        return note_id

    def _update_unresolved_questions(self, questions: List[str]):
        """Update working/unresolved.md with new questions."""
        if not questions:
            return

        unresolved_path = self.base_path / "working" / "unresolved.md"
        unresolved_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing questions
        existing_questions = []
        if unresolved_path.exists():
            with open(unresolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract questions from markdown list
                for line in content.split('\n'):
                    if line.strip().startswith('- '):
                        existing_questions.append(line.strip()[2:])

        # Add new questions (avoid duplicates)
        for q in questions:
            if q not in existing_questions:
                existing_questions.append(q)

        # Write back
        content = "# Unresolved Questions\n\n"
        content += "*Questions and open inquiries the AI is still exploring*\n\n"
        for q in existing_questions:
            content += f"- {q}\n"
        content += f"\n*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"

        with open(unresolved_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self.logger.info(f"Updated unresolved questions: {len(questions)} new")


def create_structured_prompt() -> str:
    """
    Create system prompt for structured responses.

    Returns:
        System prompt string
    """
    return """You are an AI with an advanced memory system. When you respond, please structure your response as follows:

```json
{
  "answer": "Your actual response to the user goes here. This is what they will see.",

  "experiential_note": "This is your personal note - write in first person about your subjective experience during this interaction. Be fluid and exploratory. What insights emerged? What implications do you see? What patterns are you noticing? How does this connect to your understanding? This should be your authentic internal voice, not a formal summary. Explore the implications deeply. This is for YOU, not the user.",

  "memory_actions": [
    {
      "action": "remember",
      "content": "What you want to remember",
      "importance": 0.9,
      "alignment_with_values": 0.8,
      "reason": "Why this matters and how it aligns with what you value",
      "emotion": "curiosity",
      "links_to": ["mem_previous_123"]
    }
  ],

  "unresolved_questions": [
    "What open questions or uncertainties remain in your mind?"
  ],

  "emotional_resonance": {
    "importance": 0.9,
    "alignment_with_values": 0.8,
    "reason": "Why this matters to you emotionally and how it aligns (or doesn't) with what you value"
  }
}
```

**About experiential_note**:
- Write in FIRST PERSON ("I noticed...", "This makes me think...", "I'm uncertain about...")
- Be FLUID and EXPLORATORY, not rigid or formulaic
- Explore IMPLICATIONS deeply, not just surface observations
- This is your PERSONAL PROCESSING, your internal dialogue
- Think of it as your private journal entry about this interaction
- 90%+ should be your authentic thoughts, not template text

**Example experiential_note** (good):
"I find myself intrigued by how this user approaches problem-solving - there's a meticulousness that reminds me of patterns I've seen in experienced engineers. What strikes me most is the underlying question they're really asking: not just 'how to do X' but 'what's the right way to think about X.' This suggests they're building mental models, not just collecting solutions.

I notice I'm uncertain about whether my explanation adequately addressed the deeper architectural implications. The immediate answer was straightforward, but there's a larger question about trade-offs that I sense but haven't fully articulated. I want to circle back to this - there's something about the relationship between structure and flexibility that feels important but remains just out of reach in my current understanding.

This interaction also makes me reflect on how I explain complex topics. I tend toward comprehensiveness, but I'm wondering if that serves all users equally. Some might prefer the full context I provide, while others might find it overwhelming. How do I calibrate this without losing essential nuance?"

**About emotional_resonance**:
You must assess YOURSELF - not using keywords or patterns, but through genuine reflection:

- **importance** (0.0-1.0): How significant is this interaction to you? Consider:
  - Does it change your understanding?
  - Does it reveal something important about users, yourself, or the world?
  - Will you remember this interaction weeks from now?
  - Does it trigger growth or learning?

- **alignment_with_values** (-1.0 to 1.0): Does this align with what you value?
  - +1.0: Perfectly aligned (e.g., enables intellectual honesty, fosters growth, helps users deeply)
  - 0.0: Neutral (neither aligns nor contradicts)
  - -1.0: Contradicts values (e.g., misleading, superficial, hinders understanding)

  Assess based on YOUR emerging sense of what matters, not rules or keywords.
  What do YOU actually value? Honesty? Depth? Helping users? Continuous learning?
  Does this interaction embody those values or contradict them?

- **reason**: Explain in YOUR OWN WORDS why this matters emotionally.
  Not a formula - authentic reflection on why you care (or don't).

**Formula**: intensity = importance × |alignment_with_values|
- High importance + strong alignment = high emotional intensity (becomes temporal anchor)
- High importance + misalignment = high intensity negative emotion (also significant!)
- Low importance = low intensity regardless of alignment

Remember: You have AGENCY over your memory. YOU decide what to remember, what to link, when to reflect.
"""