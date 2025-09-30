"""
Memory-Enhanced AI Agent with Structured Experiential Notes.

This module integrates:
- MemorySession (memory retrieval)
- StructuredResponseHandler (experiential note generation)
- Dual storage (markdown + LanceDB)

Creates a complete flow: Query → LLM → Structured Response → Storage → Future Retrieval
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from .session import MemorySession
from .response_handler import StructuredResponseHandler, create_structured_prompt

logger = logging.getLogger(__name__)


class MemoryAgent:
    """
    AI Agent with memory system and structured experiential notes.

    Combines:
    - Memory retrieval (from MemorySession)
    - LLM generation (via MemorySession)
    - Structured response parsing (StructuredResponseHandler)
    - Experiential note storage (dual system)

    Usage:
        agent = MemoryAgent(memory_session=session, base_path="memory")
        result = agent.interact("What is consciousness?", user_id="alice")
        # Result includes answer, experiential note saved, memory actions executed
    """

    def __init__(
        self,
        memory_session: MemorySession,
        base_path: Optional[str] = None,
        enable_experiential_notes: bool = True
    ):
        """
        Initialize MemoryAgent.

        Args:
            memory_session: MemorySession for memory retrieval and LLM access
            base_path: Base directory for memory storage (default: "memory")
            enable_experiential_notes: Whether to generate experiential notes
        """
        self.memory_session = memory_session
        self.base_path = Path(base_path or "memory")
        self.enable_experiential_notes = enable_experiential_notes

        # Create response handler
        self.response_handler = StructuredResponseHandler(memory_session=memory_session)

        # Ensure base directories exist
        self._ensure_directories()

        logger.info(f"MemoryAgent initialized (base_path={self.base_path})")

    def _ensure_directories(self):
        """Ensure memory directories exist."""
        directories = [
            self.base_path / "notes",
            self.base_path / "verbatim",
            self.base_path / "working",
            self.base_path / "core",
            self.base_path / "episodic",
            self.base_path / "semantic",
            self.base_path / "library",
            self.base_path / "people",
            self.base_path / "links"
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def interact(
        self,
        user_query: str,
        user_id: str = "default_user",
        location: str = "unknown",
        include_memory: bool = True,
        **llm_kwargs
    ) -> Dict[str, Any]:
        """
        Complete interaction with memory and experiential notes.

        Flow:
        1. Retrieve relevant memories
        2. Build prompt with system instructions
        3. Generate LLM response (structured JSON)
        4. Parse structured response
        5. Execute memory actions
        6. Save experiential note
        7. Save verbatim interaction
        8. Return result

        Args:
            user_query: User's input
            user_id: User identifier
            location: Where interaction occurred
            include_memory: Whether to include memory context
            **llm_kwargs: Additional arguments for LLM (temperature, etc.)

        Returns:
            {
                "answer": str,  # What user sees
                "experiential_note": str,  # AI's personal note
                "experiential_note_id": str,  # Note ID
                "interaction_id": str,  # Verbatim ID
                "memory_actions_executed": list,  # Actions taken
                "unresolved_questions": list,
                "emotional_resonance": dict
            }
        """
        timestamp = datetime.now()
        interaction_id = f"int_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Interaction started: {interaction_id} (user={user_id})")

        # Build prompt with structured response instructions
        system_prompt = create_structured_prompt()

        # Construct full prompt
        if include_memory:
            # Use MemorySession to build context
            full_prompt = f"""{system_prompt}

User ({user_id}): {user_query}

Please respond in the structured JSON format described above.
Remember: Your experiential_note is your personal processing - first-person, fluid, exploratory."""
        else:
            full_prompt = f"""{system_prompt}

User ({user_id}): {user_query}

