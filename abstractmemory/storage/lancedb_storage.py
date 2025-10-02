"""
LanceDB storage for semantic search and rich metadata querying.

This implements the semantic memory layer with:
- Vector embeddings for semantic search
- Rich metadata for SQL filtering
- Hybrid search (semantic + SQL)
- Multiple tables: notes, verbatim, links, library, core_memory
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB not installed. Install with: pip install lancedb")

try:
    from abstractllm.embeddings import EmbeddingManager
    ABSTRACTCORE_AVAILABLE = True
except ImportError:
    ABSTRACTCORE_AVAILABLE = False
    logging.warning("AbstractCore embeddings not available (install abstractllm)")

logger = logging.getLogger(__name__)


class LanceDBStorage:
    """
    LanceDB storage with semantic search capabilities.

    Tables:
    - notes_table: Experiential notes (LLM-generated during interaction)
    - verbatim_table: Verbatim interaction records (factual)
    - links_table: Memory associations/relationships
    - library_table: Documents AI has read (subconscious)
    - core_memory_table: Core identity components (10 components)
    """

    def __init__(self, db_path: Path, embedding_model: str = "all-minilm-l6-v2"):
        """
        Initialize LanceDB storage.

        Args:
            db_path: Path to LanceDB database
            embedding_model: Model for embeddings (default: all-minilm-l6-v2)
        """
        if not LANCEDB_AVAILABLE:
            raise RuntimeError("LanceDB not installed. Install with: pip install lancedb")

        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize LanceDB
        self.db = lancedb.connect(str(self.db_path))
        logger.info(f"Connected to LanceDB at {self.db_path}")

        # Initialize embeddings
        if ABSTRACTCORE_AVAILABLE:
            self.embedding_manager = EmbeddingManager(model=embedding_model)
            logger.info(f"Using AbstractCore embeddings: {embedding_model}")
        else:
            self.embedding_manager = None
            logger.warning("AbstractCore not available - embeddings disabled")

        # Initialize tables
        self._init_tables()

    def _init_tables(self):
        """Initialize all LanceDB tables with proper schemas."""
        # Notes table schema
        self.notes_schema = {
            "id": "string",
            "timestamp": "timestamp",
            "user_id": "string",
            "location": "string",
            "content": "string",
            "category": "string",  # reflection, insight, observation, etc.
            "importance": "float",
            "emotion": "string",
            "emotion_intensity": "float",
            "emotion_valence": "string",  # positive, negative, mixed
            "linked_memory_ids": "string",  # JSON array
            "tags": "string",  # JSON array
            "embedding": "vector",  # 384-dim for all-minilm-l6-v2
            "file_path": "string",
            "metadata": "string"  # JSON
        }

        # Verbatim table schema
        self.verbatim_schema = {
            "id": "string",
            "timestamp": "timestamp",
            "user_id": "string",
            "location": "string",
            "user_input": "string",
            "agent_response": "string",
            "topic": "string",
            "category": "string",
            "confidence": "float",
            "tags": "string",  # JSON array
            "embedding": "vector",
            "file_path": "string",
            "metadata": "string"
        }

        # Links table schema
        self.links_schema = {
            "link_id": "string",
            "from_id": "string",
            "to_id": "string",
            "relationship": "string",  # elaborates_on, contradicts, relates_to, etc.
            "timestamp": "timestamp",
            "confidence": "float",
            "metadata": "string"
        }

        # Library table schema (subconscious documents)
        self.library_schema = {
            "doc_id": "string",
            "source_path": "string",
            "source_url": "string",
            "content_type": "string",  # code, markdown, pdf, text
            "first_accessed": "timestamp",
            "last_accessed": "timestamp",
            "access_count": "int",
            "importance_score": "float",
            "tags": "string",  # JSON array
            "topics": "string",  # JSON array
            "embedding": "vector",
            "content_excerpt": "string",
            "metadata": "string"
        }

        # Core memory table schema (10 components)
        self.core_memory_schema = {
            "component": "string",  # purpose, personality, values, etc.
            "version": "int",
            "timestamp": "timestamp",
            "content": "string",
            "change_summary": "string",
            "metadata": "string"
        }

        logger.info("LanceDB schemas initialized")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using AbstractCore.

        Args:
            text: Text to embed

        Returns:
            384-dim embedding vector or None if unavailable
        """
        if not self.embedding_manager:
            logger.warning("Embedding manager not available")
            return None

        try:
            embedding = self.embedding_manager.embed(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def add_note(self, note_data: Dict[str, Any]) -> bool:
        """
        Add experiential note to notes_table.

        Args:
            note_data: Note data with content, metadata, etc.

        Returns:
            True if successful
        """
        try:
            # Generate embedding
            embedding = self._get_embedding(note_data.get("content", ""))
            if embedding is None:
                logger.warning("Skipping note storage - no embedding available")
                return False

            # Prepare record
            record = {
                "id": note_data.get("id", f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "timestamp": note_data.get("timestamp", datetime.now()),
                "user_id": note_data.get("user_id", "unknown"),
                "location": note_data.get("location", "unknown"),
                "content": note_data.get("content", ""),
                "category": note_data.get("category", "note"),
                "importance": note_data.get("importance", 0.5),
                "emotion": note_data.get("emotion", "neutral"),
                "emotion_intensity": note_data.get("emotion_intensity", 0.5),
                "emotion_valence": note_data.get("emotion_valence", "neutral"),
                "linked_memory_ids": json.dumps(note_data.get("linked_memory_ids", [])),
                "tags": json.dumps(note_data.get("tags", [])),
                "embedding": embedding,
                "file_path": note_data.get("file_path", ""),
                "metadata": json.dumps(note_data.get("metadata", {}))
            }

            # Get or create table
            if "notes" not in self.db.table_names():
                self.db.create_table("notes", [record])
                logger.info("Created notes table")
            else:
                table = self.db.open_table("notes")
                table.add([record])

            logger.info(f"Added note to LanceDB: {record['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to add note to LanceDB: {e}")
            return False

    def search_notes(self,
                     query: str,
                     filters: Optional[Dict] = None,
                     limit: int = 10) -> List[Dict]:
        """
        Hybrid search: semantic + SQL filtering.

        Args:
            query: Semantic search query
            filters: Optional SQL filters (user_id, category, since, until, min_importance)
            limit: Max results

        Returns:
            List of matching notes with metadata
        """
        try:
            if "notes" not in self.db.table_names():
                logger.warning("Notes table does not exist yet")
                return []

            # Generate query embedding
            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                logger.warning("Cannot perform semantic search - no embedding available")
                return []

            table = self.db.open_table("notes")

            # Start with semantic search
            results = table.search(query_embedding).limit(limit * 2)  # Get more for filtering

            # Apply SQL filters
            filters = filters or {}

            if filters.get("user_id"):
                results = results.where(f"user_id = '{filters['user_id']}'")

            if filters.get("category"):
                results = results.where(f"category = '{filters['category']}'")

            if filters.get("min_importance"):
                results = results.where(f"importance >= {filters['min_importance']}")

            if filters.get("emotion_valence"):
                results = results.where(f"emotion_valence = '{filters['emotion_valence']}'")

            # Temporal filters - use CAST for proper timestamp comparison
            if filters.get("since"):
                since_ts = filters["since"]
                if isinstance(since_ts, datetime):
                    since_iso = since_ts.isoformat()
                    where_clause = f"CAST(timestamp AS TIMESTAMP) >= CAST('{since_iso}' AS TIMESTAMP)"
                    logger.debug(f"Applying temporal filter: {where_clause}")
                    results = results.where(where_clause)

            if filters.get("until"):
                until_ts = filters["until"]
                if isinstance(until_ts, datetime):
                    until_iso = until_ts.isoformat()
                    where_clause = f"CAST(timestamp AS TIMESTAMP) <= CAST('{until_iso}' AS TIMESTAMP)"
                    logger.debug(f"Applying temporal filter: {where_clause}")
                    results = results.where(where_clause)

            # Execute and convert to list
            results = results.limit(limit).to_list()

            # Parse JSON fields
            for result in results:
                if "linked_memory_ids" in result and isinstance(result["linked_memory_ids"], str):
                    result["linked_memory_ids"] = json.loads(result["linked_memory_ids"])
                if "tags" in result and isinstance(result["tags"], str):
                    result["tags"] = json.loads(result["tags"])
                if "metadata" in result and isinstance(result["metadata"], str):
                    result["metadata"] = json.loads(result["metadata"])

            logger.info(f"Found {len(results)} notes matching query: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to search notes: {e}")
            return []

    def add_link(self, link_data: Dict[str, Any]) -> bool:
        """
        Add memory link to links_table.

        Args:
            link_data: Link data with from_id, to_id, relationship

        Returns:
            True if successful
        """
        try:
            record = {
                "link_id": link_data.get("link_id", f"link_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "from_id": link_data.get("from_id", ""),
                "to_id": link_data.get("to_id", ""),
                "relationship": link_data.get("relationship", "relates_to"),
                "timestamp": link_data.get("timestamp", datetime.now()),
                "confidence": link_data.get("confidence", 1.0),
                "metadata": json.dumps(link_data.get("metadata", {}))
            }

            # Get or create table
            if "links" not in self.db.table_names():
                self.db.create_table("links", [record])
                logger.info("Created links table")
            else:
                table = self.db.open_table("links")
                table.add([record])

            logger.info(f"Added link: {record['from_id']} -> {record['to_id']} ({record['relationship']})")
            return True

        except Exception as e:
            logger.error(f"Failed to add link to LanceDB: {e}")
            return False

    def add_verbatim(self, verbatim_data: Dict[str, Any]) -> bool:
        """
        Add verbatim interaction to verbatim table (Phase 1).

        This indexes factual conversation records for semantic search.
        Only called if session.index_verbatims=True.

        Args:
            verbatim_data: Dict with id, timestamp, user_id, location, user_input,
                          agent_response, topic, category, confidence, tags,
                          file_path, metadata

        Returns:
            True if successful
        """
        try:
            if not self.embedding_manager:
                logger.warning("Cannot index verbatim - embeddings disabled")
                return False

            # Generate embedding for combined user_input + agent_response
            combined_text = f"{verbatim_data.get('user_input', '')} {verbatim_data.get('agent_response', '')}"
            embedding = self._get_embedding(combined_text)

            if embedding is None:
                logger.warning("Failed to generate embedding for verbatim")
                return False

            # Create record matching verbatim_schema
            record = {
                "id": verbatim_data.get("id", ""),
                "timestamp": verbatim_data.get("timestamp", datetime.now()),
                "user_id": verbatim_data.get("user_id", ""),
                "location": verbatim_data.get("location", "unknown"),
                "user_input": verbatim_data.get("user_input", ""),
                "agent_response": verbatim_data.get("agent_response", ""),
                "topic": verbatim_data.get("topic", ""),
                "category": verbatim_data.get("category", "conversation"),
                "confidence": verbatim_data.get("confidence", 1.0),
                "tags": verbatim_data.get("tags", "[]"),  # Already JSON string
                "embedding": embedding,
                "file_path": verbatim_data.get("file_path", ""),
                "metadata": verbatim_data.get("metadata", "{}")  # Already JSON string
            }

            # Get or create table
            if "verbatim" not in self.db.table_names():
                self.db.create_table("verbatim", [record])
                logger.info("Created verbatim table")
            else:
                table = self.db.open_table("verbatim")
                table.add([record])

            logger.debug(f"Added verbatim to LanceDB: {record['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to add verbatim to LanceDB: {e}")
            return False

    def get_related_memories(self, memory_id: str, depth: int = 1) -> List[str]:
        """
        Get related memory IDs via links (bidirectional).

        Args:
            memory_id: Source memory ID
            depth: How many hops to follow (1-5)

        Returns:
            List of related memory IDs
        """
        try:
            if "links" not in self.db.table_names():
                return []

            table = self.db.open_table("links")
            visited = set([memory_id])
            current_level = [memory_id]

            for _ in range(depth):
                next_level = []

                for mid in current_level:
                    # Find outgoing links
                    outgoing = table.search().where(f"from_id = '{mid}'").to_list()
                    for link in outgoing:
                        if link["to_id"] not in visited:
                            visited.add(link["to_id"])
                            next_level.append(link["to_id"])

                    # Find incoming links
                    incoming = table.search().where(f"to_id = '{mid}'").to_list()
                    for link in incoming:
                        if link["from_id"] not in visited:
                            visited.add(link["from_id"])
                            next_level.append(link["from_id"])

                if not next_level:
                    break

                current_level = next_level

            # Remove original memory_id
            visited.discard(memory_id)

            logger.info(f"Found {len(visited)} related memories for {memory_id} (depth={depth})")
            return list(visited)

        except Exception as e:
            logger.error(f"Failed to get related memories: {e}")
            return []

    def add_library_document(self, doc_data: Dict[str, Any]) -> bool:
        """
        Add document to library_table (subconscious memory).

        Args:
            doc_data: Document data

        Returns:
            True if successful
        """
        try:
            # Generate embedding from excerpt
            excerpt = doc_data.get("content_excerpt", "")
            embedding = self._get_embedding(excerpt)
            if embedding is None:
                logger.warning("Skipping library document - no embedding available")
                return False

            record = {
                "doc_id": doc_data.get("doc_id", f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                "source_path": doc_data.get("source_path", ""),
                "source_url": doc_data.get("source_url", ""),
                "content_type": doc_data.get("content_type", "text"),
                "first_accessed": doc_data.get("first_accessed", datetime.now()),
                "last_accessed": doc_data.get("last_accessed", datetime.now()),
                "access_count": doc_data.get("access_count", 1),
                "importance_score": doc_data.get("importance_score", 0.5),
                "tags": json.dumps(doc_data.get("tags", [])),
                "topics": json.dumps(doc_data.get("topics", [])),
                "embedding": embedding,
                "content_excerpt": excerpt,
                "metadata": json.dumps(doc_data.get("metadata", {}))
            }

            # Get or create table
            if "library" not in self.db.table_names():
                self.db.create_table("library", [record])
                logger.info("Created library table")
            else:
                table = self.db.open_table("library")
                table.add([record])

            logger.info(f"Added library document: {record['doc_id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to add library document: {e}")
            return False

    def search_library(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search library (subconscious documents).

        Args:
            query: Semantic search query
            limit: Max results

        Returns:
            List of matching documents
        """
        try:
            if "library" not in self.db.table_names():
                logger.warning("Library table does not exist yet")
                return []

            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                return []

            table = self.db.open_table("library")
            results = table.search(query_embedding).limit(limit).to_list()

            # Parse JSON fields
            for result in results:
                if "tags" in result and isinstance(result["tags"], str):
                    result["tags"] = json.loads(result["tags"])
                if "topics" in result and isinstance(result["topics"], str):
                    result["topics"] = json.loads(result["topics"])
                if "metadata" in result and isinstance(result["metadata"], str):
                    result["metadata"] = json.loads(result["metadata"])

            logger.info(f"Found {len(results)} library documents matching: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to search library: {e}")
            return []
