"""
Universal memory indexer for all memory modules.

Provides methods to index each memory type to LanceDB with
batch processing and incremental updates.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

from ..storage.lancedb_storage import LanceDBStorage
from .config import MemoryIndexConfig, IndexManager

logger = logging.getLogger(__name__)


class MemoryIndexer:
    """Universal indexer for all memory modules."""

    def __init__(
        self,
        memory_base_path: Path,
        lancedb_storage: LanceDBStorage,
        config: Optional[MemoryIndexConfig] = None
    ):
        """
        Initialize the memory indexer.

        Args:
            memory_base_path: Base path for memory storage
            lancedb_storage: LanceDB storage instance
            config: Optional index configuration
        """
        self.memory_base_path = Path(memory_base_path)
        self.lancedb = lancedb_storage
        self.index_manager = IndexManager(memory_base_path)
        self.config = config or self.index_manager.config

        # Initialize module paths
        self.module_paths = {
            'notes': self.memory_base_path / 'notes',
            'verbatim': self.memory_base_path / 'verbatim',
            'library': self.memory_base_path / 'library',
            'links': self.memory_base_path / 'links',
            'core': self.memory_base_path / 'core',
            'working': self.memory_base_path / 'working',
            'episodic': self.memory_base_path / 'episodic',
            'semantic': self.memory_base_path / 'semantic',
            'people': self.memory_base_path / 'people'
        }

    def index_all_enabled(self, force_reindex: bool = False) -> Dict[str, int]:
        """
        Index all enabled memory modules.

        Args:
            force_reindex: Whether to force reindexing of existing content

        Returns:
            Dictionary with module names and number of items indexed
        """
        results = {}
        for module_name in self.config.get_enabled_modules():
            try:
                count = self.index_module(module_name, force_reindex)
                results[module_name] = count
                logger.info(f"Indexed {count} items from {module_name}")
            except Exception as e:
                logger.error(f"Failed to index {module_name}: {e}")
                results[module_name] = 0

        return results

    def index_module(self, module_name: str, force_reindex: bool = False) -> int:
        """
        Index a specific memory module.

        Args:
            module_name: Name of the module to index
            force_reindex: Whether to force reindexing

        Returns:
            Number of items indexed
        """
        if not self.config.should_index_module(module_name, "manual"):
            logger.warning(f"Module {module_name} is not enabled for indexing")
            return 0

        # Dispatch to specific indexer based on module type
        indexers = {
            'notes': self._index_notes,
            'verbatim': self._index_verbatim,
            'library': self._index_library,
            'links': self._index_links,
            'core': self._index_core_memory,
            'working': self._index_working_memory,
            'episodic': self._index_episodic_memory,
            'semantic': self._index_semantic_memory,
            'people': self._index_people
        }

        if module_name not in indexers:
            raise ValueError(f"Unknown module: {module_name}")

        count = indexers[module_name](force_reindex)

        # Update configuration stats
        self.config.update_index_stats(module_name, count)
        self.index_manager.save_config()

        # Log summary instead of individual items
        if count > 0:
            logger.info(f"Indexed {count} items from {module_name}")
        else:
            logger.debug(f"No new items to index from {module_name}")

        return count

    def _index_notes(self, force_reindex: bool = False) -> int:
        """Index experiential notes."""
        notes_path = self.module_paths['notes']
        if not notes_path.exists():
            return 0

        count = 0
        # Recursively find all .md files under notes/
        for note_file in notes_path.rglob("*.md"):
            try:
                # Check if already indexed
                note_id = f"note_{note_file.stem}"
                if not force_reindex and self._is_indexed('notes', note_id):
                    continue

                content = note_file.read_text(encoding='utf-8')
                timestamp = datetime.fromtimestamp(note_file.stat().st_mtime)

                # Extract emotion and intensity from content
                emotion, intensity = self._extract_emotion_from_note(content)

                # Add to LanceDB
                self.lancedb.add_note({
                    'id': note_id,
                    'content': content,
                    'timestamp': timestamp.isoformat(),
                    'emotion': emotion,
                    'emotion_intensity': intensity,
                    'type': 'experiential',
                    'source': str(note_file.relative_to(self.memory_base_path))
                })
                count += 1

            except Exception as e:
                logger.error(f"Failed to index note {note_file}: {e}")

        return count

    def _index_verbatim(self, force_reindex: bool = False) -> int:
        """Index verbatim conversation transcripts."""
        verbatim_path = self.module_paths['verbatim']
        if not verbatim_path.exists():
            return 0

        count = 0
        for user_dir in verbatim_path.iterdir():
            if not user_dir.is_dir():
                continue

            for year_dir in user_dir.iterdir():
                if not year_dir.is_dir():
                    continue

                for verbatim_file in year_dir.glob("*.md"):
                    try:
                        verbatim_id = f"verbatim_{user_dir.name}_{verbatim_file.stem}"
                        if not force_reindex and self._is_indexed('verbatim', verbatim_id):
                            continue

                        content = verbatim_file.read_text(encoding='utf-8')
                        timestamp = datetime.fromtimestamp(verbatim_file.stat().st_mtime)

                        # Parse verbatim for query and response
                        query, response = self._parse_verbatim(content)

                        self.lancedb.add_verbatim({
                            'id': verbatim_id,
                            'user_id': user_dir.name,
                            'query': query,
                            'response': response,
                            'content': content,
                            'timestamp': timestamp.isoformat(),
                            'source': str(verbatim_file.relative_to(self.memory_base_path))
                        })
                        count += 1

                    except Exception as e:
                        logger.error(f"Failed to index verbatim {verbatim_file}: {e}")

        return count

    def _index_library(self, force_reindex: bool = False) -> int:
        """Index library documents."""
        library_path = self.module_paths['library']
        docs_path = library_path / 'documents'

        if not docs_path.exists():
            return 0

        count = 0
        for doc_dir in docs_path.iterdir():
            if not doc_dir.is_dir():
                continue

            metadata_file = doc_dir / 'metadata.json'
            content_file = doc_dir / 'content.md'

            if not metadata_file.exists() or not content_file.exists():
                continue

            try:
                doc_id = doc_dir.name
                if not force_reindex and self._is_indexed('library', doc_id):
                    continue

                # Load metadata and content
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                content = content_file.read_text(encoding='utf-8')

                # Add to LanceDB
                self.lancedb.add_library_document({
                    'id': doc_id,
                    'content': content,
                    'title': metadata.get('title', 'Untitled'),
                    'source_path': metadata.get('source_path', ''),
                    'content_type': metadata.get('content_type', 'unknown'),
                    'timestamp': metadata.get('captured_at', datetime.now().isoformat()),
                    'tags': metadata.get('tags', []),
                    'importance': metadata.get('importance', 0.0),
                    'access_count': metadata.get('access_count', 0)
                })
                count += 1

            except Exception as e:
                logger.error(f"Failed to index library document {doc_dir}: {e}")

        return count

    def _index_links(self, force_reindex: bool = False) -> int:
        """Index memory links/associations."""
        # Links are already indexed automatically when created
        # This method would reindex from filesystem if needed
        links_path = self.module_paths['links']
        if not links_path.exists():
            return 0

        count = 0
        for date_dir in links_path.iterdir():
            if not date_dir.is_dir():
                continue

            for link_file in date_dir.glob("*.json"):
                try:
                    link_id = f"link_{link_file.stem}"
                    if not force_reindex and self._is_indexed('links', link_id):
                        continue

                    with open(link_file, 'r') as f:
                        link_data = json.load(f)

                    # Add to LanceDB if not already indexed
                    # Links table already exists and is actively used
                    count += 1

                except Exception as e:
                    logger.error(f"Failed to index link {link_file}: {e}")

        return count

    def _index_core_memory(self, force_reindex: bool = False) -> int:
        """Index core memory components."""
        core_path = self.module_paths['core']
        if not core_path.exists():
            return 0

        count = 0
        core_components = [
            'purpose.md', 'personality.md', 'values.md', 'goals.md',
            'expertise.md', 'knowledge.md', 'identity.md',
            'capabilities.md', 'constraints.md', 'growth_edges.md'
        ]

        for component_file in core_components:
            file_path = core_path / component_file
            if not file_path.exists():
                continue

            try:
                component_name = component_file.replace('.md', '')
                component_id = f"core_{component_name}"

                if not force_reindex and self._is_indexed('core_memory', component_id):
                    continue

                content = file_path.read_text(encoding='utf-8')
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

                # Add to LanceDB core_memory table
                self.lancedb.add_core_memory({
                    'id': component_id,
                    'component': component_name,
                    'content': content,
                    'timestamp': timestamp.isoformat(),
                    'version': self._get_version_from_path(file_path)
                })
                count += 1

            except Exception as e:
                logger.error(f"Failed to index core component {file_path}: {e}")

        return count

    def _index_working_memory(self, force_reindex: bool = False) -> int:
        """Index working memory (current context, tasks, etc)."""
        working_path = self.module_paths['working']
        if not working_path.exists():
            return 0

        count = 0
        working_files = ['current_context.md', 'active_tasks.md', 'unresolved.md', 'resolved.md']

        for memory_file in working_files:
            file_path = working_path / memory_file
            if not file_path.exists():
                continue

            try:
                memory_type = memory_file.replace('.md', '')
                memory_id = f"working_{memory_type}"

                if not force_reindex and self._is_indexed('working_memory', memory_id):
                    continue

                content = file_path.read_text(encoding='utf-8')
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

                # Add to LanceDB working_memory table
                self.lancedb.add_working_memory({
                    'id': memory_id,
                    'type': memory_type,
                    'content': content,
                    'timestamp': timestamp.isoformat(),
                    'active': memory_type in ['current_context', 'active_tasks', 'unresolved']
                })
                count += 1

            except Exception as e:
                logger.error(f"Failed to index working memory {file_path}: {e}")

        return count

    def _index_episodic_memory(self, force_reindex: bool = False) -> int:
        """Index episodic memory (key moments, discoveries, etc)."""
        episodic_path = self.module_paths['episodic']
        if not episodic_path.exists():
            return 0

        count = 0
        episodic_files = ['key_moments.md', 'experiments.md', 'discoveries.md']

        for memory_file in episodic_files:
            file_path = episodic_path / memory_file
            if not file_path.exists():
                continue

            try:
                memory_type = memory_file.replace('.md', '')

                # Parse individual episodes from the file
                content = file_path.read_text(encoding='utf-8')
                episodes = self._parse_episodic_content(content, memory_type)

                for episode in episodes:
                    episode_id = episode['id']
                    if not force_reindex and self._is_indexed('episodic_memory', episode_id):
                        continue

                    # Add to LanceDB episodic_memory table
                    self.lancedb.add_episodic_memory(episode)
                    count += 1

            except Exception as e:
                logger.error(f"Failed to index episodic memory {file_path}: {e}")

        return count

    def _index_semantic_memory(self, force_reindex: bool = False) -> int:
        """Index semantic memory (insights, concepts, knowledge graph)."""
        semantic_path = self.module_paths['semantic']
        if not semantic_path.exists():
            return 0

        count = 0

        # Index insights
        insights_file = semantic_path / 'insights.md'
        if insights_file.exists():
            try:
                content = insights_file.read_text(encoding='utf-8')
                insights = self._parse_semantic_content(content, 'insight')

                for insight in insights:
                    if not force_reindex and self._is_indexed('semantic_memory', insight['id']):
                        continue

                    self.lancedb.add_semantic_memory(insight)
                    count += 1

            except Exception as e:
                logger.error(f"Failed to index insights: {e}")

        # Index concepts
        concepts_file = semantic_path / 'concepts.md'
        if concepts_file.exists():
            try:
                content = concepts_file.read_text(encoding='utf-8')
                concepts = self._parse_semantic_content(content, 'concept')

                for concept in concepts:
                    if not force_reindex and self._is_indexed('semantic_memory', concept['id']):
                        continue

                    self.lancedb.add_semantic_memory(concept)
                    count += 1

            except Exception as e:
                logger.error(f"Failed to index concepts: {e}")

        return count

    def _index_people(self, force_reindex: bool = False) -> int:
        """Index user profiles and preferences."""
        people_path = self.module_paths['people']
        if not people_path.exists():
            return 0

        count = 0
        for user_dir in people_path.iterdir():
            if not user_dir.is_dir():
                continue

            profile_file = user_dir / 'profile.md'
            preferences_file = user_dir / 'preferences.md'

            try:
                user_id = user_dir.name
                profile_id = f"people_{user_id}_profile"

                if force_reindex or not self._is_indexed('people', profile_id):
                    # Index profile
                    if profile_file.exists():
                        profile_content = profile_file.read_text(encoding='utf-8')
                        self.lancedb.add_people({
                            'id': profile_id,
                            'user_id': user_id,
                            'type': 'profile',
                            'content': profile_content,
                            'timestamp': datetime.fromtimestamp(profile_file.stat().st_mtime).isoformat()
                        })
                        count += 1

                    # Index preferences
                    if preferences_file.exists():
                        pref_id = f"people_{user_id}_preferences"
                        pref_content = preferences_file.read_text(encoding='utf-8')
                        self.lancedb.add_people({
                            'id': pref_id,
                            'user_id': user_id,
                            'type': 'preferences',
                            'content': pref_content,
                            'timestamp': datetime.fromtimestamp(preferences_file.stat().st_mtime).isoformat()
                        })
                        count += 1

            except Exception as e:
                logger.error(f"Failed to index user {user_dir}: {e}")

        return count

    # Helper methods

    def _is_indexed(self, table_name: str, item_id: str) -> bool:
        """Check if an item is already indexed in LanceDB."""
        try:
            # Check if table exists
            if table_name not in self.lancedb.db.table_names():
                return False

            # Query table for this item ID
            table = self.lancedb.db.open_table(table_name)
            results = table.search().where(f"id = '{item_id}'").limit(1).to_list()

            return len(results) > 0
        except Exception as e:
            logger.debug(f"Error checking if {item_id} is indexed in {table_name}: {e}")
            return False

    def _extract_emotion_from_note(self, content: str) -> Tuple[str, float]:
        """Extract emotion and intensity from note content."""
        # Simple extraction - looks for emotion markers in content
        # Real implementation would parse the structured note format
        import re

        emotion_pattern = r'Emotion:\s*(\w+)\s*\(([0-9.]+)\)'
        match = re.search(emotion_pattern, content)

        if match:
            return match.group(1), float(match.group(2))
        return 'neutral', 0.5

    def _parse_verbatim(self, content: str) -> Tuple[str, str]:
        """Parse verbatim content into query and response."""
        lines = content.split('\n')
        query = ""
        response = ""
        in_query = False
        in_response = False

        for line in lines:
            if line.startswith('**User:**'):
                in_query = True
                in_response = False
                query = line.replace('**User:**', '').strip()
            elif line.startswith('**Agent:**'):
                in_query = False
                in_response = True
                response = line.replace('**Agent:**', '').strip()
            elif in_query:
                query += " " + line.strip()
            elif in_response:
                response += " " + line.strip()

        return query.strip(), response.strip()

    def _get_version_from_path(self, file_path: Path) -> str:
        """Get version information from file path or content."""
        # Check for .versions directory
        versions_dir = file_path.parent / '.versions'
        if versions_dir.exists():
            # Get latest version
            versions = sorted(versions_dir.glob(f"{file_path.stem}_*.md"))
            if versions:
                return versions[-1].stem.split('_')[-1]
        return "1.0.0"

    def _parse_episodic_content(self, content: str, memory_type: str) -> List[Dict]:
        """Parse episodic memory content into individual episodes."""
        episodes = []
        lines = content.split('\n')
        current_episode = None
        episode_count = 0

        for line in lines:
            line = line.strip()
            if line.startswith('##'):
                # New episode
                if current_episode:
                    episodes.append(current_episode)

                episode_count += 1
                title = line.replace('#', '').strip()
                current_episode = {
                    'id': f"episodic_{memory_type}_{episode_count:04d}",
                    'type': memory_type,
                    'title': title,
                    'content': "",
                    'timestamp': datetime.now().isoformat(),
                    'emotion': 'neutral',
                    'emotion_intensity': 0.5
                }
            elif current_episode and line:
                current_episode['content'] += line + '\n'

        if current_episode:
            episodes.append(current_episode)

        return episodes

    def _parse_semantic_content(self, content: str, memory_type: str) -> List[Dict]:
        """Parse semantic memory content into individual items."""
        items = []
        lines = content.split('\n')
        current_item = None
        item_count = 0

        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                # New item
                if current_item:
                    items.append(current_item)

                item_count += 1
                item_content = line[1:].strip()
                current_item = {
                    'id': f"semantic_{memory_type}_{item_count:04d}",
                    'type': memory_type,
                    'content': item_content,
                    'timestamp': datetime.now().isoformat(),
                    'connections': []
                }
            elif current_item and line and line.startswith(' '):
                # Additional content for current item
                current_item['content'] += ' ' + line.strip()

        if current_item:
            items.append(current_item)

        return items

    def rebuild_index(self, module_name: str) -> int:
        """
        Completely rebuild the index for a module.

        Args:
            module_name: Name of the module to rebuild

        Returns:
            Number of items indexed
        """
        # Drop existing table if it exists
        table_name = self.config.get_module_config(module_name).table_name
        if table_name:
            try:
                self.lancedb.drop_table(table_name)
            except:
                pass  # Table might not exist

        # Force reindex
        return self.index_module(module_name, force_reindex=True)

    def get_index_stats(self, module_name: Optional[str] = None) -> Dict:
        """
        Get indexing statistics for one or all modules.

        Args:
            module_name: Optional specific module to get stats for

        Returns:
            Dictionary with indexing statistics
        """
        if module_name:
            module_config = self.config.get_module_config(module_name)
            if not module_config:
                return {}

            return {
                'module': module_name,
                'enabled': module_config.enabled,
                'table_name': module_config.table_name,
                'last_indexed': module_config.last_indexed,
                'index_count': module_config.index_count,
                'auto_update': module_config.auto_update
            }

        # Get stats for all modules
        return self.config.get_status()