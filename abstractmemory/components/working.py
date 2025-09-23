"""
Working memory with sliding window.
"""

from collections import deque
from typing import List, Optional
from datetime import datetime

from abstractmemory.core.interfaces import IMemoryComponent, MemoryItem


class WorkingMemory(IMemoryComponent):
    """Short-term working memory with fixed capacity"""

    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.items = deque(maxlen=capacity)

    def add(self, item: MemoryItem) -> str:
        """Add item to working memory"""
        item_id = f"wm_{datetime.now().timestamp()}"
        self.items.append((item_id, item))

        # Auto-consolidate if over capacity (deque will handle max capacity automatically)
        return item_id

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Retrieve recent items matching query"""
        results = []
        query_lower = query.lower()

        for item_id, item in self.items:
            if query_lower in str(item.content).lower():
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    def consolidate(self) -> int:
        """Move old items to episodic memory"""
        # In real implementation, would move to episodic
        to_consolidate = len(self.items) // 2
        for _ in range(to_consolidate):
            self.items.popleft()
        return to_consolidate

    def get_context_window(self) -> List[MemoryItem]:
        """Get current context window"""
        return [item for _, item in self.items]