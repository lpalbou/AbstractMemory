"""
Knowledge Graph Storage for AbstractMemory.

Implements the third storage layer for relationship understanding using NetworkX.
This provides the graph database capabilities for SPO triples and relationship mapping.

Storage Layers:
1. Filesystem - Human-readable markdown files
2. LanceDB - Vector embeddings for semantic search  
3. Knowledge Graph - Relationship understanding (THIS MODULE)
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import pickle

# Use NetworkX for graph operations (lighter than Neo4j for this use case)
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphTriple:
    """Represents a knowledge graph triple with metadata."""
    subject: str
    predicate: str
    object: str
    confidence: float
    timestamp: datetime
    source: str
    importance: float = 0.5
    relationship_type: str = "associative"
    context: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'subject': self.subject,
            'predicate': self.predicate,
            'object': self.object,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'importance': self.importance,
            'relationship_type': self.relationship_type,
            'context': self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphTriple':
        """Create from dictionary."""
        return cls(
            subject=data['subject'],
            predicate=data['predicate'],
            object=data['object'],
            confidence=data['confidence'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            source=data['source'],
            importance=data.get('importance', 0.5),
            relationship_type=data.get('relationship_type', 'associative'),
            context=data.get('context', '')
        )


class KnowledgeGraphStorage:
    """
    Knowledge Graph Storage using NetworkX.
    
    Provides the third storage layer for AbstractMemory, focusing on:
    - Subject-Predicate-Object triple storage
    - Relationship mapping between concepts
    - Graph-based queries and traversal
    - Contradiction detection
    - Relationship inference
    """

    def __init__(self, storage_path: Path):
        """
        Initialize Knowledge Graph Storage.

        Args:
            storage_path: Path to store graph data
        """
        if not NETWORKX_AVAILABLE:
            raise ImportError("NetworkX is required for Knowledge Graph Storage. Install with: pip install networkx")
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.graph_file = self.storage_path / "knowledge_graph.gpickle"
        self.metadata_file = self.storage_path / "graph_metadata.json"
        
        self.logger = get_logger(__name__)
        
        # Initialize or load the graph
        self.graph = self._load_or_create_graph()
        self.metadata = self._load_metadata()
        
        self.logger.info(f"KnowledgeGraphStorage initialized with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")

    def _load_or_create_graph(self) -> nx.MultiDiGraph:
        """Load existing graph or create new one."""
        if self.graph_file.exists():
            try:
                # Try different NetworkX loading methods for compatibility
                try:
                    graph = nx.read_gpickle(self.graph_file)
                except AttributeError:
                    # Fallback for newer NetworkX versions
                    import pickle
                    with open(self.graph_file, 'rb') as f:
                        graph = pickle.load(f)
                self.logger.info(f"Loaded existing knowledge graph from {self.graph_file}")
                return graph
            except Exception as e:
                self.logger.warning(f"Failed to load graph, creating new one: {e}")
        
        # Create new directed multigraph (allows multiple edges between same nodes)
        graph = nx.MultiDiGraph()
        self.logger.info("Created new knowledge graph")
        return graph

    def _load_metadata(self) -> Dict[str, Any]:
        """Load graph metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load metadata: {e}")
        
        return {
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'total_triples': 0,
            'relationship_types': set()
        }

    def _save_graph(self):
        """Save graph to disk."""
        try:
            # Try different NetworkX saving methods for compatibility
            try:
                nx.write_gpickle(self.graph, self.graph_file)
            except AttributeError:
                # Fallback for newer NetworkX versions
                import pickle
                with open(self.graph_file, 'wb') as f:
                    pickle.dump(self.graph, f)
            
            self.metadata['last_updated'] = datetime.now().isoformat()
            self.metadata['total_triples'] = self.graph.number_of_edges()
            
            with open(self.metadata_file, 'w') as f:
                # Convert set to list for JSON serialization
                metadata_copy = self.metadata.copy()
                if 'relationship_types' in metadata_copy and isinstance(metadata_copy['relationship_types'], set):
                    metadata_copy['relationship_types'] = list(metadata_copy['relationship_types'])
                json.dump(metadata_copy, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save graph: {e}")

    def add_triple(self, triple: GraphTriple) -> str:
        """
        Add a triple to the knowledge graph.

        Args:
            triple: GraphTriple to add

        Returns:
            str: Edge ID of the added triple
        """
        try:
            # Add nodes if they don't exist
            if not self.graph.has_node(triple.subject):
                self.graph.add_node(triple.subject, 
                                  node_type="concept", 
                                  first_seen=triple.timestamp.isoformat())
            
            if not self.graph.has_node(triple.object):
                self.graph.add_node(triple.object, 
                                  node_type="concept", 
                                  first_seen=triple.timestamp.isoformat())
            
            # Add edge with triple metadata
            edge_data = triple.to_dict()
            edge_id = self.graph.add_edge(
                triple.subject, 
                triple.object, 
                key=f"{triple.predicate}_{triple.timestamp.strftime('%Y%m%d_%H%M%S')}",
                **edge_data
            )
            
            # Update metadata
            if 'relationship_types' not in self.metadata:
                self.metadata['relationship_types'] = set()
            self.metadata['relationship_types'].add(triple.relationship_type)
            
            # Save periodically (every 10 triples)
            if self.graph.number_of_edges() % 10 == 0:
                self._save_graph()
            
            self.logger.debug(f"Added triple: {triple.subject} -{triple.predicate}-> {triple.object}")
            return str(edge_id)
            
        except Exception as e:
            self.logger.error(f"Error adding triple: {e}")
            return ""

    def find_related_concepts(self, concept: str, depth: int = 2, min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find concepts related to given concept within specified depth.

        Args:
            concept: Starting concept
            depth: Maximum traversal depth
            min_confidence: Minimum confidence threshold

        Returns:
            List[Dict]: Related concepts with relationship metadata
        """
        try:
            if not self.graph.has_node(concept):
                return []
            
            related = []
            visited = set()
            
            # BFS traversal up to specified depth
            current_level = {concept}
            
            for current_depth in range(depth):
                next_level = set()
                
                for node in current_level:
                    if node in visited:
                        continue
                    visited.add(node)
                    
                    # Get all neighbors (both incoming and outgoing)
                    for neighbor in self.graph.neighbors(node):
                        if neighbor not in visited:
                            # Get edge data for all edges between node and neighbor
                            edges = self.graph.get_edge_data(node, neighbor)
                            if edges:
                                for edge_key, edge_data in edges.items():
                                    confidence = edge_data.get('confidence', 0.0)
                                    if confidence >= min_confidence:
                                        related.append({
                                            'concept': neighbor,
                                            'relationship': edge_data.get('predicate', 'unknown'),
                                            'confidence': confidence,
                                            'distance': current_depth + 1,
                                            'relationship_type': edge_data.get('relationship_type', 'associative'),
                                            'source': edge_data.get('source', 'unknown'),
                                            'timestamp': edge_data.get('timestamp', '')
                                        })
                                        next_level.add(neighbor)
                    
                    # Also check incoming edges
                    for predecessor in self.graph.predecessors(node):
                        if predecessor not in visited:
                            edges = self.graph.get_edge_data(predecessor, node)
                            if edges:
                                for edge_key, edge_data in edges.items():
                                    confidence = edge_data.get('confidence', 0.0)
                                    if confidence >= min_confidence:
                                        related.append({
                                            'concept': predecessor,
                                            'relationship': f"inverse_{edge_data.get('predicate', 'unknown')}",
                                            'confidence': confidence,
                                            'distance': current_depth + 1,
                                            'relationship_type': edge_data.get('relationship_type', 'associative'),
                                            'source': edge_data.get('source', 'unknown'),
                                            'timestamp': edge_data.get('timestamp', '')
                                        })
                                        next_level.add(predecessor)
                
                current_level = next_level
                if not current_level:
                    break
            
            # Sort by confidence and distance
            related.sort(key=lambda x: (-x['confidence'], x['distance']))
            
            self.logger.debug(f"Found {len(related)} related concepts for '{concept}' within depth {depth}")
            return related
            
        except Exception as e:
            self.logger.error(f"Error finding related concepts: {e}")
            return []

    def detect_contradictions(self, confidence_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Detect contradictory relationships in the graph.

        Args:
            confidence_threshold: Minimum confidence for contradiction detection

        Returns:
            List[Dict]: Detected contradictions
        """
        try:
            contradictions = []
            
            # Define opposing relationship patterns
            opposing_patterns = [
                ('supports', 'contradicts'),
                ('enables', 'prevents'),
                ('causes', 'prevents'),
                ('agrees_with', 'disagrees_with'),
                ('confirms', 'refutes')
            ]
            
            # Check all node pairs for contradictory relationships
            for node1 in self.graph.nodes():
                for node2 in self.graph.nodes():
                    if node1 == node2:
                        continue
                    
                    # Get all edges between these nodes (in both directions)
                    edges_1_to_2 = self.graph.get_edge_data(node1, node2) or {}
                    edges_2_to_1 = self.graph.get_edge_data(node2, node1) or {}
                    
                    all_edges = []
                    for edge_data in edges_1_to_2.values():
                        all_edges.append((node1, node2, edge_data))
                    for edge_data in edges_2_to_1.values():
                        all_edges.append((node2, node1, edge_data))
                    
                    # Check for contradictory predicates
                    for i, (subj1, obj1, edge1) in enumerate(all_edges):
                        for j, (subj2, obj2, edge2) in enumerate(all_edges):
                            if i >= j:
                                continue
                            
                            pred1 = edge1.get('predicate', '').lower()
                            pred2 = edge2.get('predicate', '').lower()
                            conf1 = edge1.get('confidence', 0.0)
                            conf2 = edge2.get('confidence', 0.0)
                            
                            if conf1 < confidence_threshold or conf2 < confidence_threshold:
                                continue
                            
                            # Check if predicates are contradictory
                            for pos_pred, neg_pred in opposing_patterns:
                                if ((pos_pred in pred1 and neg_pred in pred2) or 
                                    (neg_pred in pred1 and pos_pred in pred2)):
                                    
                                    contradictions.append({
                                        'node1': subj1,
                                        'node2': obj1,
                                        'predicate1': pred1,
                                        'predicate2': pred2,
                                        'confidence1': conf1,
                                        'confidence2': conf2,
                                        'source1': edge1.get('source', 'unknown'),
                                        'source2': edge2.get('source', 'unknown'),
                                        'timestamp1': edge1.get('timestamp', ''),
                                        'timestamp2': edge2.get('timestamp', ''),
                                        'contradiction_type': f"{pos_pred}_vs_{neg_pred}"
                                    })
            
            self.logger.info(f"Detected {len(contradictions)} potential contradictions")
            return contradictions
            
        except Exception as e:
            self.logger.error(f"Error detecting contradictions: {e}")
            return []

    def get_concept_summary(self, concept: str) -> Dict[str, Any]:
        """
        Get summary information about a concept.

        Args:
            concept: Concept to summarize

        Returns:
            Dict: Concept summary with relationships and metadata
        """
        try:
            if not self.graph.has_node(concept):
                return {'exists': False}
            
            node_data = self.graph.nodes[concept]
            
            # Get all outgoing relationships
            outgoing = []
            for target in self.graph.neighbors(concept):
                edges = self.graph.get_edge_data(concept, target)
                for edge_data in edges.values():
                    outgoing.append({
                        'target': target,
                        'predicate': edge_data.get('predicate', 'unknown'),
                        'confidence': edge_data.get('confidence', 0.0),
                        'relationship_type': edge_data.get('relationship_type', 'associative')
                    })
            
            # Get all incoming relationships
            incoming = []
            for source in self.graph.predecessors(concept):
                edges = self.graph.get_edge_data(source, concept)
                for edge_data in edges.values():
                    incoming.append({
                        'source': source,
                        'predicate': edge_data.get('predicate', 'unknown'),
                        'confidence': edge_data.get('confidence', 0.0),
                        'relationship_type': edge_data.get('relationship_type', 'associative')
                    })
            
            return {
                'exists': True,
                'concept': concept,
                'node_data': node_data,
                'outgoing_relationships': outgoing,
                'incoming_relationships': incoming,
                'total_relationships': len(outgoing) + len(incoming),
                'first_seen': node_data.get('first_seen', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error getting concept summary: {e}")
            return {'exists': False, 'error': str(e)}

    def query_by_predicate(self, predicate: str, min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """
        Query all triples with a specific predicate.

        Args:
            predicate: Predicate to search for
            min_confidence: Minimum confidence threshold

        Returns:
            List[Dict]: Matching triples
        """
        try:
            results = []
            
            for source, target, edge_data in self.graph.edges(data=True):
                if (edge_data.get('predicate', '').lower() == predicate.lower() and 
                    edge_data.get('confidence', 0.0) >= min_confidence):
                    
                    results.append({
                        'subject': source,
                        'predicate': edge_data.get('predicate'),
                        'object': target,
                        'confidence': edge_data.get('confidence'),
                        'relationship_type': edge_data.get('relationship_type'),
                        'source': edge_data.get('source'),
                        'timestamp': edge_data.get('timestamp')
                    })
            
            # Sort by confidence
            results.sort(key=lambda x: -x['confidence'])
            
            self.logger.debug(f"Found {len(results)} triples with predicate '{predicate}'")
            return results
            
        except Exception as e:
            self.logger.error(f"Error querying by predicate: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        try:
            stats = {
                'nodes': self.graph.number_of_nodes(),
                'edges': self.graph.number_of_edges(),
                'relationship_types': list(self.metadata.get('relationship_types', [])),
                'created_at': self.metadata.get('created_at'),
                'last_updated': self.metadata.get('last_updated'),
                'storage_path': str(self.storage_path)
            }
            
            # Calculate additional statistics
            if stats['nodes'] > 0:
                stats['avg_connections_per_node'] = stats['edges'] / stats['nodes']
            else:
                stats['avg_connections_per_node'] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    def save(self):
        """Explicitly save the graph to disk."""
        self._save_graph()
        self.logger.info("Knowledge graph saved to disk")

    def close(self):
        """Close and save the knowledge graph."""
        self.save()


def create_knowledge_graph(storage_path: Path) -> KnowledgeGraphStorage:
    """
    Create a KnowledgeGraphStorage instance.

    Args:
        storage_path: Path to store graph data

    Returns:
        KnowledgeGraphStorage instance
    """
    return KnowledgeGraphStorage(storage_path=storage_path)
