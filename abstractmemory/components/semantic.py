"""
Semantic memory for facts, concepts, and learned knowledge.
Separate from Core (identity) and Episodic (events).
"""

from typing import List, Dict, Set, Any
from datetime import datetime
from collections import defaultdict

from abstractmemory.core.interfaces import IMemoryComponent, MemoryItem


class SemanticMemory(IMemoryComponent):
    """
    Long-term storage of facts and concepts learned over time.
    Only stores validated, recurring knowledge.
    """

    def __init__(self, validation_threshold: int = 3, embedding_provider=None):
        """
        Args:
            validation_threshold: How many times a fact must be observed to be stored
            embedding_provider: Provider for semantic embeddings (optional)
                                When available, enables semantic search over facts
        """
        self.facts: Dict[str, Dict] = {}  # Validated facts
        self.concepts: Dict[str, Set[str]] = {}  # Concept relationships
        self.pending_facts: defaultdict = defaultdict(int)  # Counting occurrences
        self.validation_threshold = validation_threshold
        self.embedding_provider = embedding_provider
        self.fact_embeddings: Dict[str, List[float]] = {}  # fact_id -> embedding

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

            # Generate embedding if provider available
            if self.embedding_provider:
                try:
                    fact_embedding = self.embedding_provider.generate_embedding(str(item.content))
                    self.fact_embeddings[fact_id] = fact_embedding
                except Exception as e:
                    # Continue without embedding if generation fails
                    import logging
                    logging.debug(f"Failed to generate embedding for fact {fact_id}: {e}")

            # Clear from pending
            del self.pending_facts[fact_key]
            return fact_id

        return ""  # Not yet validated

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """
        Retrieve validated facts matching query.
        Uses semantic search (embeddings) when available, otherwise falls back to keyword search.
        """
        # Try semantic search first if embeddings available
        if self.embedding_provider and self.fact_embeddings:
            semantic_results = self._semantic_search(query, limit)
            if semantic_results:
                return semantic_results

        # Fallback to keyword search
        return self._keyword_search(query, limit)

    def _semantic_search(self, query: str, limit: int) -> List[MemoryItem]:
        """Perform semantic search using embeddings."""
        try:
            # Generate query embedding
            query_embedding = self.embedding_provider.generate_embedding(query)

            # Calculate similarities
            fact_scores = []
            for fact_id, fact_embedding in self.fact_embeddings.items():
                if fact_id in self.facts:  # Ensure fact still exists
                    similarity = self._cosine_similarity(query_embedding, fact_embedding)
                    fact_scores.append((similarity, fact_id))

            # Sort by similarity and get top results
            fact_scores.sort(key=lambda x: x[0], reverse=True)

            # Convert to MemoryItems
            results = []
            for similarity, fact_id in fact_scores[:limit]:
                fact = self.facts[fact_id]

                # Preserve original metadata and add search metadata
                original_metadata = fact.get('original_metadata', {})
                metadata = original_metadata.copy()
                metadata['occurrence_count'] = fact['occurrence_count']
                metadata['semantic_similarity'] = similarity
                metadata['search_type'] = 'semantic'

                # Boost confidence with semantic similarity
                boosted_confidence = min(1.0, fact['confidence'] * (1 + similarity * 0.5))

                results.append(MemoryItem(
                    content=fact['content'],
                    event_time=fact['first_seen'],
                    ingestion_time=fact['validated_at'],
                    confidence=boosted_confidence,
                    metadata=metadata
                ))

            return results

        except Exception as e:
            import logging
            logging.debug(f"Semantic search failed, falling back to keyword search: {e}")
            return []

    def _keyword_search(self, query: str, limit: int) -> List[MemoryItem]:
        """Fallback keyword search."""
        results = []
        query_lower = query.lower()

        for fact_id, fact in self.facts.items():
            if query_lower in str(fact['content']).lower():
                # Preserve original metadata and add occurrence count
                original_metadata = fact.get('original_metadata', {})
                metadata = original_metadata.copy()
                metadata['occurrence_count'] = fact['occurrence_count']
                metadata['search_type'] = 'keyword'

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

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import math

            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0

            return dot_product / (magnitude1 * magnitude2)
        except:
            return 0

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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize semantic memory to dictionary"""
        # Convert datetime objects to ISO strings
        facts_data = {}
        for fact_id, fact in self.facts.items():
            facts_data[fact_id] = {
                'content': fact['content'],
                'confidence': fact['confidence'],
                'first_seen': fact['first_seen'].isoformat() if fact['first_seen'] else None,
                'validated_at': fact['validated_at'].isoformat() if fact['validated_at'] else None,
                'occurrence_count': fact['occurrence_count'],
                'original_metadata': fact['original_metadata']
            }

        # Convert sets to lists for JSON serialization
        concepts_data = {}
        for concept, fact_ids in self.concepts.items():
            concepts_data[concept] = list(fact_ids)

        return {
            'facts': facts_data,
            'concepts': concepts_data,
            'pending_facts': dict(self.pending_facts),
            'validation_threshold': self.validation_threshold
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticMemory':
        """Deserialize semantic memory from dictionary"""
        # Create instance
        instance = cls.__new__(cls)
        instance.validation_threshold = data.get('validation_threshold', 3)
        instance.pending_facts = defaultdict(int, data.get('pending_facts', {}))
        instance.facts = {}
        instance.concepts = {}

        # Reconstruct facts
        facts_data = data.get('facts', {})
        for fact_id, fact_data in facts_data.items():
            try:
                first_seen = datetime.fromisoformat(fact_data['first_seen']) if fact_data.get('first_seen') else None
                validated_at = datetime.fromisoformat(fact_data['validated_at']) if fact_data.get('validated_at') else None
            except (ValueError, TypeError):
                first_seen = None
                validated_at = None

            instance.facts[fact_id] = {
                'content': fact_data.get('content', ''),
                'confidence': fact_data.get('confidence', 0.5),
                'first_seen': first_seen,
                'validated_at': validated_at,
                'occurrence_count': fact_data.get('occurrence_count', 1),
                'original_metadata': fact_data.get('original_metadata', {})
            }

        # Reconstruct concepts
        concepts_data = data.get('concepts', {})
        for concept, fact_ids in concepts_data.items():
            instance.concepts[concept] = set(fact_ids)

        return instance