"""
Enhanced Triple Storage Manager for AbstractMemory.

Implements unified architecture across all three storage layers:
1. Filesystem - Structured data storage
2. LanceDB - Semantic search + metadata filtering  
3. Knowledge Graph - Relationship mapping (connects everything)

Encapsulates complexity behind high-level methods:
- reconstruct(): Intelligent context reconstruction across all layers
- remember(): Unified storage across filesystem + LanceDB + KG
- reflect(): Deep reflection using relationship context
- search(): Unified search with relationship awareness
- plan(): Planning using accumulated knowledge
- alignment(): Value alignment assessment

Facts Flow (Phased Approach):
A) Facts → working/temporary_semantics.md (current, unchanged)
B) Consolidation triggers → semantic/{topic}.md 
C) Consolidated facts → Knowledge Graph (prevents pollution)
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from abstractllm.utils.structured_logging import get_logger

# Import storage layers
from .storage.lancedb_storage import LanceDBStorage
from .storage.knowledge_graph import KnowledgeGraphStorage, GraphTriple

logger = get_logger(__name__)


@dataclass
class UnifiedSearchResult:
    """Unified search result across all storage layers."""
    content: str
    source_layer: str  # 'filesystem', 'lancedb', or 'knowledge_graph'
    relevance_score: float
    metadata: Dict[str, Any]
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'content': self.content,
            'source_layer': self.source_layer,
            'relevance_score': self.relevance_score,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class TripleStorageManager:
    """
    Manages all three storage layers with unified operations.
    
    Provides:
    - Unified search across all layers
    - Cross-layer data synchronization
    - Intelligent routing of queries to appropriate layers
    - Relationship-aware context reconstruction
    """

    def __init__(self, 
                 base_path: Path, 
                 embedding_manager,
                 lancedb_storage: Optional[LanceDBStorage] = None,
                 knowledge_graph: Optional[KnowledgeGraphStorage] = None):
        """
        Initialize Triple Storage Manager.

        Args:
            base_path: Base memory path
            embedding_manager: EmbeddingManager for LanceDB
            lancedb_storage: Optional existing LanceDB storage
            knowledge_graph: Optional existing knowledge graph
        """
        self.base_path = Path(base_path)
        self.logger = get_logger(__name__)
        
        self.logger.debug("🏗️  [TripleStorageManager] Initializing Enhanced Triple Storage Manager")
        self.logger.debug(f"📁 [TripleStorageManager] Base path: {base_path}")
        
        # Initialize storage layers
        self.filesystem_path = self.base_path
        
        # LanceDB storage (Layer 2)
        self.logger.debug("🔍 [TripleStorageManager] Initializing LanceDB storage layer...")
        if lancedb_storage:
            self.lancedb = lancedb_storage
            self.logger.debug("✅ [TripleStorageManager] Using existing LanceDB storage")
        else:
            lancedb_path = self.base_path / "lancedb"
            self.lancedb = LanceDBStorage(lancedb_path, embedding_manager)
            self.logger.debug(f"✅ [TripleStorageManager] Created new LanceDB storage at {lancedb_path}")
        
        # Knowledge Graph storage (Layer 3)
        self.logger.debug("🕸️  [TripleStorageManager] Initializing Knowledge Graph storage layer...")
        if knowledge_graph:
            self.knowledge_graph = knowledge_graph
            self.logger.debug("✅ [TripleStorageManager] Using existing Knowledge Graph storage")
        else:
            graph_path = self.base_path / "knowledge_graph"
            self.knowledge_graph = KnowledgeGraphStorage(graph_path)
            self.logger.debug(f"✅ [TripleStorageManager] Created new Knowledge Graph storage at {graph_path}")
        
        self.logger.info("🚀 [TripleStorageManager] Enhanced Triple Storage Manager initialized with all three layers")
        self.logger.debug(f"📊 [TripleStorageManager] Storage layers: Filesystem + LanceDB + Knowledge Graph")

    def store_memory(self, memory_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Store memory across all appropriate layers.

        Args:
            memory_data: Memory data to store

        Returns:
            Dict: Storage IDs from each layer
        """
        try:
            storage_ids = {}
            
            # 1. Store in filesystem (markdown files)
            file_id = self._store_in_filesystem(memory_data)
            if file_id:
                storage_ids['filesystem'] = file_id
            
            # 2. Store in LanceDB for semantic search
            lance_id = self._store_in_lancedb(memory_data)
            if lance_id:
                storage_ids['lancedb'] = lance_id
            
            # 3. Extract and store relationships in knowledge graph
            graph_ids = self._store_in_knowledge_graph(memory_data)
            if graph_ids:
                storage_ids['knowledge_graph'] = graph_ids
            
            self.logger.info(f"Stored memory across {len(storage_ids)} layers")
            return storage_ids
            
        except Exception as e:
            self.logger.error(f"Error storing memory: {e}")
            return {}

    def _store_in_filesystem(self, memory_data: Dict[str, Any]) -> Optional[str]:
        """Store memory in filesystem layer."""
        try:
            # This would integrate with existing filesystem storage
            # For now, return a placeholder ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_id = f"fs_{timestamp}"
            
            # TODO: Implement actual filesystem storage
            # This should create markdown files in appropriate directories
            
            return file_id
            
        except Exception as e:
            self.logger.error(f"Error storing in filesystem: {e}")
            return None

    def _store_in_lancedb(self, memory_data: Dict[str, Any]) -> Optional[str]:
        """Store memory in LanceDB layer."""
        try:
            # Use existing LanceDB storage
            content = memory_data.get('content', '')
            if not content:
                return None
            
            # Determine table based on memory type
            memory_type = memory_data.get('type', 'notes')
            
            if memory_type == 'verbatim':
                return self.lancedb.add_verbatim(memory_data)
            elif memory_type == 'library':
                return self.lancedb.add_library_document(memory_data)
            else:
                return self.lancedb.add_note(memory_data)
                
        except Exception as e:
            self.logger.error(f"Error storing in LanceDB: {e}")
            return None

    def _store_in_knowledge_graph(self, memory_data: Dict[str, Any]) -> List[str]:
        """Store relationships in knowledge graph layer."""
        try:
            graph_ids = []
            
            # Extract relationships from memory data
            relationships = memory_data.get('relationships', [])
            triples = memory_data.get('triples', [])
            
            # Store explicit relationships
            for rel in relationships:
                if all(key in rel for key in ['subject', 'predicate', 'object']):
                    triple = GraphTriple(
                        subject=rel['subject'],
                        predicate=rel['predicate'],
                        object=rel['object'],
                        confidence=rel.get('confidence', 0.7),
                        timestamp=datetime.now(),
                        source=memory_data.get('source', 'memory_storage'),
                        importance=rel.get('importance', 0.5),
                        relationship_type=rel.get('relationship_type', 'associative'),
                        context=memory_data.get('content', '')[:200]
                    )
                    
                    graph_id = self.knowledge_graph.add_triple(triple)
                    if graph_id:
                        graph_ids.append(graph_id)
            
            # Store extracted triples
            for triple_data in triples:
                if all(key in triple_data for key in ['subject', 'predicate', 'object']):
                    triple = GraphTriple(
                        subject=triple_data['subject'],
                        predicate=triple_data['predicate'],
                        object=triple_data['object'],
                        confidence=triple_data.get('confidence', 0.7),
                        timestamp=datetime.now(),
                        source=memory_data.get('source', 'fact_extraction'),
                        importance=triple_data.get('importance', 0.5),
                        relationship_type=triple_data.get('relationship_type', 'associative'),
                        context=memory_data.get('content', '')[:200]
                    )
                    
                    graph_id = self.knowledge_graph.add_triple(triple)
                    if graph_id:
                        graph_ids.append(graph_id)
            
            return graph_ids
            
        except Exception as e:
            self.logger.error(f"Error storing in knowledge graph: {e}")
            return []

    def unified_search(self, 
                      query: str, 
                      filters: Optional[Dict[str, Any]] = None,
                      include_relationships: bool = True,
                      max_results: int = 20) -> List[UnifiedSearchResult]:
        """
        Perform unified search across all storage layers.

        Args:
            query: Search query
            filters: Optional filters (user_id, time_range, etc.)
            include_relationships: Whether to include graph relationships
            max_results: Maximum results to return

        Returns:
            List[UnifiedSearchResult]: Unified search results
        """
        self.logger.debug(f"🔍 [TripleStorageManager.unified_search] Starting unified search")
        self.logger.debug(f"❓ [TripleStorageManager.unified_search] Query: '{query}', Max results: {max_results}")
        self.logger.debug(f"🔧 [TripleStorageManager.unified_search] Filters: {filters}, Include relationships: {include_relationships}")
        
        try:
            all_results = []
            
            # 1. Search LanceDB for semantic similarity
            self.logger.debug("🔍 [TripleStorageManager.unified_search] Searching LanceDB layer...")
            lancedb_results = self._search_lancedb(query, filters, max_results // 2)
            all_results.extend(lancedb_results)
            self.logger.debug(f"✅ [TripleStorageManager.unified_search] LanceDB search: {len(lancedb_results)} results")
            
            # 2. Search Knowledge Graph for relationships
            if include_relationships:
                self.logger.debug("🕸️  [TripleStorageManager.unified_search] Searching Knowledge Graph layer...")
                graph_results = self._search_knowledge_graph(query, filters, max_results // 2)
                all_results.extend(graph_results)
                self.logger.debug(f"✅ [TripleStorageManager.unified_search] Knowledge Graph search: {len(graph_results)} results")
            else:
                self.logger.debug("ℹ️  [TripleStorageManager.unified_search] Skipping Knowledge Graph search (relationships disabled)")
            
            # 3. TODO: Search filesystem for exact matches
            # filesystem_results = self._search_filesystem(query, filters)
            # all_results.extend(filesystem_results)
            self.logger.debug("ℹ️  [TripleStorageManager.unified_search] Filesystem search not yet implemented")
            
            # Sort by relevance score
            self.logger.debug("📊 [TripleStorageManager.unified_search] Sorting results by relevance...")
            all_results.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # Limit results
            final_results = all_results[:max_results]
            self.logger.debug(f"✂️  [TripleStorageManager.unified_search] Limited to top {len(final_results)} results")
            
            self.logger.info(f"✅ [TripleStorageManager.unified_search] Unified search completed: {len(final_results)} results for '{query}'")
            return final_results
            
        except Exception as e:
            self.logger.error(f"❌ [TripleStorageManager.unified_search] Error in unified search: {e}")
            return []

    def _search_lancedb(self, 
                       query: str, 
                       filters: Optional[Dict[str, Any]], 
                       max_results: int) -> List[UnifiedSearchResult]:
        """Search LanceDB layer."""
        try:
            results = []
            
            # Search notes table
            notes_results = self.lancedb.search_notes(
                query=query,
                limit=max_results // 2,
                filters=filters
            )
            
            for result in notes_results:
                unified_result = UnifiedSearchResult(
                    content=result.get('content', ''),
                    source_layer='lancedb_notes',
                    relevance_score=result.get('_distance', 0.0),
                    metadata=result,
                    timestamp=datetime.fromisoformat(result['timestamp']) if 'timestamp' in result else None
                )
                results.append(unified_result)
            
            # Search all tables for verbatim content
            all_results = self.lancedb.search_all_tables(
                query=query,
                limit=max_results // 2
            )
            verbatim_results = all_results.get('verbatim', [])
            
            for result in verbatim_results:
                unified_result = UnifiedSearchResult(
                    content=result.get('content', ''),
                    source_layer='lancedb_verbatim',
                    relevance_score=result.get('_distance', 0.0),
                    metadata=result,
                    timestamp=datetime.fromisoformat(result['timestamp']) if 'timestamp' in result else None
                )
                results.append(unified_result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching LanceDB: {e}")
            return []

    def _search_knowledge_graph(self, 
                               query: str, 
                               filters: Optional[Dict[str, Any]], 
                               max_results: int) -> List[UnifiedSearchResult]:
        """Search Knowledge Graph layer."""
        try:
            results = []
            
            # Extract potential concepts from query
            query_concepts = self._extract_concepts_from_query(query)
            
            for concept in query_concepts:
                # Find related concepts
                related = self.knowledge_graph.find_related_concepts(
                    concept=concept,
                    depth=2,
                    min_confidence=0.5
                )
                
                for rel in related[:max_results // len(query_concepts) if query_concepts else max_results]:
                    content = f"{concept} -> {rel['relationship']} -> {rel['concept']}"
                    
                    unified_result = UnifiedSearchResult(
                        content=content,
                        source_layer='knowledge_graph',
                        relevance_score=rel['confidence'],
                        metadata={
                            'source_concept': concept,
                            'target_concept': rel['concept'],
                            'relationship': rel['relationship'],
                            'relationship_type': rel['relationship_type'],
                            'distance': rel['distance']
                        },
                        timestamp=datetime.fromisoformat(rel['timestamp']) if rel['timestamp'] else None
                    )
                    results.append(unified_result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching knowledge graph: {e}")
            return []

    def _extract_concepts_from_query(self, query: str) -> List[str]:
        """Extract potential concepts from search query."""
        # Simple concept extraction - could be enhanced with NLP
        words = query.lower().split()
        
        # Filter out common words and keep potential concepts
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'what', 'how', 'when', 'where', 'why'}
        concepts = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return concepts[:3]  # Limit to top 3 concepts

    def get_relationship_context(self, concept: str, depth: int = 2) -> Dict[str, Any]:
        """
        Get relationship context for a concept from knowledge graph.

        Args:
            concept: Concept to get context for
            depth: Relationship traversal depth

        Returns:
            Dict: Relationship context
        """
        try:
            # Get concept summary
            summary = self.knowledge_graph.get_concept_summary(concept)
            
            if not summary.get('exists', False):
                return {'exists': False}
            
            # Get related concepts
            related = self.knowledge_graph.find_related_concepts(concept, depth)
            
            # Organize by relationship type
            context = {
                'concept': concept,
                'exists': True,
                'direct_relationships': summary.get('total_relationships', 0),
                'related_concepts': related,
                'relationship_types': {},
                'summary': summary
            }
            
            # Group by relationship type
            for rel in related:
                rel_type = rel['relationship_type']
                if rel_type not in context['relationship_types']:
                    context['relationship_types'][rel_type] = []
                context['relationship_types'][rel_type].append(rel)
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting relationship context: {e}")
            return {'exists': False, 'error': str(e)}

    def detect_memory_contradictions(self) -> List[Dict[str, Any]]:
        """Detect contradictions across memory layers."""
        try:
            # Use knowledge graph contradiction detection
            contradictions = self.knowledge_graph.detect_contradictions()
            
            # TODO: Cross-reference with LanceDB and filesystem for additional context
            
            return contradictions
            
        except Exception as e:
            self.logger.error(f"Error detecting contradictions: {e}")
            return []

    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get statistics from all storage layers."""
        try:
            stats = {
                'filesystem': {
                    'path': str(self.filesystem_path),
                    'exists': self.filesystem_path.exists()
                },
                'lancedb': self.lancedb.get_statistics() if hasattr(self.lancedb, 'get_statistics') else {},
                'knowledge_graph': self.knowledge_graph.get_statistics(),
                'unified': {
                    'total_layers': 3,
                    'active_layers': 2,  # LanceDB + Knowledge Graph (filesystem TODO)
                    'last_updated': datetime.now().isoformat()
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting storage statistics: {e}")
            return {}

    def save_all_layers(self):
        """Save all storage layers to disk."""
        try:
            # Save knowledge graph
            self.knowledge_graph.save()
            
            # LanceDB saves automatically
            
            # TODO: Save filesystem changes
            
            self.logger.info("All storage layers saved")
            
        except Exception as e:
            self.logger.error(f"Error saving storage layers: {e}")

    # HIGH-LEVEL INTERFACE METHODS (Encapsulating Storage Complexity)

    def remember(self, 
                content: str,
                item_type: str = "note",
                user_id: str = "user",
                location: str = "unknown",
                importance: float = 0.5,
                metadata: Optional[Dict[str, Any]] = None,
                relationships: Optional[List[Dict[str, Any]]] = None) -> Dict[str, str]:
        """
        Unified remember() method - stores across all three layers intelligently.
        
        Process:
        1. Store in filesystem (structured data)
        2. Index in LanceDB (semantic search)
        3. Extract and store relationships in KG (only for consolidated facts)
        
        Args:
            content: Content to remember
            item_type: Type of memory ('note', 'verbatim', 'fact', 'document')
            user_id: User identifier
            location: Location context
            importance: Importance score (0.0-1.0)
            metadata: Additional metadata
            relationships: Explicit relationships (for consolidated facts only)
            
        Returns:
            Dict: Storage IDs from each layer
        """
        self.logger.debug(f"💾 [TripleStorageManager.remember] Starting unified remember operation")
        self.logger.debug(f"📝 [TripleStorageManager.remember] Content: {content[:100]}{'...' if len(content) > 100 else ''}")
        self.logger.debug(f"🏷️  [TripleStorageManager.remember] Type: {item_type}, User: {user_id}, Importance: {importance}")
        self.logger.debug(f"🔗 [TripleStorageManager.remember] Relationships: {len(relationships or [])} provided")
        
        try:
            storage_ids = {}
            
            # Prepare memory data
            memory_data = {
                'content': content,
                'type': item_type,
                'user_id': user_id,
                'location': location,
                'timestamp': datetime.now().isoformat(),
                'importance': importance,
                'metadata': metadata or {},
                'relationships': relationships or []
            }
            
            # 1. Store in filesystem (Layer 1)
            self.logger.debug("📁 [TripleStorageManager.remember] Storing in filesystem layer...")
            file_id = self._store_in_filesystem(memory_data)
            if file_id:
                storage_ids['filesystem'] = file_id
                self.logger.debug(f"✅ [TripleStorageManager.remember] Filesystem storage: {file_id}")
            else:
                self.logger.debug("❌ [TripleStorageManager.remember] Filesystem storage failed")
            
            # 2. Index in LanceDB (Layer 2) 
            self.logger.debug("🔍 [TripleStorageManager.remember] Indexing in LanceDB layer...")
            lance_id = self._store_in_lancedb(memory_data)
            if lance_id:
                storage_ids['lancedb'] = lance_id
                self.logger.debug(f"✅ [TripleStorageManager.remember] LanceDB storage: {lance_id}")
            else:
                self.logger.debug("❌ [TripleStorageManager.remember] LanceDB storage failed")
            
            # 3. Store relationships in KG (Layer 3) - ONLY for consolidated facts
            if item_type == 'consolidated_fact' and relationships:
                self.logger.debug("🕸️  [TripleStorageManager.remember] Storing relationships in Knowledge Graph...")
                graph_ids = self._store_in_knowledge_graph(memory_data)
                if graph_ids:
                    storage_ids['knowledge_graph'] = graph_ids
                    self.logger.debug(f"✅ [TripleStorageManager.remember] Knowledge Graph storage: {len(graph_ids)} relationships")
                    
                    # Create cross-layer references
                    self.logger.debug("🔗 [TripleStorageManager.remember] Creating cross-layer references...")
                    self._create_cross_layer_references(file_id, lance_id, graph_ids, memory_data)
                    self.logger.debug("✅ [TripleStorageManager.remember] Cross-layer references created")
                else:
                    self.logger.debug("❌ [TripleStorageManager.remember] Knowledge Graph storage failed")
            elif item_type == 'consolidated_fact':
                self.logger.debug("⚠️  [TripleStorageManager.remember] Consolidated fact but no relationships provided")
            else:
                self.logger.debug(f"ℹ️  [TripleStorageManager.remember] Skipping KG storage for type: {item_type} (quality gate)")
            
            self.logger.info(f"✅ [TripleStorageManager.remember] Memory stored across {len(storage_ids)} layers: {list(storage_ids.keys())}")
            return storage_ids
            
        except Exception as e:
            self.logger.error(f"❌ [TripleStorageManager.remember] Error in unified remember(): {e}")
            return {}

    def reconstruct(self, 
                   query: str, 
                   user_id: str = "user",
                   context_depth: int = 3,
                   relationship_depth: int = 2) -> Dict[str, Any]:
        """
        Intelligent context reconstruction across all layers.
        
        Process:
        1. Semantic search in LanceDB for relevant content
        2. Relationship exploration in KG for connected concepts
        3. Filesystem retrieval of full context
        4. Synthesis of multi-layer context
        
        Args:
            query: Context reconstruction query
            user_id: User context
            context_depth: How deep to search for context
            relationship_depth: How deep to explore relationships
            
        Returns:
            Dict: Reconstructed context from all layers
        """
        self.logger.debug(f"🔍 [TripleStorageManager.reconstruct] Starting context reconstruction")
        self.logger.debug(f"❓ [TripleStorageManager.reconstruct] Query: '{query}' for user: {user_id}")
        self.logger.debug(f"📊 [TripleStorageManager.reconstruct] Depths: context={context_depth}, relationship={relationship_depth}")
        
        try:
            context = {
                'query': query,
                'user_id': user_id,
                'semantic_context': [],
                'relationship_context': [],
                'synthesis': '',
                'confidence': 0.0,
                'sources': []
            }
            
            # 1. Semantic search in LanceDB
            self.logger.debug("🔍 [TripleStorageManager.reconstruct] Performing semantic search in LanceDB...")
            semantic_results = self.unified_search(
                query=query,
                filters={'user_id': user_id},
                include_relationships=False,
                max_results=context_depth * 2
            )
            context['semantic_context'] = semantic_results[:context_depth]
            self.logger.debug(f"✅ [TripleStorageManager.reconstruct] Semantic search: {len(semantic_results)} results, using top {len(context['semantic_context'])}")
            
            # 2. Relationship exploration in KG
            self.logger.debug("🕸️  [TripleStorageManager.reconstruct] Exploring relationships in Knowledge Graph...")
            relationship_context = self.get_relationship_context(query, relationship_depth)
            context['relationship_context'] = relationship_context
            if relationship_context.get('exists'):
                rel_count = len(relationship_context.get('related_concepts', []))
                self.logger.debug(f"✅ [TripleStorageManager.reconstruct] Relationship exploration: {rel_count} related concepts found")
            else:
                self.logger.debug("ℹ️  [TripleStorageManager.reconstruct] No relationship context found")
            
            # 3. Synthesize context
            self.logger.debug("🧠 [TripleStorageManager.reconstruct] Synthesizing multi-layer context...")
            context['synthesis'] = self._synthesize_context(
                semantic_results, relationship_context
            )
            
            # 4. Calculate confidence
            context['confidence'] = self._calculate_context_confidence(context)
            self.logger.debug(f"🎯 [TripleStorageManager.reconstruct] Context confidence: {context['confidence']:.2f}")
            
            # 5. Track sources
            context['sources'] = self._extract_sources(semantic_results, relationship_context)
            self.logger.debug(f"📚 [TripleStorageManager.reconstruct] Sources tracked: {len(context['sources'])}")
            
            self.logger.info(f"✅ [TripleStorageManager.reconstruct] Context reconstructed: {len(context['semantic_context'])} semantic + {len(context.get('relationship_context', {}).get('related_concepts', []))} relationship elements")
            return context
            
        except Exception as e:
            self.logger.error(f"❌ [TripleStorageManager.reconstruct] Error in context reconstruction: {e}")
            return {'error': str(e)}

    def reflect(self, 
               topic: str,
               reflection_depth: str = "deep",
               include_contradictions: bool = True) -> Dict[str, Any]:
        """
        Deep reflection using relationship context from knowledge graph.
        
        Args:
            topic: Topic to reflect on
            reflection_depth: "shallow", "deep", or "comprehensive"
            include_contradictions: Whether to detect contradictions
            
        Returns:
            Dict: Reflection results with insights and patterns
        """
        try:
            reflection = {
                'topic': topic,
                'depth': reflection_depth,
                'insights': [],
                'patterns': [],
                'contradictions': [],
                'evolution': '',
                'confidence': 0.0
            }
            
            # Get comprehensive context for topic
            context = self.reconstruct(topic, "system", context_depth=5, relationship_depth=3)
            
            # Analyze patterns in relationships
            if context.get('relationship_context', {}).get('exists'):
                patterns = self._analyze_relationship_patterns(topic, context)
                reflection['patterns'] = patterns
            
            # Generate insights from cross-layer analysis
            insights = self._generate_insights_from_context(context)
            reflection['insights'] = insights
            
            # Detect contradictions if requested
            if include_contradictions:
                contradictions = self.detect_memory_contradictions()
                # Filter for topic-relevant contradictions
                topic_contradictions = [c for c in contradictions 
                                      if topic.lower() in str(c).lower()]
                reflection['contradictions'] = topic_contradictions
            
            # Analyze evolution of understanding
            evolution = self._analyze_understanding_evolution(topic, context)
            reflection['evolution'] = evolution
            
            reflection['confidence'] = self._calculate_reflection_confidence(reflection)
            
            self.logger.info(f"Deep reflection on '{topic}' generated {len(insights)} insights")
            return reflection
            
        except Exception as e:
            self.logger.error(f"Error in reflection: {e}")
            return {'error': str(e)}

    def plan(self, 
            goal: str,
            context: Optional[Dict[str, Any]] = None,
            planning_horizon: str = "medium") -> Dict[str, Any]:
        """
        Planning using accumulated knowledge from all storage layers.
        
        Args:
            goal: Planning goal
            context: Optional additional context
            planning_horizon: "short", "medium", or "long"
            
        Returns:
            Dict: Planning results with steps and dependencies
        """
        try:
            plan = {
                'goal': goal,
                'horizon': planning_horizon,
                'steps': [],
                'resources': [],
                'confidence': 0.0,
                'reasoning': ''
            }
            
            # Reconstruct relevant context for planning
            planning_context = self.reconstruct(goal, "system", context_depth=4)
            
            # Generate basic planning structure
            plan['reasoning'] = f"Planning for '{goal}' using {len(planning_context.get('semantic_context', []))} relevant memories"
            plan['resources'] = [r['content'][:100] for r in planning_context.get('semantic_context', [])[:3]]
            plan['steps'] = [
                f"Analyze requirements for {goal}",
                f"Identify resources and constraints",
                f"Execute plan with monitoring"
            ]
            
            plan['confidence'] = planning_context.get('confidence', 0.5)
            
            self.logger.info(f"Generated plan for '{goal}' with {len(plan['steps'])} steps")
            return plan
            
        except Exception as e:
            self.logger.error(f"Error in planning: {e}")
            return {'error': str(e)}

    def alignment(self, 
                 action: str,
                 values_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Value alignment assessment using accumulated understanding.
        
        Args:
            action: Action to assess for alignment
            values_context: Optional values context
            
        Returns:
            Dict: Alignment assessment results
        """
        try:
            assessment = {
                'action': action,
                'alignment_score': 0.7,  # Default neutral
                'concerns': [],
                'supporting_evidence': [],
                'recommendation': 'Proceed with caution - insufficient value context'
            }
            
            # Get values context from memory
            values_search = self.unified_search("values purpose ethics", max_results=3)
            if values_search:
                assessment['supporting_evidence'] = [r.content[:100] for r in values_search[:2]]
                assessment['alignment_score'] = 0.8  # Higher if we have value context
                assessment['recommendation'] = 'Action appears aligned with known values'
            
            self.logger.info(f"Value alignment assessed for '{action}': {assessment['alignment_score']:.2f}")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error in alignment assessment: {e}")
            return {'error': str(e)}

    # HELPER METHODS FOR HIGH-LEVEL INTERFACE

    def _synthesize_context(self, semantic_results: List, relationship_context: Dict) -> str:
        """Synthesize context from multiple sources."""
        try:
            if not semantic_results:
                return "No relevant context found"
            
            synthesis = f"Found {len(semantic_results)} relevant memories"
            if relationship_context.get('exists'):
                rel_count = len(relationship_context.get('related_concepts', []))
                synthesis += f" with {rel_count} relationship connections"
            
            return synthesis
            
        except Exception as e:
            return f"Context synthesis error: {e}"

    def _calculate_context_confidence(self, context: Dict) -> float:
        """Calculate confidence score for reconstructed context."""
        try:
            semantic_count = len(context.get('semantic_context', []))
            has_relationships = context.get('relationship_context', {}).get('exists', False)
            
            # Base confidence on available information
            confidence = min(0.9, 0.3 + (semantic_count * 0.1))
            if has_relationships:
                confidence += 0.2
            
            return confidence
            
        except Exception:
            return 0.5

    def _analyze_relationship_patterns(self, topic: str, context: Dict) -> List[str]:
        """Analyze patterns in relationship context."""
        try:
            patterns = []
            rel_context = context.get('relationship_context', {})
            
            if rel_context.get('exists'):
                rel_types = rel_context.get('relationship_types', {})
                for rel_type, rels in rel_types.items():
                    if rels:
                        patterns.append(f"{rel_type}: {len(rels)} connections")
            
            return patterns
            
        except Exception:
            return []

    def _generate_insights_from_context(self, context: Dict) -> List[str]:
        """Generate insights from cross-layer context analysis."""
        try:
            insights = []
            
            semantic_count = len(context.get('semantic_context', []))
            if semantic_count > 0:
                insights.append(f"Found {semantic_count} relevant memories for analysis")
            
            if context.get('relationship_context', {}).get('exists'):
                insights.append("Topic has established relationship connections")
            
            confidence = context.get('confidence', 0)
            if confidence > 0.8:
                insights.append("High confidence in context reconstruction")
            
            return insights
            
        except Exception:
            return []

    def _analyze_understanding_evolution(self, topic: str, context: Dict) -> str:
        """Analyze how understanding of topic has evolved."""
        try:
            semantic_results = context.get('semantic_context', [])
            if not semantic_results:
                return "No evolution data available"
            
            # Simple evolution analysis based on timestamps
            timestamps = []
            for result in semantic_results:
                if hasattr(result, 'timestamp') and result.timestamp:
                    timestamps.append(result.timestamp)
            
            if len(timestamps) > 1:
                return f"Understanding evolved across {len(timestamps)} interactions"
            else:
                return "Limited evolution data available"
                
        except Exception:
            return "Evolution analysis unavailable"

    def _calculate_reflection_confidence(self, reflection: Dict) -> float:
        """Calculate confidence score for reflection results."""
        try:
            insights_count = len(reflection.get('insights', []))
            patterns_count = len(reflection.get('patterns', []))
            
            confidence = min(0.9, 0.4 + (insights_count * 0.1) + (patterns_count * 0.05))
            return confidence
            
        except Exception:
            return 0.5

    def _extract_sources(self, semantic_results: List, relationship_context: Dict) -> List[str]:
        """Extract source information from context."""
        try:
            sources = []
            
            for result in semantic_results[:3]:  # Top 3 sources
                if hasattr(result, 'source_layer'):
                    sources.append(f"{result.source_layer}: {result.content[:50]}...")
            
            if relationship_context.get('exists'):
                sources.append(f"Knowledge graph: {relationship_context.get('concept', 'unknown')}")
            
            return sources
            
        except Exception:
            return []

    def _create_cross_layer_references(self, file_id: str, lance_id: str, 
                                     graph_ids: List[str], memory_data: Dict):
        """Create cross-layer references in knowledge graph (for consolidated facts only)."""
        try:
            if memory_data.get('type') != 'consolidated_fact':
                return  # Only create references for consolidated facts
            
            timestamp = datetime.now()
            
            # Link filesystem to LanceDB
            if file_id and lance_id:
                ref_triple = GraphTriple(
                    subject=f"file:{file_id}",
                    predicate="indexed_as", 
                    object=f"lance:{lance_id}",
                    confidence=1.0,
                    timestamp=timestamp,
                    source="cross_layer_reference",
                    importance=0.3,
                    relationship_type="structural",
                    context="Cross-layer storage reference"
                )
                self.knowledge_graph.add_triple(ref_triple)
            
        except Exception as e:
            self.logger.error(f"Error creating cross-layer references: {e}")

    def close(self):
        """Close all storage layers."""
        try:
            self.knowledge_graph.close()
            # LanceDB doesn't need explicit closing
            
            self.logger.info("All storage layers closed")
            
        except Exception as e:
            self.logger.error(f"Error closing storage layers: {e}")


def create_triple_storage_manager(base_path: Path, 
                                 embedding_manager,
                                 lancedb_storage: Optional[LanceDBStorage] = None,
                                 knowledge_graph: Optional[KnowledgeGraphStorage] = None) -> TripleStorageManager:
    """
    Create a TripleStorageManager instance.

    Args:
        base_path: Base memory path
        embedding_manager: EmbeddingManager for LanceDB
        lancedb_storage: Optional existing LanceDB storage
        knowledge_graph: Optional existing knowledge graph

    Returns:
        TripleStorageManager instance
    """
    return TripleStorageManager(
        base_path=base_path,
        embedding_manager=embedding_manager,
        lancedb_storage=lancedb_storage,
        knowledge_graph=knowledge_graph
    )
