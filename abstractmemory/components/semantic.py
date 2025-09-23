"""
Semantic memory for facts, concepts, and learned knowledge.
Separate from Core (identity) and Episodic (events).
"""

from typing import List, Dict, Set
from datetime import datetime
from collections import defaultdict

from abstractmemory.core.interfaces import IMemoryComponent, MemoryItem


class SemanticMemory(IMemoryComponent):
    """
    Long-term storage of facts and concepts learned over time.
    Only stores validated, recurring knowledge.
    """

    def __init__(self, validation_threshold: int = 3):
        """
        Args:
            validation_threshold: How many times a fact must be observed to be stored
        """
        self.facts: Dict[str, Dict] = {}  # Validated facts
        self.concepts: Dict[str, Set[str]] = {}  # Concept relationships
        self.pending_facts: defaultdict = defaultdict(int)  # Counting occurrences
        self.validation_threshold = validation_threshold

    def add(self, item: MemoryItem) -> str:
        """Add potential fact - only stored after validation"""
        fact_key = str(item.content).lower()

        # Count occurrence
        self.pending_facts[fact_key] += 1

        # Promote to validated facts if threshold met
        if self.pending_facts[fact_key] >= self.validation_threshold:
            fact_id = f"fact_{len(self.facts)}_{datetime.now().timestamp()}"
            occurrence_count = self.pending_facts[fact_key]
            self.facts[fact_id] = {
                'content': item.content,
                'confidence': min(1.0, occurrence_count * 0.1 + 0.3),  # Confidence grows with repetition
                'first_seen': item.event_time,
                'validated_at': datetime.now(),
                'occurrence_count': occurrence_count,
                'original_metadata': item.metadata or {}
            }
            # Clear from pending
            del self.pending_facts[fact_key]
            return fact_id

        return ""  # Not yet validated

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Retrieve validated facts matching query"""
        results = []
        query_lower = query.lower()

        for fact_id, fact in self.facts.items():
            if query_lower in str(fact['content']).lower():
                # Preserve original metadata and add occurrence count
                original_metadata = fact.get('original_metadata', {})
                metadata = original_metadata.copy()
                metadata['occurrence_count'] = fact['occurrence_count']

                results.append(MemoryItem(
                    content=fact['content'],
                    event_time=fact['first_seen'],
                    ingestion_time=fact['validated_at'],
                    confidence=fact['confidence'],
                    metadata=metadata
                ))
                if len(results) >= limit:
                    break

        # Sort by confidence and return results
        sorted_results = sorted(results, key=lambda x: x.confidence, reverse=True)[:limit]
        return sorted_results

    def consolidate(self) -> int:
        """Link related facts into concepts"""
        consolidated = 0
        # Group facts by common terms
        for fact_id, fact in self.facts.items():
            words = str(fact['content']).lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    if word not in self.concepts:
                        self.concepts[word] = set()
                    self.concepts[word].add(fact_id)
                    consolidated += 1
        return consolidated

    def get_concept_network(self, concept: str) -> Dict[str, Set[str]]:
        """Get related facts for a concept"""
        if concept.lower() in self.concepts:
            fact_ids = self.concepts[concept.lower()]
            return {
                'concept': concept,
                'facts': [self.facts[fid]['content'] for fid in fact_ids if fid in self.facts]
            }
        return {'concept': concept, 'facts': []}