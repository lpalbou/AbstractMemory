"""
Dual Storage Manager for managing multiple storage backends.
Supports markdown, lancedb, dual, or no storage modes.
"""

from typing import Optional, Dict, List, Literal, Any
from datetime import datetime
import logging

from ..core.interfaces import IStorage

logger = logging.getLogger(__name__)


class DualStorageManager:
    """
    Manages multiple storage backends for verbatim interactions and experiential notes.

    Modes:
    - "markdown": Human-readable, observable, version-controllable
    - "lancedb": SQL + vector search capabilities via AbstractCore embeddings
    - "dual": Write to both, read from LanceDB for performance
    - None: No persistence (default)
    """

    def __init__(self,
                 mode: Optional[Literal["markdown", "lancedb", "dual"]] = None,
                 markdown_path: Optional[str] = None,
                 lancedb_uri: Optional[str] = None,
                 embedding_provider: Optional[Any] = None):
        """
        Initialize storage manager.

        Args:
            mode: Storage mode to use
            markdown_path: Path for markdown storage
            lancedb_uri: URI for LanceDB storage
            embedding_provider: AbstractCore instance for embeddings
        """
        self.mode = mode
        self.embedding_provider = embedding_provider

        # Initialize storage backends based on mode
        self.markdown_storage = None
        self.lancedb_storage = None

        if mode in ["markdown", "dual"] and markdown_path:
            try:
                from .markdown_storage import MarkdownStorage
                self.markdown_storage = MarkdownStorage(markdown_path)
                logger.info(f"Initialized markdown storage at {markdown_path}")
            except (ImportError, OSError, FileNotFoundError) as e:
                logger.warning(f"Failed to initialize markdown storage: {e}")
                self.markdown_storage = None

        if mode in ["lancedb", "dual"] and lancedb_uri:
            try:
                from .lancedb_storage import LanceDBStorage
                self.lancedb_storage = LanceDBStorage(lancedb_uri, embedding_provider)
                logger.info(f"Initialized LanceDB storage at {lancedb_uri}")
            except (ImportError, OSError, FileNotFoundError) as e:
                logger.warning(f"Failed to initialize LanceDB storage: {e}")
                self.lancedb_storage = None

    def is_enabled(self) -> bool:
        """Check if any storage backend is enabled"""
        return self.mode is not None and (self.markdown_storage is not None or self.lancedb_storage is not None)

    def save_interaction(self, user_id: str, timestamp: datetime,
                        user_input: str, agent_response: str,
                        topic: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """
        Save verbatim interaction to enabled storage backends.

        Returns:
            Interaction ID if successful, None if no storage enabled
        """
        if not self.is_enabled():
            return None

        interaction_id = None

        # Save to markdown storage
        if self.markdown_storage:
            try:
                interaction_id = self.markdown_storage.save_interaction(
                    user_id, timestamp, user_input, agent_response, topic, metadata
                )
                logger.debug(f"Saved interaction {interaction_id} to markdown storage")
            except Exception as e:
                logger.error(f"Failed to save interaction to markdown: {e}")

        # Save to LanceDB storage
        if self.lancedb_storage:
            try:
                # LanceDB storage handles embedding generation internally
                ldb_id = self.lancedb_storage.save_interaction(
                    user_id, timestamp, user_input, agent_response, topic, metadata
                )
                if interaction_id is None:  # Use LanceDB ID if markdown didn't provide one
                    interaction_id = ldb_id

                logger.debug(f"Saved interaction {ldb_id} to LanceDB storage")
            except Exception as e:
                logger.error(f"Failed to save interaction to LanceDB: {e}")

        return interaction_id

    def save_experiential_note(self, timestamp: datetime, reflection: str,
                              interaction_id: str, note_type: str = "reflection",
                              metadata: Optional[Dict] = None) -> Optional[str]:
        """
        Save AI experiential note to enabled storage backends.

        Returns:
            Note ID if successful, None if no storage enabled
        """
        if not self.is_enabled():
            return None

        note_id = None

        # Save to markdown storage
        if self.markdown_storage:
            try:
                note_id = self.markdown_storage.save_experiential_note(
                    timestamp, reflection, interaction_id, note_type, metadata
                )
                logger.debug(f"Saved experiential note {note_id} to markdown storage")
            except Exception as e:
                logger.error(f"Failed to save experiential note to markdown: {e}")

        # Save to LanceDB storage
        if self.lancedb_storage:
            try:
                # LanceDB storage handles embedding generation internally
                ldb_note_id = self.lancedb_storage.save_experiential_note(
                    timestamp, reflection, interaction_id, note_type, metadata
                )
                if note_id is None:  # Use LanceDB ID if markdown didn't provide one
                    note_id = ldb_note_id

                logger.debug(f"Saved experiential note {ldb_note_id} to LanceDB storage")
            except Exception as e:
                logger.error(f"Failed to save experiential note to LanceDB: {e}")

        return note_id

    def link_interaction_to_note(self, interaction_id: str, note_id: str) -> None:
        """Create bidirectional link between interaction and experiential note"""
        if not self.is_enabled():
            return

        # Link in markdown storage
        if self.markdown_storage:
            try:
                self.markdown_storage.link_interaction_to_note(interaction_id, note_id)
                logger.debug(f"Linked interaction {interaction_id} to note {note_id} in markdown")
            except Exception as e:
                logger.error(f"Failed to create link in markdown: {e}")

        # Link in LanceDB storage
        if self.lancedb_storage:
            try:
                self.lancedb_storage.link_interaction_to_note(interaction_id, note_id)
                logger.debug(f"Linked interaction {interaction_id} to note {note_id} in LanceDB")
            except Exception as e:
                logger.error(f"Failed to create link in LanceDB: {e}")

    def search_interactions(self, query: str, user_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Dict]:
        """
        Search interactions. Prefers LanceDB for performance, falls back to markdown.

        Returns:
            List of matching interactions
        """
        if not self.is_enabled():
            return []

        # Prefer LanceDB for search if available (SQL + vector capabilities)
        if self.lancedb_storage:
            try:
                results = self.lancedb_storage.search_interactions(
                    query, user_id, start_date, end_date
                )
                logger.debug(f"Found {len(results)} interactions via LanceDB search")
                return results
            except Exception as e:
                logger.error(f"LanceDB search failed: {e}")

        # Fallback to markdown search
        if self.markdown_storage:
            try:
                results = self.markdown_storage.search_interactions(
                    query, user_id, start_date, end_date
                )
                logger.debug(f"Found {len(results)} interactions via markdown search")
                return results
            except Exception as e:
                logger.error(f"Markdown search failed: {e}")

        return []

    def save_memory_component(self, component_name: str, component_data: Any) -> None:
        """Save memory component (core, semantic, working, episodic) for backup"""
        if not self.is_enabled():
            return

        # Save to markdown as human-readable snapshot
        if self.markdown_storage and hasattr(self.markdown_storage, 'save_memory_component'):
            try:
                self.markdown_storage.save_memory_component(component_name, component_data)
                logger.debug(f"Saved {component_name} component to markdown storage")
            except Exception as e:
                logger.error(f"Failed to save {component_name} to markdown: {e}")

        # Save to LanceDB for efficient querying
        if self.lancedb_storage and hasattr(self.lancedb_storage, 'save_memory_component'):
            try:
                self.lancedb_storage.save_memory_component(component_name, component_data)
                logger.debug(f"Saved {component_name} component to LanceDB storage")
            except Exception as e:
                logger.error(f"Failed to save {component_name} to LanceDB: {e}")

    def load_memory_component(self, component_name: str) -> Optional[Any]:
        """Load memory component. Prefers LanceDB for performance."""
        if not self.is_enabled():
            return None

        # Try LanceDB first for performance
        if self.lancedb_storage and hasattr(self.lancedb_storage, 'load_memory_component'):
            try:
                component = self.lancedb_storage.load_memory_component(component_name)
                if component is not None:
                    logger.debug(f"Loaded {component_name} component from LanceDB storage")
                    return component
            except Exception as e:
                logger.error(f"Failed to load {component_name} from LanceDB: {e}")

        # Fallback to markdown
        if self.markdown_storage and hasattr(self.markdown_storage, 'load_memory_component'):
            try:
                component = self.markdown_storage.load_memory_component(component_name)
                if component is not None:
                    logger.debug(f"Loaded {component_name} component from markdown storage")
                    return component
            except Exception as e:
                logger.error(f"Failed to load {component_name} from markdown: {e}")

        return None

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored data"""
        stats = {
            "mode": self.mode,
            "markdown_enabled": self.markdown_storage is not None,
            "lancedb_enabled": self.lancedb_storage is not None,
            "embedding_provider": self.embedding_provider is not None
        }

        if self.markdown_storage and hasattr(self.markdown_storage, 'get_stats'):
            stats["markdown_stats"] = self.markdown_storage.get_stats()

        if self.lancedb_storage and hasattr(self.lancedb_storage, 'get_stats'):
            stats["lancedb_stats"] = self.lancedb_storage.get_stats()

        return stats