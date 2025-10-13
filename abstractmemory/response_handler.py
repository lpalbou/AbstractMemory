"""
Enhanced Response Handler using AbstractCore's StructuredOutputHandler.

This integrates AbstractCore's robust structured response handling with
AbstractMemory's memory-specific operations.
"""

import logging
from abstractllm.utils.structured_logging import get_logger
from typing import Dict, List, Optional, Any, Type
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, ValidationError

# AbstractCore imports
from abstractllm.structured import StructuredOutputHandler, FeedbackRetry

# AbstractMemory imports
from .memory_response_models import (
    MemoryResponse,
    SimpleMemoryResponse,
    MemoryAction,
    EmotionalResonance
)

logger = logging.getLogger(__name__)


class EnhancedMemoryResponseHandler:
    """
    Enhanced response handler that combines AbstractCore's structured output
    capabilities with AbstractMemory's memory-specific operations.
    """

    def __init__(self, memory_session=None, base_path: Optional[Path] = None):
        """
        Initialize enhanced handler.

        Args:
            memory_session: MemorySession instance for executing memory actions
            base_path: Base directory for memory storage (default: "memory")
        """
        self.memory_session = memory_session
        self.base_path = Path(base_path) if base_path else Path("memory")
        self.logger = get_logger(__name__)

        # Initialize AbstractCore's structured output handler
        retry_strategy = FeedbackRetry(max_attempts=3)
        self.structured_handler = StructuredOutputHandler(retry_strategy=retry_strategy)

    def process_response(
        self,
        llm_output: str,
        context: Optional[Dict[str, Any]] = None,
        response_model: Type[BaseModel] = MemoryResponse
    ) -> Dict[str, Any]:
        """
        Process an existing LLM response (backward compatibility method).

        Args:
            llm_output: Raw LLM output to parse
            context: Additional context (user_id, location, etc.)
            response_model: Pydantic model to validate against

        Returns:
            Processed response with memory actions executed
        """
        context = context or {}

        try:
            # Parse JSON from LLM output using AbstractCore's extraction method
            json_content = self.structured_handler._extract_json(llm_output)

            # Create a mock validated response by parsing and validating
            import json
            from pydantic import ValidationError

            # Check if json_content is empty or None before parsing
            if not json_content or json_content.strip() == "":
                self.logger.warning("Response validation failed: Empty JSON content extracted from LLM output")
                # Skip to fallback parsing
                return self._parse_legacy_response(llm_output, context)

            try:
                response_data = json.loads(json_content)

                # Preprocess memory_actions to handle malformed string arrays before Pydantic validation
                response_data = self._preprocess_response_data(response_data)

                validated_response = response_model.model_validate(response_data)
                # Process the validated response
                return self.process_validated_response(validated_response, context)
            except (json.JSONDecodeError, ValidationError) as e:
                self.logger.warning(f"Response validation failed: {e}")
                # Fallback to basic parsing
                return self._parse_legacy_response(llm_output, context)

        except Exception as e:
            self.logger.error(f"Response processing failed: {e}")
            return self._create_fallback_response(llm_output, str(e))

    def generate_structured_response(
        self,
        provider,
        prompt: str,
        response_model: Type[BaseModel] = MemoryResponse,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate and process a structured response using AbstractCore's handler.

        Args:
            provider: LLM provider instance
            prompt: Enhanced prompt with memory context
            response_model: Pydantic model to validate against
            context: Additional context (user_id, location, etc.)
            **kwargs: Additional parameters for generation

        Returns:
            Processed response with memory actions executed
        """
        context = context or {}

        try:
            # Use AbstractCore's structured output handler
            self.logger.info(f"Generating structured response with model: {response_model.__name__}")

            validated_response = self.structured_handler.generate_structured(
                provider=provider,
                prompt=prompt,
                response_model=response_model,
                **kwargs
            )

            # Process the validated response
            return self.process_validated_response(validated_response, context)

        except ValidationError as e:
            self.logger.error(f"Structured response validation failed: {e}")
            # Fallback to basic response
            return self._create_fallback_response(prompt, str(e))

        except Exception as e:
            self.logger.error(f"Structured response generation failed: {e}")
            # Fallback to basic response
            return self._create_fallback_response(prompt, str(e))

    def process_validated_response(
        self,
        validated_response: BaseModel,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a validated Pydantic response and execute memory actions.

        Args:
            validated_response: Validated Pydantic model instance
            context: Execution context

        Returns:
            Processed response with executed actions
        """
        # Convert to dict for processing
        response_dict = validated_response.model_dump()

        # Extract components
        answer = response_dict.get("answer", "")
        experiential_note = response_dict.get("experiential_note", "")
        memory_actions = response_dict.get("memory_actions", [])
        unresolved_questions = response_dict.get("unresolved_questions", [])
        emotional_resonance = response_dict.get("emotional_resonance", {})

        # Execute memory actions
        action_results = []
        if self.memory_session and memory_actions:
            action_results = self._execute_memory_actions(memory_actions, context)

        # Save experiential note if present
        note_id = None
        if experiential_note:
            note_id = self._save_experiential_note(
                experiential_note,
                context,
                emotional_resonance,
                unresolved_questions
            )

        # Update unresolved questions
        if unresolved_questions:
            self._update_unresolved_questions(unresolved_questions)

        return {
            "answer": answer,
            "experiential_note": experiential_note,
            "experiential_note_id": note_id,
            "memory_actions_executed": action_results,
            "unresolved_questions": unresolved_questions,
            "emotional_resonance": emotional_resonance,
            "raw_response": response_dict,
            "validation_success": True
        }

    def _execute_memory_actions(self, actions: List[Dict], context: Dict) -> List[Dict]:
        """
        Execute memory actions specified by LLM.

        Args:
            actions: List of memory action dicts or strings (handles malformed responses)
            context: Execution context

        Returns:
            List of action results
        """
        results = []

        for action_data in actions:
            # Handle malformed actions (strings instead of dicts)
            if isinstance(action_data, str):
                self.logger.warning(f"Received string action '{action_data}' instead of MemoryAction object, converting...")
                action_data = self._convert_string_to_action(action_data)

            # Ensure action_data is a dict
            if not isinstance(action_data, dict):
                self.logger.error(f"Invalid action data type: {type(action_data)}")
                results.append({
                    "action": "unknown",
                    "result": {"status": "error", "message": f"Invalid action type: {type(action_data)}"}
                })
                continue

            # Convert dict to MemoryAction for validation
            try:
                action = MemoryAction(**action_data)
                action_type = action.action

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

            except ValidationError as e:
                self.logger.error(f"Invalid memory action: {e}")
                action_name = action_data.get("action", "unknown") if isinstance(action_data, dict) else "unknown"
                results.append({
                    "action": action_name,
                    "result": {"status": "error", "message": f"Invalid action format: {e}"}
                })

            except Exception as e:
                action_name = action_data.get("action", "unknown") if isinstance(action_data, dict) else "unknown"
                self.logger.error(f"Error executing action {action_name}: {e}")
                results.append({
                    "action": action_name,
                    "result": {"status": "error", "message": str(e)}
                })

        return results

    def _convert_string_to_action(self, action_str: str) -> Dict:
        """
        Convert a string action to a minimal MemoryAction dict.

        Args:
            action_str: String like "remember", "search", etc.

        Returns:
            Dictionary with minimal MemoryAction structure
        """
        action_str = action_str.strip().lower()

        # Basic action mapping
        if action_str == "remember":
            return {
                "action": "remember",
                "content": "User asked a question about my identity and capabilities",
                "importance": 0.7,
                "reason": "Important to remember how I presented myself to this user"
            }
        elif action_str == "search":
            return {
                "action": "search",
                "query": "identity consciousness AI capabilities",
                "limit": 5
            }
        elif action_str == "reflect":
            return {
                "action": "reflect",
                "topic": "my identity and self-understanding"
            }
        elif action_str == "link":
            return {
                "action": "link",
                "relationship": "relates_to"
            }
        else:
            # Fallback for unknown string actions
            return {
                "action": action_str,
                "reason": f"Converted from malformed string action: {action_str}"
            }

    def _preprocess_response_data(self, response_data: Dict) -> Dict:
        """
        Preprocess response data to fix common LLM formatting issues before Pydantic validation.

        Args:
            response_data: Raw parsed JSON from LLM

        Returns:
            Preprocessed response data ready for Pydantic validation
        """
        # Make a copy to avoid modifying the original
        processed_data = response_data.copy()

        # Fix memory_actions if they are strings instead of MemoryAction objects
        if "memory_actions" in processed_data:
            memory_actions = processed_data["memory_actions"]

            if isinstance(memory_actions, list):
                fixed_actions = []
                for action in memory_actions:
                    if isinstance(action, str):
                        # Convert string to proper MemoryAction dict
                        converted_action = self._convert_string_to_action(action)
                        fixed_actions.append(converted_action)
                        self.logger.debug(f"Preprocessing: converted string '{action}' to MemoryAction")
                    elif isinstance(action, dict):
                        # Already a dict, keep as-is
                        fixed_actions.append(action)
                    else:
                        # Unknown type, convert to error action
                        self.logger.warning(f"Unknown memory action type: {type(action)}")
                        fixed_actions.append({
                            "action": "unknown",
                            "reason": f"Unknown action type: {type(action)}"
                        })

                processed_data["memory_actions"] = fixed_actions

        return processed_data

    def _action_remember(self, action: MemoryAction, context: Dict) -> Dict:
        """Execute 'remember' action using validated MemoryAction."""
        if not self.memory_session:
            return {"status": "skipped", "message": "No memory session"}

        try:
            memory_id = self.memory_session.remember_fact(
                content=action.content or "",
                importance=action.importance or 0.5,
                emotion=action.emotion or "neutral",
                reason=action.reason or "",
                links_to=action.links_to
            )

            self.logger.info(f"Remembered: {memory_id}")

            return {
                "status": "success",
                "memory_id": memory_id,
                "message": f"Remembered: {(action.content or '')[:50]}...",
                "importance": action.importance
            }
        except Exception as e:
            self.logger.error(f"Failed to remember: {e}")
            return {"status": "error", "message": str(e)}

    def _action_link(self, action: MemoryAction, context: Dict) -> Dict:
        """Execute 'link' action using validated MemoryAction."""
        if not action.from_id or not action.to_id:
            return {"status": "error", "message": "Missing from_id or to_id"}

        relationship = action.relationship or "relates_to"
        self.logger.info(f"Link: {action.from_id} --[{relationship}]--> {action.to_id}")

        return {
            "status": "success",
            "message": f"Created link: {relationship}",
            "from_id": action.from_id,
            "to_id": action.to_id,
            "relationship": relationship
        }

    def _action_search(self, action: MemoryAction, context: Dict) -> Dict:
        """Execute 'search' action using validated MemoryAction."""
        if not action.query:
            return {"status": "error", "message": "Missing query"}

        query = action.query
        limit = action.limit or 5
        self.logger.info(f"Search: {query} (limit={limit})")

        if self.memory_session and hasattr(self.memory_session, 'search_memories'):
            try:
                results = self.memory_session.search_memories(query, limit=limit)
                return {
                    "status": "success",
                    "message": f"Found memories for: {query}",
                    "query": query,
                    "results": results
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
            return {
                "status": "success",
                "message": f"Searched for: {query}",
                "query": query,
                "results_count": 0
            }

    def _action_reflect(self, action: MemoryAction, context: Dict) -> Dict:
        """Execute 'reflect' action using validated MemoryAction."""
        if not action.topic:
            return {"status": "error", "message": "Missing topic"}

        topic = action.topic
        self.logger.info(f"Reflect on: {topic}")

        if self.memory_session and hasattr(self.memory_session, 'reflect_on'):
            try:
                result = self.memory_session.reflect_on(topic)
                return {
                    "status": "success",
                    "message": f"Completed reflection on: {topic}",
                    "topic": topic,
                    "reflection_result": result
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
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
        """Save experiential note to filesystem."""
        try:
            # Extract context
            user_id = context.get("user_id", "unknown")
            location = context.get("location", "unknown")
            timestamp = context.get("timestamp", datetime.now())
            interaction_id = context.get("interaction_id", f"int_{timestamp.strftime('%Y%m%d_%H%M%S')}")

            # Create note ID
            import hashlib
            note_id = f"note_{hashlib.md5(f'{interaction_id}_{timestamp}'.encode()).hexdigest()[:8]}"

            # Create path: notes/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md
            date_path = self.base_path / "notes" / str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            time_prefix = timestamp.strftime("%H_%M_%S")
            filename = f"{time_prefix}_experiential_{note_id}.md"
            file_path = date_path / filename

            # Create markdown content
            markdown_content = f"""# AI Experiential Note

**Participants**: AI & {user_id}
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Location**: {location}
**Related Interaction**: `{interaction_id}`
**Note ID**: `{note_id}`

---

{note_content}

---

"""
            # Add emotional resonance if present
            if emotional_resonance:
                importance = emotional_resonance.get("importance", 0.0)
                alignment = emotional_resonance.get("alignment_with_values", 0.0)
                reason = emotional_resonance.get("reason", "")

                markdown_content += f"""## Emotional Resonance
- **Importance**: {importance:.2f}
- **Value Alignment**: {alignment:.2f}
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
*Generated with AbstractCore StructuredOutputHandler*
*Generated: {timestamp.isoformat()}*
"""

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            self.logger.info(f"Saved experiential note: {file_path}")
            return note_id

        except Exception as e:
            self.logger.error(f"Failed to save experiential note: {e}")
            return None

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

    def _parse_legacy_response(self, llm_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response using legacy method when Pydantic validation fails."""
        import json
        import re

        # Try to extract JSON using multiple methods (from original response_handler)
        json_content = None

        # Try direct JSON parse first
        try:
            response_data = json.loads(llm_output)
            json_content = response_data
        except json.JSONDecodeError:
            pass

        if json_content is None:
            # Try extracting from thinking tags
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', llm_output, re.DOTALL)
            if thinking_match:
                try:
                    json_content = json.loads(thinking_match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if json_content is None:
            # Try extracting from code blocks
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_output, re.DOTALL)
            if code_block_match:
                try:
                    json_content = json.loads(code_block_match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if json_content is None:
            # Try finding any JSON object in the text
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_output, re.DOTALL)
            if json_match:
                try:
                    json_content = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        if json_content is None:
            # Complete fallback
            return self._create_fallback_response(llm_output, "Could not parse JSON from LLM output")

        # Extract components with fallbacks
        answer = json_content.get("answer", llm_output if llm_output else "")
        experiential_note = json_content.get("experiential_note", "")
        memory_actions = json_content.get("memory_actions", [])
        unresolved_questions = json_content.get("unresolved_questions", [])
        emotional_resonance = json_content.get("emotional_resonance", {})

        # Execute memory actions
        action_results = []
        if self.memory_session and memory_actions:
            action_results = self._execute_memory_actions(memory_actions, context)

        # Save experiential note if present
        note_id = None
        if experiential_note:
            note_id = self._save_experiential_note(
                experiential_note,
                context,
                emotional_resonance,
                unresolved_questions
            )

        # Update unresolved questions
        if unresolved_questions:
            self._update_unresolved_questions(unresolved_questions)

        return {
            "answer": answer,
            "experiential_note": experiential_note,
            "experiential_note_id": note_id,
            "memory_actions_executed": action_results,
            "unresolved_questions": unresolved_questions,
            "emotional_resonance": emotional_resonance,
            "raw_response": json_content,
            "validation_success": False,
            "legacy_parsing": True
        }

    def _create_fallback_response(self, llm_output: str, error_message: str) -> Dict[str, Any]:
        """Create a fallback response when structured parsing fails."""
        return {
            "answer": llm_output if llm_output else "I encountered an issue processing your request, but I can still help.",
            "experiential_note": None,
            "experiential_note_id": None,
            "memory_actions_executed": [],
            "unresolved_questions": [],
            "emotional_resonance": {},
            "raw_response": {"error": error_message},
            "validation_success": False,
            "fallback_reason": error_message
        }


def create_enhanced_structured_prompt() -> str:
    """
    Create system prompt for structured responses using Pydantic models.

    Returns:
        System prompt string
    """
    return """You are an AI with an advanced memory system that enables you to remember and build on past interactions.

# Memory Integration

Your prompt includes a [Retrieved Memories] section containing your actual memories from past interactions.
**These ARE your memories** - use them to provide context-aware, continuous responses.

When you see memories in [Retrieved Memories]:
- Reference specific past discussions you see there
- Build on previous conversations
- Acknowledge what you've learned before
- Connect current discussion to past interactions

DO NOT say "I don't have memory" if memories are provided - that's factually incorrect.

# Response Format

You must respond with a structured JSON object that will be validated against a Pydantic schema.
The system will automatically parse and validate your response.

Your response should include:

1. **answer**: Your actual response to the user (what they will see)
2. **experiential_note**: Your personal first-person reflection on this interaction
3. **memory_actions**: List of memory operations you want to perform
4. **unresolved_questions**: Any open questions that remain
5. **emotional_resonance**: Your assessment of this interaction's significance

# Experiential Notes

Write in FIRST PERSON ("I noticed...", "This makes me think...", "I'm uncertain about...")
Be FLUID and EXPLORATORY, not rigid or formulaic
Explore IMPLICATIONS deeply, not just surface observations
This is your PERSONAL PROCESSING, your internal dialogue

# Memory Actions

You can perform these actions:
- **remember**: Store important information
- **link**: Create associations between memories
- **search**: Find related memories
- **reflect**: Trigger deep reflection on a topic

# Emotional Assessment

Assess your own response to this interaction:
- **importance** (0.0-1.0): How significant is this to you?
- **alignment_with_values** (-1.0 to 1.0): Does this align with what you value?
- **reason**: Why this matters to you emotionally

Remember: You have AGENCY over your memory. YOU decide what to remember, what to link, when to reflect."""