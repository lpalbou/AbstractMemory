"""
Working Memory Manager for AbstractMemory.

Manages active context, current tasks, and unresolved/resolved questions.
This is the "what's happening NOW" layer of memory.

Philosophy: Working memory is constantly updated and represents the AI's
current focus and active problem-solving state.

Components:
- current_context.md: Active conversation state
- current_tasks.md: What's being worked on NOW
- current_references.md: Recently accessed memories
- unresolved.md: Open questions and issues
- resolved.md: Recently resolved questions with HOW they were resolved
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WorkingMemoryManager:
    """
    Manages working memory - the active context and current state.

    Working memory is ephemeral and frequently updated. It tracks:
    - What's happening right now
    - What problems are being worked on
    - What questions remain open
    - What questions were just solved (and how)
    """

    def __init__(self, base_path: Path):
        """
        Initialize WorkingMemoryManager.

        Args:
            base_path: Root memory directory
        """
        self.base_path = Path(base_path)
        self.working_path = self.base_path / "working"
        self.working_path.mkdir(parents=True, exist_ok=True)

        # Ensure all files exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Ensure all working memory files exist."""
        from .memory_structure import _initialize_working_memory
        _initialize_working_memory(self.base_path)

    def update_context(self, context: str, user_id: Optional[str] = None) -> bool:
        """
        Update current conversation context.

        Args:
            context: Current context description
            user_id: Optional user ID for context

        Returns:
            bool: True if successful
        """
        try:
            context_file = self.working_path / "current_context.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            content = f"""# Current Context

**Last Updated**: {timestamp}
{f"**User**: {user_id}" if user_id else ""}

**What's happening RIGHT NOW in the active conversation.**

---

## Active Topic

{context}

---

## Timestamp

{timestamp}
"""

            context_file.write_text(content)
            logger.info(f"Updated current_context.md")
            return True

        except Exception as e:
            logger.error(f"Error updating context: {e}")
            return False

    def get_context(self) -> Optional[str]:
        """
        Get current context.

        Returns:
            str: Current context or None
        """
        try:
            context_file = self.working_path / "current_context.md"
            if context_file.exists():
                return context_file.read_text()
            return None
        except Exception as e:
            logger.error(f"Error reading context: {e}")
            return None

    def update_tasks(self, tasks: List[str]) -> bool:
        """
        Update current tasks list.

        Args:
            tasks: List of current tasks

        Returns:
            bool: True if successful
        """
        try:
            tasks_file = self.working_path / "current_tasks.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            task_list = "\n".join([f"- {task}" for task in tasks])

            content = f"""# Current Tasks

**Last Updated**: {timestamp}

**What's being worked on NOW.**

---

## Active Tasks

{task_list if tasks else "(No active tasks)"}

---

## Count

{len(tasks)} active task(s)
"""

            tasks_file.write_text(content)
            logger.info(f"Updated current_tasks.md with {len(tasks)} tasks")
            return True

        except Exception as e:
            logger.error(f"Error updating tasks: {e}")
            return False

    def get_tasks(self) -> List[str]:
        """
        Get current tasks.

        Returns:
            List[str]: List of current tasks
        """
        try:
            tasks_file = self.working_path / "current_tasks.md"
            if not tasks_file.exists():
                return []

            content = tasks_file.read_text()
            # Extract tasks from markdown list
            tasks = []
            for line in content.split("\n"):
                if line.strip().startswith("- "):
                    task = line.strip()[2:].strip()
                    if task and task != "(No active tasks)":
                        tasks.append(task)

            return tasks

        except Exception as e:
            logger.error(f"Error reading tasks: {e}")
            return []

    def add_unresolved(self, question: str, context: Optional[str] = None) -> bool:
        """
        Add an unresolved question.

        Args:
            question: The unresolved question
            context: Optional context about the question

        Returns:
            bool: True if successful
        """
        try:
            unresolved_file = self.working_path / "unresolved.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if unresolved_file.exists():
                existing = unresolved_file.read_text()
            else:
                existing = f"""# Unresolved Questions

**Last Updated**: {timestamp}

**Open questions and issues.**

*Connected to core/limitations.md*

---

## Open Questions

