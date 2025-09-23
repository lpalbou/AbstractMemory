"""
Bi-temporal data model based on Zep/Graphiti research.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TemporalSpan:
    """Represents a time span with validity"""
    start: datetime
    end: Optional[datetime] = None
    valid: bool = True


@dataclass
class RelationalContext:
    """Who is involved in this memory"""
    user_id: str                     # Primary user/speaker
    agent_id: Optional[str] = None   # Which agent persona
    relationship: Optional[str] = None  # "owner", "colleague", "stranger"
    session_id: Optional[str] = None   # Conversation session

@dataclass
class GroundingAnchor:
    """Multi-dimensional grounding for experiential memory"""
    # Temporal grounding (when)
    event_time: datetime        # When it happened
    ingestion_time: datetime    # When we learned about it
    validity_span: TemporalSpan # When it was/is valid

    # Relational grounding (who)
    relational: RelationalContext  # Who is involved

    # Additional grounding
    confidence: float = 1.0
    source: Optional[str] = None
    location: Optional[str] = None  # Where (optional)


class TemporalIndex:
    """Index for efficient temporal queries"""

    def __init__(self):
        self._by_event_time = []      # Sorted by event time
        self._by_ingestion_time = []  # Sorted by ingestion time
        self._anchors = {}             # ID -> GroundingAnchor

    def add_anchor(self, anchor_id: str, anchor: GroundingAnchor):
        """Add temporal anchor to index"""
        self._anchors[anchor_id] = anchor

        # Insert into sorted lists
        self._insert_sorted(self._by_event_time,
                          (anchor.event_time, anchor_id))
        self._insert_sorted(self._by_ingestion_time,
                          (anchor.ingestion_time, anchor_id))

    def query_at_time(self, point_in_time: datetime,
                     use_event_time: bool = True) -> List[str]:
        """Get valid anchor IDs at specific time"""
        valid_ids = []

        for anchor_id, anchor in self._anchors.items():
            # Check if anchor was known at this time
            if anchor.ingestion_time > point_in_time:
                continue

            # Check if anchor was valid at this time
            if use_event_time:
                if anchor.event_time <= point_in_time:
                    if anchor.validity_span.valid:
                        if (anchor.validity_span.end is None or
                            anchor.validity_span.end > point_in_time):
                            valid_ids.append(anchor_id)

        return valid_ids

    def _insert_sorted(self, lst: list, item: tuple):
        """Insert item into sorted list"""
        import bisect
        bisect.insort(lst, item)

    def get_evolution(self, start: datetime, end: datetime) -> List[Tuple[datetime, str]]:
        """Get evolution of knowledge between times"""
        changes = []

        for anchor_id, anchor in self._anchors.items():
            # Include if ingested during period
            if start <= anchor.ingestion_time <= end:
                changes.append((anchor.ingestion_time, f"Added: {anchor_id}"))

            # Include if invalidated during period
            if anchor.validity_span.end:
                if start <= anchor.validity_span.end <= end:
                    changes.append((anchor.validity_span.end, f"Invalidated: {anchor_id}"))

        return sorted(changes)