"""
Temporal knowledge graph implementation.
"""

import networkx as nx
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from abstractmemory.core.temporal import GroundingAnchor, TemporalSpan, RelationalContext


class TemporalKnowledgeGraph:
    """
    Knowledge graph with bi-temporal modeling.
    Based on Zep/Graphiti architecture.
    """

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self._node_counter = 0
        self._edge_counter = 0
        self.ontology = {}  # Auto-built ontology

    def add_entity(self, value: str, entity_type: str = 'entity') -> str:
        """Add or get entity node"""
        # Check for existing entity (deduplication)
        for node_id, data in self.graph.nodes(data=True):
            if data.get('value') == value:
                # Update access time
                self.graph.nodes[node_id]['last_accessed'] = datetime.now()
                return node_id

        # Create new entity
        node_id = f"entity_{self._node_counter}"
        self._node_counter += 1

        self.graph.add_node(
            node_id,
            value=value,
            type=entity_type,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            importance=1.0
        )

        # Update ontology
        if entity_type not in self.ontology:
            self.ontology[entity_type] = []
        self.ontology[entity_type].append(node_id)

        return node_id

    def add_fact(self, subject: str, predicate: str, object: str,
                event_time: datetime, confidence: float = 1.0,
                source: Optional[str] = None, ingestion_time: Optional[datetime] = None) -> str:
        """Add temporally anchored fact"""

        # Get or create nodes
        subj_id = self.add_entity(subject)
        obj_id = self.add_entity(object)

        # Create grounding anchor
        anchor = GroundingAnchor(
            event_time=event_time,
            ingestion_time=ingestion_time or datetime.now(),
            validity_span=TemporalSpan(start=event_time),
            relational=RelationalContext(user_id="default"),  # Will be updated when used in GroundedMemory
            confidence=confidence,
            source=source
        )

        # Check for contradictions
        self._handle_contradictions(subj_id, predicate, obj_id, anchor)

        # Add edge with temporal data
        edge_id = f"edge_{self._edge_counter}"
        self._edge_counter += 1

        self.graph.add_edge(
            subj_id, obj_id,
            key=edge_id,
            predicate=predicate,
            anchor=anchor,
            confidence=confidence,
            valid=True
        )

        return edge_id

    def _handle_contradictions(self, subj_id: str, predicate: str,
                              obj_id: str, new_anchor: GroundingAnchor):
        """Handle temporal contradictions"""
        # Check existing edges for contradictions
        for _, _, key, data in self.graph.edges(subj_id, keys=True, data=True):
            if data.get('predicate') == predicate and data.get('valid'):
                old_anchor = data.get('anchor')
                if old_anchor:
                    # Check for temporal overlap
                    if self._has_temporal_overlap(old_anchor, new_anchor):
                        # Invalidate older fact (new info takes precedence)
                        if old_anchor.ingestion_time < new_anchor.ingestion_time:
                            data['valid'] = False
                            old_anchor.validity_span.end = new_anchor.event_time
                            old_anchor.validity_span.valid = False

    def _has_temporal_overlap(self, anchor1: GroundingAnchor,
                             anchor2: GroundingAnchor) -> bool:
        """Check if two anchors have temporal overlap"""
        span1 = anchor1.validity_span
        span2 = anchor2.validity_span

        # If either span has no end, check if starts overlap
        if span1.end is None or span2.end is None:
            return True  # Conservative: assume overlap

        # Check for actual overlap
        return not (span1.end < span2.start or span2.end < span1.start)

    def query_at_time(self, query: str, point_in_time: datetime) -> List[Dict[str, Any]]:
        """Query knowledge state at specific time"""
        results = []

        for u, v, key, data in self.graph.edges(keys=True, data=True):
            anchor = data.get('anchor')
            if not anchor:
                continue

            # Check if fact was known and valid at this time
            if (anchor.ingestion_time <= point_in_time and
                anchor.event_time <= point_in_time and
                data.get('valid', True)):  # Default to True if not explicitly set

                # Check if still valid at query time
                if (anchor.validity_span.end is None or
                    anchor.validity_span.end > point_in_time):

                    # Check if matches query
                    if query.lower() in data.get('predicate', '').lower():
                        results.append({
                            'subject': self.graph.nodes[u]['value'],
                            'predicate': data['predicate'],
                            'object': self.graph.nodes[v]['value'],
                            'confidence': data.get('confidence', 1.0),
                            'event_time': anchor.event_time,
                            'source': getattr(anchor, 'source', None)
                        })

        return results

    def get_entity_evolution(self, entity: str, start: datetime,
                            end: datetime) -> List[Dict[str, Any]]:
        """Track how entity's relationships evolved over time"""
        # Find entity node
        entity_id = None
        for node_id, data in self.graph.nodes(data=True):
            if data.get('value') == entity:
                entity_id = node_id
                break

        if not entity_id:
            return []

        evolution = []

        # Check all edges involving this entity
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if u == entity_id or v == entity_id:
                anchor = data.get('anchor')
                if anchor and start <= anchor.event_time <= end:
                    evolution.append({
                        'time': anchor.event_time,
                        'type': 'fact_added' if data.get('valid') else 'fact_invalidated',
                        'subject': self.graph.nodes[u]['value'],
                        'predicate': data['predicate'],
                        'object': self.graph.nodes[v]['value']
                    })

        return sorted(evolution, key=lambda x: x['time'])