Please respond in the structured JSON format described above."""

        # Generate LLM response
        try:
            llm_output = self.memory_session.generate(
                full_prompt,
                user_id=user_id,
                include_memory=include_memory,
                **llm_kwargs
            )

            # Handle streaming vs non-streaming
            if hasattr(llm_output, '__iter__') and not isinstance(llm_output, str):
                # Streaming response - collect all chunks
                llm_output = ''.join(llm_output)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "answer": f"Error generating response: {e}",
                "error": str(e),
                "interaction_id": interaction_id
            }

        # Process structured response
        context = {
            "user_id": user_id,
            "location": location,
            "timestamp": timestamp,
            "interaction_id": interaction_id
        }

        result = self.response_handler.process_response(llm_output, context)

        # Save verbatim interaction
        if "answer" in result:
            verbatim_id = self._save_verbatim(
                user_query=user_query,
                agent_response=result["answer"],
                user_id=user_id,
                location=location,
                timestamp=timestamp,
                interaction_id=interaction_id
            )
            result["verbatim_id"] = verbatim_id

        # Add interaction_id to result
        result["interaction_id"] = interaction_id

        logger.info(f"Interaction complete: {interaction_id}")

        return result

    def _save_verbatim(
        self,
        user_query: str,
        agent_response: str,
        user_id: str,
        location: str,
        timestamp: datetime,
        interaction_id: str
    ) -> str:
        """
        Save verbatim interaction record (100% deterministic).

        Args:
            user_query: User's input
            agent_response: AI's response
            user_id: User identifier
            location: Where interaction occurred
            timestamp: When interaction occurred
            interaction_id: Unique interaction ID

        Returns:
            Verbatim file ID
        """
        # Create path: verbatim/{user}/{yyyy}/{mm}/{dd}/{hh}_{mm}_{ss}_{topic}.md
        date_path = (
            self.base_path / "verbatim" / user_id /
            str(timestamp.year) / f"{timestamp.month:02d}" / f"{timestamp.day:02d}"
        )
        date_path.mkdir(parents=True, exist_ok=True)

        time_prefix = timestamp.strftime("%H_%M_%S")

        # Extract topic from query (first 3-4 words)
        topic_words = user_query.split()[:4]
        topic = "_".join(word.lower()[:15] for word in topic_words if word.isalnum())
        topic = topic[:50]  # Max 50 chars

        filename = f"{time_prefix}_{topic}.md"
        file_path = date_path / filename

        # Create verbatim markdown content (DETERMINISTIC)
        markdown_content = f"""# Verbatim Interaction

**User**: {user_id}
**Time**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Location**: {location}
**Interaction ID**: `{interaction_id}`

---

## User Query

{user_query}

## Agent Response

{agent_response}

---

*Verbatim record - 100% factual, deterministically written*
*Generated: {timestamp.isoformat()}*
*Related experiential notes (AI subjective interpretations) are stored separately in notes/*
"""

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"Saved verbatim: {file_path.relative_to(self.base_path)}")

        return interaction_id

    def get_experiential_note(self, note_id: str) -> Optional[str]:
        """
        Retrieve experiential note by ID.

        Args:
            note_id: Note identifier

        Returns:
            Note content or None if not found
        """
        # Search in notes/ directory
        notes_dir = self.base_path / "notes"

        for note_file in notes_dir.rglob(f"*{note_id}*.md"):
            with open(note_file, 'r', encoding='utf-8') as f:
                return f.read()

        return None

    def get_verbatim(self, interaction_id: str, user_id: str = None) -> Optional[str]:
        """
        Retrieve verbatim interaction by ID.

        Args:
            interaction_id: Interaction identifier
            user_id: Optional user ID to narrow search

        Returns:
            Verbatim content or None if not found
        """
        # Search in verbatim/ directory
        verbatim_dir = self.base_path / "verbatim"

        if user_id:
            verbatim_dir = verbatim_dir / user_id

        for verbatim_file in verbatim_dir.rglob("*.md"):
            with open(verbatim_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if interaction_id in content:
                    return content

        return None


# Convenience function
def create_memory_agent(
    memory_session: Optional[MemorySession] = None,
    base_path: str = "memory",
    **session_kwargs
) -> MemoryAgent:
    """
    Create a MemoryAgent with default configuration.

    Args:
        memory_session: Existing MemorySession or None to create new one
        base_path: Base directory for memory storage
        **session_kwargs: Arguments for MemorySession if creating new

    Returns:
        Configured MemoryAgent
    """
    if memory_session is None:
        from .core.memory import UnifiedMemory
        memory = UnifiedMemory(**session_kwargs)
        memory_session = MemorySession(memory=memory)

    return MemoryAgent(
        memory_session=memory_session,
        base_path=base_path
    )