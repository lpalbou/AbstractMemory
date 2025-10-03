"""
Dynamic context injector for intelligent memory retrieval and injection.

Provides smart filtering and prioritization of memories from all indexed modules
based on multiple relevance factors.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ContextRelevance:
    """Tracks relevance scores for a memory item."""
    semantic_score: float = 0.0  # Similarity to query (0-1)
    temporal_score: float = 0.0  # Time-based relevance (0-1)
    location_score: float = 0.0  # Location relevance (0-1)
    emotion_score: float = 0.0   # Emotional resonance (0-1)
    importance_score: float = 0.0  # Inherent importance (0-1)

    @property
    def total_score(self) -> float:
        """Calculate weighted total score."""
        weights = {
            'semantic': 0.35,
            'temporal': 0.20,
            'location': 0.10,
            'emotion': 0.20,
            'importance': 0.15
        }

        return (
            self.semantic_score * weights['semantic'] +
            self.temporal_score * weights['temporal'] +
            self.location_score * weights['location'] +
            self.emotion_score * weights['emotion'] +
            self.importance_score * weights['importance']
        )


class DynamicContextInjector:
    """Manages dynamic context injection from indexed memory modules."""

    def __init__(
        self,
        memory_base_path: Path,
        lancedb_storage,
        index_config,
        memory_indexer
    ):
        """
        Initialize the dynamic context injector.

        Args:
            memory_base_path: Base path for memory storage
            lancedb_storage: LanceDB storage instance
            index_config: Memory index configuration
            memory_indexer: Memory indexer instance
        """
        self.memory_base_path = Path(memory_base_path)
        self.lancedb = lancedb_storage
        self.index_config = index_config
        self.memory_indexer = memory_indexer

        # Token budget per module (configurable)
        self.token_budgets = {
            'notes': 500,
            'verbatim': 300,
            'library': 400,
            'core': 300,
            'working': 200,
            'episodic': 400,
            'semantic': 400,
            'people': 200,
            'links': 100
        }

        # Total token budget for context
        self.max_context_tokens = 2000

    def inject_context(
        self,
        query: str,
        user_id: str,
        location: str = "unknown",
        focus_level: int = 3,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Dynamically inject context from all enabled memory modules.

        Args:
            query: User query for semantic search
            user_id: User identifier
            location: Current location context
            focus_level: Depth of context retrieval (0-5)
            timestamp: Current timestamp (default: now)

        Returns:
            Dictionary with injected context from all modules
        """
        if timestamp is None:
            timestamp = datetime.now()

        context = {
            'timestamp': timestamp.isoformat(),
            'user_id': user_id,
            'location': location,
            'query': query,
            'focus_level': focus_level,
            'modules': {},
            'total_memories': 0,
            'token_estimate': 0
        }

        # Get enabled modules from config
        enabled_modules = self.index_config.get_enabled_modules()

        # Retrieve and rank memories from each module
        for module in enabled_modules:
            if not self.index_config.dynamic_injection_enabled:
                continue

            try:
                module_context = self._retrieve_module_context(
                    module=module,
                    query=query,
                    user_id=user_id,
                    location=location,
                    timestamp=timestamp,
                    focus_level=focus_level
                )

                if module_context['memories']:
                    context['modules'][module] = module_context
                    context['total_memories'] += len(module_context['memories'])
                    context['token_estimate'] += module_context['token_estimate']

            except Exception as e:
                logger.error(f"Failed to retrieve context from {module}: {e}")

        # Apply global token budget
        context = self._apply_token_budget(context)

        # Generate synthesis
        context['synthesis'] = self._synthesize_context(context)

        return context

    def _retrieve_module_context(
        self,
        module: str,
        query: str,
        user_id: str,
        location: str,
        timestamp: datetime,
        focus_level: int
    ) -> Dict[str, Any]:
        """
        Retrieve context from a specific memory module.

        Args:
            module: Name of the memory module
            query: Search query
            user_id: User identifier
            location: Current location
            timestamp: Current timestamp
            focus_level: Retrieval depth

        Returns:
            Module-specific context dictionary
        """
        # Adjust retrieval limit based on focus level
        base_limit = 5
        limit = base_limit + (focus_level * 2)  # 5, 7, 9, 11, 13, 15

        module_context = {
            'module': module,
            'memories': [],
            'token_estimate': 0,
            'relevance_scores': []
        }

        # Module-specific retrieval strategies
        if module == 'notes':
            memories = self._retrieve_notes(query, user_id, timestamp, limit)
        elif module == 'verbatim':
            memories = self._retrieve_verbatim(query, user_id, timestamp, limit)
        elif module == 'library':
            memories = self._retrieve_library(query, limit)
        elif module == 'core':
            memories = self._retrieve_core_memory(focus_level)
        elif module == 'working':
            memories = self._retrieve_working_memory(query, limit)
        elif module == 'episodic':
            memories = self._retrieve_episodic(query, timestamp, limit)
        elif module == 'semantic':
            memories = self._retrieve_semantic(query, limit)
        elif module == 'people':
            memories = self._retrieve_people(user_id, query, limit)
        elif module == 'links':
            # Links are handled differently (used to expand other memories)
            return module_context
        else:
            return module_context

        # Score and rank memories
        scored_memories = []
        for memory in memories:
            relevance = self._calculate_relevance(
                memory=memory,
                query=query,
                user_id=user_id,
                location=location,
                timestamp=timestamp,
                module=module
            )
            scored_memories.append((memory, relevance))

        # Sort by total relevance score
        scored_memories.sort(key=lambda x: x[1].total_score, reverse=True)

        # Apply module token budget
        budget = self.token_budgets.get(module, 300)
        current_tokens = 0

        for memory, relevance in scored_memories:
            # Estimate tokens (rough: 1 token per 4 chars)
            memory_tokens = len(str(memory.get('content', ''))) // 4

            if current_tokens + memory_tokens > budget:
                break

            module_context['memories'].append(memory)
            module_context['relevance_scores'].append(relevance)
            current_tokens += memory_tokens

        module_context['token_estimate'] = current_tokens

        return module_context

    def _retrieve_notes(
        self,
        query: str,
        user_id: str,
        timestamp: datetime,
        limit: int
    ) -> List[Dict]:
        """Retrieve experiential notes."""
        if not self.lancedb:
            return []

        filters = {
            'user_id': user_id,
            'since': timestamp - timedelta(days=7),  # Last week
            'min_importance': 0.3
        }

        return self.lancedb.search_notes(query, filters, limit)

    def _retrieve_verbatim(
        self,
        query: str,
        user_id: str,
        timestamp: datetime,
        limit: int
    ) -> List[Dict]:
        """Retrieve verbatim conversations if indexed."""
        if not self.lancedb or 'verbatim' not in self.lancedb.db.table_names():
            return []

        # Search verbatim table
        try:
            results = self.lancedb.search_all_tables(
                query=query,
                tables=['verbatim'],
                limit=limit
            )
            return results.get('verbatim', [])
        except:
            return []

    def _retrieve_library(self, query: str, limit: int) -> List[Dict]:
        """Retrieve library documents."""
        if not self.lancedb:
            return []

        return self.lancedb.search_library(query, limit)

    def _retrieve_core_memory(self, focus_level: int) -> List[Dict]:
        """Retrieve core memory components based on focus level."""
        core_path = self.memory_base_path / 'core'
        if not core_path.exists():
            return []

        memories = []

        # Always include purpose and values
        essential_components = ['purpose.md', 'values.md']

        # Add more components at higher focus levels
        if focus_level >= 3:
            essential_components.extend(['personality.md', 'goals.md'])
        if focus_level >= 4:
            essential_components.extend(['expertise.md', 'knowledge.md'])
        if focus_level >= 5:
            essential_components.extend(['identity.md', 'capabilities.md', 'constraints.md', 'growth_edges.md'])

        for component_file in essential_components:
            file_path = core_path / component_file
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    memories.append({
                        'id': f"core_{component_file.replace('.md', '')}",
                        'component': component_file.replace('.md', ''),
                        'content': content[:500],  # Truncate for context
                        'type': 'core_memory'
                    })
                except:
                    continue

        return memories

    def _retrieve_working_memory(self, query: str, limit: int) -> List[Dict]:
        """Retrieve working memory (current context, tasks)."""
        if not self.lancedb or 'working_memory' not in self.lancedb.db.table_names():
            # Fallback to filesystem
            working_path = self.memory_base_path / 'working'
            if not working_path.exists():
                return []

            memories = []
            for file_name in ['current_context.md', 'active_tasks.md', 'unresolved.md']:
                file_path = working_path / file_name
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        if content.strip():
                            memories.append({
                                'id': f"working_{file_name.replace('.md', '')}",
                                'type': file_name.replace('.md', ''),
                                'content': content[:500],
                                'active': file_name != 'resolved.md'
                            })
                    except:
                        continue
            return memories

        # Use LanceDB if available
        results = self.lancedb.search_all_tables(
            query=query,
            tables=['working_memory'],
            limit=limit
        )
        return results.get('working_memory', [])

    def _retrieve_episodic(
        self,
        query: str,
        timestamp: datetime,
        limit: int
    ) -> List[Dict]:
        """Retrieve episodic memories (key moments)."""
        if not self.lancedb or 'episodic_memory' not in self.lancedb.db.table_names():
            # Fallback to filesystem
            episodic_path = self.memory_base_path / 'episodic'
            if not episodic_path.exists():
                return []

            memories = []
            key_moments_file = episodic_path / 'key_moments.md'
            if key_moments_file.exists():
                try:
                    content = key_moments_file.read_text(encoding='utf-8')
                    # Parse key moments (simple extraction)
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().startswith('##'):
                            title = line.replace('#', '').strip()
                            # Get content until next header or end
                            moment_content = []
                            for j in range(i+1, min(i+10, len(lines))):
                                if lines[j].startswith('##'):
                                    break
                                moment_content.append(lines[j])

                            memories.append({
                                'id': f"episodic_moment_{i}",
                                'type': 'key_moment',
                                'title': title,
                                'content': '\n'.join(moment_content)[:500]
                            })
                except:
                    pass

            return memories[:limit]

        # Use LanceDB if available
        results = self.lancedb.search_all_tables(
            query=query,
            tables=['episodic_memory'],
            limit=limit
        )
        return results.get('episodic_memory', [])

    def _retrieve_semantic(self, query: str, limit: int) -> List[Dict]:
        """Retrieve semantic memories (insights, concepts)."""
        if not self.lancedb or 'semantic_memory' not in self.lancedb.db.table_names():
            # Fallback to filesystem
            semantic_path = self.memory_base_path / 'semantic'
            if not semantic_path.exists():
                return []

            memories = []

            # Load insights
            insights_file = semantic_path / 'insights.md'
            if insights_file.exists():
                try:
                    content = insights_file.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    for line in lines[:limit//2]:  # Half the limit for insights
                        if line.strip().startswith('-') or line.strip().startswith('*'):
                            memories.append({
                                'id': f"semantic_insight_{len(memories)}",
                                'type': 'insight',
                                'content': line.strip()[1:].strip()
                            })
                except:
                    pass

            # Load concepts
            concepts_file = semantic_path / 'concepts.md'
            if concepts_file.exists():
                try:
                    content = concepts_file.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    for line in lines[:limit//2]:  # Half the limit for concepts
                        if line.strip().startswith('-') or line.strip().startswith('*'):
                            memories.append({
                                'id': f"semantic_concept_{len(memories)}",
                                'type': 'concept',
                                'content': line.strip()[1:].strip()
                            })
                except:
                    pass

            return memories

        # Use LanceDB if available
        results = self.lancedb.search_all_tables(
            query=query,
            tables=['semantic_memory'],
            limit=limit
        )
        return results.get('semantic_memory', [])

    def _retrieve_people(self, user_id: str, query: str, limit: int) -> List[Dict]:
        """Retrieve user profiles and preferences."""
        if not self.lancedb or 'people' not in self.lancedb.db.table_names():
            # Fallback to filesystem
            people_path = self.memory_base_path / 'people' / user_id
            if not people_path.exists():
                return []

            memories = []

            # Load profile
            profile_file = people_path / 'profile.md'
            if profile_file.exists():
                try:
                    content = profile_file.read_text(encoding='utf-8')
                    memories.append({
                        'id': f"people_{user_id}_profile",
                        'type': 'profile',
                        'user_id': user_id,
                        'content': content[:500]
                    })
                except:
                    pass

            # Load preferences
            prefs_file = people_path / 'preferences.md'
            if prefs_file.exists():
                try:
                    content = prefs_file.read_text(encoding='utf-8')
                    memories.append({
                        'id': f"people_{user_id}_preferences",
                        'type': 'preferences',
                        'user_id': user_id,
                        'content': content[:500]
                    })
                except:
                    pass

            return memories

        # Use LanceDB if available
        results = self.lancedb.search_all_tables(
            query=query,
            tables=['people'],
            limit=limit
        )
        return [m for m in results.get('people', []) if m.get('user_id') == user_id]

    def _calculate_relevance(
        self,
        memory: Dict,
        query: str,
        user_id: str,
        location: str,
        timestamp: datetime,
        module: str
    ) -> ContextRelevance:
        """
        Calculate multi-dimensional relevance score for a memory.

        Args:
            memory: Memory item
            query: Search query
            user_id: User identifier
            location: Current location
            timestamp: Current timestamp
            module: Source module

        Returns:
            ContextRelevance with computed scores
        """
        relevance = ContextRelevance()

        # Semantic score (already computed by LanceDB search)
        relevance.semantic_score = memory.get('_distance', 0.5)  # LanceDB similarity

        # Temporal score (recency)
        if 'timestamp' in memory:
            try:
                mem_time = datetime.fromisoformat(memory['timestamp'])
                time_diff = (timestamp - mem_time).total_seconds()
                # Decay function: more recent = higher score
                hours_ago = time_diff / 3600
                relevance.temporal_score = max(0, 1.0 - (hours_ago / 168))  # 1 week decay
            except:
                relevance.temporal_score = 0.3

        # Location score
        if 'location' in memory and memory['location'] == location:
            relevance.location_score = 1.0
        else:
            relevance.location_score = 0.0

        # Emotion score
        emotion_intensity = memory.get('emotion_intensity', 0.5)
        relevance.emotion_score = emotion_intensity

        # Importance score
        relevance.importance_score = memory.get('importance', 0.5)

        # Module-specific adjustments
        if module == 'core':
            relevance.importance_score = 0.9  # Core memories always important
        elif module == 'working':
            relevance.temporal_score = 1.0  # Working memory is current
        elif module == 'library':
            relevance.importance_score = memory.get('importance_score', 0.5)

        return relevance

    def _apply_token_budget(self, context: Dict) -> Dict:
        """
        Apply global token budget to context.

        Args:
            context: Full context dictionary

        Returns:
            Context with token budget applied
        """
        if context['token_estimate'] <= self.max_context_tokens:
            return context

        # Need to trim - prioritize by module importance
        module_priorities = {
            'core': 1.0,
            'working': 0.9,
            'notes': 0.8,
            'episodic': 0.7,
            'semantic': 0.7,
            'library': 0.6,
            'people': 0.5,
            'verbatim': 0.4,
            'links': 0.3
        }

        # Sort modules by priority
        sorted_modules = sorted(
            context['modules'].keys(),
            key=lambda m: module_priorities.get(m, 0.5),
            reverse=True
        )

        # Rebuild context with budget
        trimmed_context = {
            **context,
            'modules': {},
            'total_memories': 0,
            'token_estimate': 0
        }

        current_tokens = 0
        for module in sorted_modules:
            module_data = context['modules'][module]
            module_budget = min(
                self.token_budgets.get(module, 300),
                self.max_context_tokens - current_tokens
            )

            if module_budget <= 0:
                break

            # Trim memories to fit budget
            trimmed_memories = []
            module_tokens = 0

            for memory in module_data['memories']:
                mem_tokens = len(str(memory.get('content', ''))) // 4
                if module_tokens + mem_tokens <= module_budget:
                    trimmed_memories.append(memory)
                    module_tokens += mem_tokens
                else:
                    break

            if trimmed_memories:
                trimmed_context['modules'][module] = {
                    **module_data,
                    'memories': trimmed_memories,
                    'token_estimate': module_tokens
                }
                trimmed_context['total_memories'] += len(trimmed_memories)
                current_tokens += module_tokens

        trimmed_context['token_estimate'] = current_tokens
        return trimmed_context

    def _synthesize_context(self, context: Dict) -> str:
        """
        Synthesize context into a coherent string for LLM injection.

        Args:
            context: Full context dictionary

        Returns:
            Synthesized context string
        """
        parts = []

        # Header
        parts.append(f"[Context Reconstruction]")
        parts.append(f"Time: {context['timestamp']}")
        parts.append(f"User: {context['user_id']}")
        parts.append(f"Location: {context['location']}")
        parts.append(f"Focus Level: {context['focus_level']}")
        parts.append(f"Total Memories: {context['total_memories']}")
        parts.append("")

        # Module-specific contexts
        for module_name, module_data in context['modules'].items():
            if not module_data['memories']:
                continue

            parts.append(f"[{module_name.title()} Memory]")

            for memory in module_data['memories'][:5]:  # Limit per module
                if module_name == 'core':
                    parts.append(f"- {memory.get('component', 'unknown')}: {memory.get('content', '')[:200]}")
                elif module_name == 'notes':
                    parts.append(f"- [{memory.get('id', '')}] {memory.get('content', '')[:200]}")
                elif module_name == 'library':
                    parts.append(f"- Document: {memory.get('source_path', 'unknown')} - {memory.get('content_excerpt', '')[:150]}")
                elif module_name == 'episodic':
                    parts.append(f"- {memory.get('title', 'Moment')}: {memory.get('content', '')[:150]}")
                elif module_name == 'semantic':
                    parts.append(f"- {memory.get('type', 'insight')}: {memory.get('content', '')[:150]}")
                elif module_name == 'people':
                    parts.append(f"- {memory.get('type', 'info')}: {memory.get('content', '')[:150]}")
                elif module_name == 'working':
                    parts.append(f"- {memory.get('type', 'context')}: {memory.get('content', '')[:150]}")
                else:
                    parts.append(f"- {memory.get('content', '')[:200]}")

            parts.append("")

        return "\n".join(parts)