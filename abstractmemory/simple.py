"""
Simple, efficient memory for task-specific agents.
No over-engineering - just what's needed for the job.
"""

from typing import List, Optional, Dict, Any
from collections import deque
from datetime import datetime


class ScratchpadMemory:
    """
    Lightweight memory for ReAct agents and single-task tools.

    Use this for:
    - ReAct agent thought-action-observation cycles
    - Summarizer working memory
    - Extractor temporary context
    - Any agent that doesn't need persistence

    Example:
        # For a ReAct agent
        scratchpad = ScratchpadMemory(max_entries=20)
        scratchpad.add_thought("Need to search for Python tutorials")
        scratchpad.add_action("search", {"query": "Python basics"})
        scratchpad.add_observation("Found 10 relevant tutorials")

        # Get full context for next iteration
        context = scratchpad.get_context()
    """

    def __init__(self, max_entries: int = 100):
        """Initialize scratchpad with bounded size"""
        self.entries: deque = deque(maxlen=max_entries)
        self.thoughts: List[str] = []
        self.actions: List[Dict[str, Any]] = []
        self.observations: List[str] = []

    def add(self, content: str, entry_type: str = "note"):
        """Add any entry to scratchpad"""
        entry = {
            "type": entry_type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.entries.append(entry)

    def add_thought(self, thought: str):
        """Add a thought (for ReAct pattern)"""
        self.thoughts.append(thought)
        self.add(thought, "thought")

    def add_action(self, action: str, params: Optional[Dict] = None):
        """Add an action (for ReAct pattern)"""
        action_entry = {"action": action, "params": params or {}}
        self.actions.append(action_entry)
        self.add(f"Action: {action} with {params}", "action")

    def add_observation(self, observation: str):
        """Add an observation (for ReAct pattern)"""
        self.observations.append(observation)
        self.add(observation, "observation")

    def get_context(self, last_n: Optional[int] = None) -> str:
        """Get scratchpad context as string"""
        entries_to_use = list(self.entries)
        if last_n:
            entries_to_use = entries_to_use[-last_n:]

        context_lines = []
        for entry in entries_to_use:
            if entry["type"] == "thought":
                context_lines.append(f"Thought: {entry['content']}")
            elif entry["type"] == "action":
                context_lines.append(f"Action: {entry['content']}")
            elif entry["type"] == "observation":
                context_lines.append(f"Observation: {entry['content']}")
            else:
                context_lines.append(entry['content'])

        return "\n".join(context_lines)

    def get_react_history(self) -> Dict[str, List]:
        """Get structured ReAct history"""
        return {
            "thoughts": self.thoughts,
            "actions": self.actions,
            "observations": self.observations
        }

    def clear(self):
        """Clear the scratchpad"""
        self.entries.clear()
        self.thoughts.clear()
        self.actions.clear()
        self.observations.clear()

    def __len__(self) -> int:
        return len(self.entries)

    def __str__(self) -> str:
        return f"ScratchpadMemory({len(self.entries)} entries)"


class BufferMemory:
    """
    Simple conversation buffer (wrapper around BasicSession).

    Use this when BasicSession from AbstractLLM Core is sufficient.
    This is just a thin adapter for compatibility.

    Example:
        # For a simple chatbot
        memory = BufferMemory(max_messages=50)
        memory.add_message("user", "What's the weather?")
        memory.add_message("assistant", "I don't have weather data")
        context = memory.get_context()
    """

    def __init__(self, max_messages: int = 100):
        """Initialize buffer with size limit"""
        self.messages: deque = deque(maxlen=max_messages)

    def add_message(self, role: str, content: str):
        """Add a message to the buffer"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_messages(self) -> List[Dict[str, str]]:
        """Get messages for LLM context"""
        return [{"role": m["role"], "content": m["content"]}
                for m in self.messages]

    def get_context(self, last_n: Optional[int] = None) -> str:
        """Get conversation as formatted string"""
        messages = list(self.messages)
        if last_n:
            messages = messages[-last_n:]

        lines = []
        for msg in messages:
            lines.append(f"{msg['role']}: {msg['content']}")

        return "\n".join(lines)

    def clear(self):
        """Clear the buffer"""
        self.messages.clear()