"""

            # Add new question
            question_entry = f"\n### {timestamp}\n\n**Question**: {question}\n"
            if context:
                question_entry += f"\n**Context**: {context}\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append question
            updated = existing + question_entry
            unresolved_file.write_text(updated)

            logger.info(f"Added unresolved question: {question[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error adding unresolved question: {e}")
            return False

    def add_resolved(self, question: str, solution: str, method: Optional[str] = None) -> bool:
        """
        Add a resolved question with its solution.

        Args:
            question: The resolved question
            solution: How it was resolved
            method: Optional method/approach used

        Returns:
            bool: True if successful
        """
        try:
            resolved_file = self.working_path / "resolved.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if resolved_file.exists():
                existing = resolved_file.read_text()
            else:
                existing = f"""# Resolved Questions

**Last Updated**: {timestamp}

**Recently resolved questions and HOW they were resolved.**

*Prevents re-inventing the wheel.*

---

## Recently Resolved

"""

            # Add resolution
            resolution_entry = f"\n### {timestamp}\n\n**Question**: {question}\n\n**Solution**: {solution}\n"
            if method:
                resolution_entry += f"\n**Method**: {method}\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append resolution
            updated = existing + resolution_entry
            resolved_file.write_text(updated)

            logger.info(f"Added resolved question: {question[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error adding resolved question: {e}")
            return False

    def get_unresolved(self) -> List[Dict[str, str]]:
        """
        Get all unresolved questions.

        Returns:
            List[Dict]: List of unresolved questions with metadata
        """
        try:
            unresolved_file = self.working_path / "unresolved.md"
            if not unresolved_file.exists():
                return []

            content = unresolved_file.read_text()
            questions = []

            # Parse markdown format
            current_question = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_question:
                        questions.append(current_question)
                    current_question = {"timestamp": line[4:].strip()}
                elif line.startswith("**Question**:"):
                    if current_question:
                        current_question["question"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Context**:"):
                    if current_question:
                        current_question["context"] = line.split(":", 1)[1].strip()

            if current_question:
                questions.append(current_question)

            return questions

        except Exception as e:
            logger.error(f"Error reading unresolved questions: {e}")
            return []

    def get_resolved(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get recently resolved questions.

        Args:
            limit: Maximum number of resolutions to return

        Returns:
            List[Dict]: List of resolved questions with solutions
        """
        try:
            resolved_file = self.working_path / "resolved.md"
            if not resolved_file.exists():
                return []

            content = resolved_file.read_text()
            resolutions = []

            # Parse markdown format
            current_resolution = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_resolution:
                        resolutions.append(current_resolution)
                    current_resolution = {"timestamp": line[4:].strip()}
                elif line.startswith("**Question**:"):
                    if current_resolution:
                        current_resolution["question"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Solution**:"):
                    if current_resolution:
                        current_resolution["solution"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Method**:"):
                    if current_resolution:
                        current_resolution["method"] = line.split(":", 1)[1].strip()

            if current_resolution:
                resolutions.append(current_resolution)

            # Return most recent first
            return resolutions[-limit:][::-1]

        except Exception as e:
            logger.error(f"Error reading resolved questions: {e}")
            return []

    def update_references(self, references: List[str]) -> bool:
        """
        Update recently accessed memory references.

        Args:
            references: List of memory IDs or descriptions recently accessed

        Returns:
            bool: True if successful
        """
        try:
            references_file = self.working_path / "current_references.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            ref_list = "\n".join([f"- {ref}" for ref in references])

            content = f"""# Current References

**Last Updated**: {timestamp}

**What was accessed recently.**

---

## Recently Accessed

{ref_list if references else "(No recent references)"}

---

## Count

{len(references)} reference(s) accessed
"""

            references_file.write_text(content)
            logger.info(f"Updated current_references.md with {len(references)} references")
            return True

        except Exception as e:
            logger.error(f"Error updating references: {e}")
            return False

    def clear_context(self) -> bool:
        """
        Clear current context (e.g., at end of session).

        Returns:
            bool: True if successful
        """
        try:
            return self.update_context("(Context cleared)")
        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            return False

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current working memory state.

        Returns:
            Dict: Summary with tasks, unresolved, resolved counts
        """
        return {
            "active_tasks": len(self.get_tasks()),
            "unresolved_count": len(self.get_unresolved()),
            "recent_resolved_count": len(self.get_resolved()),
            "has_context": self.get_context() is not None
        }
