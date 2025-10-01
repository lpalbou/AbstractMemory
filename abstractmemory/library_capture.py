"""
Library Memory Capture - "You Are What You Read"

Captures everything the AI reads into Library (subconscious memory).
Tracks access patterns, calculates importance, enables retrieval during reconstruction.

Philosophy from docs/mindmap.md:266-318:
- Library is subconscious memory (not actively recalled)
- "You are what you read" - access patterns reveal interests
- Everything AI has been exposed to
- Retrievable during active reconstruction

Implementation follows docs/diagrams.md:865-994.
"""

import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import math

logger = logging.getLogger(__name__)


class LibraryCapture:
    """
    Captures and tracks everything the AI reads.

    Structure (from docs/mindmap.md:275-283):
    library/
    ├── documents/{doc_hash}/
    │   ├── content.md (full document)
    │   ├── metadata.json (source, access stats)
    │   └── excerpts/{excerpt_id}.md (key passages)
    ├── access_log.json (when/how often accessed)
    ├── importance_map.json (which docs most significant)
    └── index.json (master index)
    """

    def __init__(self, library_base_path: Path, embedding_manager=None, lancedb_storage=None):
        """
        Initialize Library Capture system.

        CRITICAL: Implements DUAL STORAGE (markdown + LanceDB) per design spec.

        Args:
            library_base_path: Base path for library storage
            embedding_manager: AbstractCore EmbeddingManager for vectors
            lancedb_storage: LanceDB storage for dual storage (MANDATORY)
        """
        self.library_path = Path(library_base_path) / "library"
        self.documents_path = self.library_path / "documents"
        self.embedding_manager = embedding_manager
        self.lancedb_storage = lancedb_storage

        # Create structure
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.documents_path.mkdir(parents=True, exist_ok=True)

        # Initialize tracking files
        self.access_log_path = self.library_path / "access_log.json"
        self.importance_map_path = self.library_path / "importance_map.json"
        self.index_path = self.library_path / "index.json"

        self._ensure_tracking_files()

        logger.info(f"Library initialized at {self.library_path} with dual storage: {lancedb_storage is not None}")

    def _ensure_tracking_files(self):
        """Ensure tracking JSON files exist."""
        if not self.access_log_path.exists():
            self.access_log_path.write_text(json.dumps([], indent=2))

        if not self.importance_map_path.exists():
            self.importance_map_path.write_text(json.dumps({}, indent=2))

        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({
                "documents": {},
                "last_updated": datetime.now().isoformat()
            }, indent=2))

    def calculate_doc_hash(self, source_path: str, content: str) -> str:
        """
        Calculate unique document hash from path + content.

        From docs/diagrams.md:881-883.

        Args:
            source_path: Path to source file/URL
            content: Document content

        Returns:
            str: Unique hash ID (hash_abc123...)
        """
        combined = f"{source_path}:{content[:1000]}"  # Use first 1KB for hash
        hash_obj = hashlib.md5(combined.encode())
        return f"hash_{hash_obj.hexdigest()}"

    def capture_document(self,
                        source_path: str,
                        content: str,
                        content_type: str = "text",
                        source_url: Optional[str] = None,
                        context: Optional[str] = None,
                        tags: Optional[List[str]] = None) -> str:
        """
        Capture a document into Library.

        From docs/diagrams.md:876-919 (Library Capture Process).

        Args:
            source_path: Path to source file
            content: Document content
            content_type: Type (code, markdown, pdf, text)
            source_url: Optional source URL
            context: Optional context for why read
            tags: Optional tags

        Returns:
            str: Document hash ID
        """
        # 1. Generate document hash
        doc_hash = self.calculate_doc_hash(source_path, content)
        doc_dir = self.documents_path / doc_hash

        # Check if already captured
        if doc_dir.exists():
            logger.debug(f"Document {doc_hash} already captured, updating access")
            self.track_access(doc_hash, context)
            return doc_hash

        # 2. Create document directory
        doc_dir.mkdir(parents=True, exist_ok=True)
        excerpts_dir = doc_dir / "excerpts"
        excerpts_dir.mkdir(exist_ok=True)

        logger.info(f"Capturing document {doc_hash} from {source_path}")

        # 3. Store full content
        content_file = doc_dir / "content.md"
        content_file.write_text(content)

        # 4. Extract metadata
        now = datetime.now().isoformat()
        metadata = {
            "doc_id": doc_hash,
            "source_path": source_path,
            "source_url": source_url,
            "content_type": content_type,
            "size": len(content),
            "first_accessed": now,
            "last_accessed": now,
            "access_count": 1,
            "importance_score": 0.0,  # Calculated later
            "tags": tags or self._auto_extract_tags(content_type, source_path),
            "captured_at": now
        }

        metadata_file = doc_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

        # 5. Generate embedding if available
        if self.embedding_manager:
            try:
                # Use first 500 words for embedding
                excerpt = " ".join(content.split()[:500])
                embedding = self.embedding_manager.embed(excerpt)
                metadata["embedding"] = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                metadata_file.write_text(json.dumps(metadata, indent=2))
            except Exception as e:
                logger.warning(f"Could not generate embedding for {doc_hash}: {e}")

        # 6. Update index
        self._update_index(doc_hash, metadata)

        # 7. DUAL STORAGE: Write to LanceDB
        if self.lancedb_storage:
            try:
                # Prepare LanceDB record
                excerpt = " ".join(content.split()[:500])  # First 500 words for embedding
                lancedb_data = {
                    "doc_id": doc_hash,
                    "source_path": source_path,
                    "source_url": source_url or "",
                    "content_type": content_type,
                    "first_accessed": now,
                    "last_accessed": now,
                    "access_count": 1,
                    "importance_score": 0.0,
                    "tags": metadata["tags"],
                    "topics": [],  # Could extract from content later
                    "content_excerpt": excerpt,
                    "metadata": {
                        "size": len(content),
                        "captured_at": now,
                        "context": context
                    }
                }
                success = self.lancedb_storage.add_library_document(lancedb_data)
                if success:
                    logger.info(f"✅ Dual storage: Document written to LanceDB")
                else:
                    logger.warning(f"⚠️ LanceDB write failed for {doc_hash}")
            except Exception as e:
                logger.error(f"❌ Error writing to LanceDB: {e}")
        else:
            logger.warning("⚠️ LanceDB not available - dual storage incomplete")

        # 8. Log access
        self.track_access(doc_hash, context)

        logger.info(f"✅ Captured document {doc_hash} ({len(content)} bytes)")

        return doc_hash

    def _auto_extract_tags(self, content_type: str, source_path: str) -> List[str]:
        """Auto-extract tags from content type and path."""
        tags = [content_type]

        # Extract from path
        path_parts = Path(source_path).parts

        # Add file extension
        ext = Path(source_path).suffix.lstrip('.')
        if ext:
            tags.append(ext)

        # Add language if code
        if content_type == "code":
            language_map = {
                'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                'java': 'java', 'cpp': 'cpp', 'c': 'c', 'rs': 'rust',
                'go': 'go', 'rb': 'ruby', 'php': 'php', 'swift': 'swift'
            }
            if ext in language_map:
                tags.append(language_map[ext])

        return list(set(tags))

    def track_access(self, doc_hash: str, context: Optional[str] = None) -> bool:
        """
        Track document access.

        From docs/diagrams.md:938-943.

        Args:
            doc_hash: Document hash ID
            context: Optional context for access

        Returns:
            bool: Success
        """
        try:
            now = datetime.now().isoformat()

            # 1. Update metadata
            doc_dir = self.documents_path / doc_hash
            if not doc_dir.exists():
                logger.warning(f"Document {doc_hash} not found for access tracking")
                return False

            metadata_file = doc_dir / "metadata.json"
            metadata = json.loads(metadata_file.read_text())

            # Increment access_count
            metadata["access_count"] = metadata.get("access_count", 0) + 1
            metadata["last_accessed"] = now

            metadata_file.write_text(json.dumps(metadata, indent=2))

            # 2. Log to access_log.json
            access_log = json.loads(self.access_log_path.read_text())
            # Ensure access_log is a list (backward compatibility)
            if isinstance(access_log, dict):
                access_log = []
            access_log.append({
                "timestamp": now,
                "doc_id": doc_hash,
                "context": context
            })
            self.access_log_path.write_text(json.dumps(access_log, indent=2))

            # 3. Recalculate importance
            self._recalculate_importance(doc_hash, metadata)

            logger.debug(f"Tracked access to {doc_hash} (count: {metadata['access_count']})")

            return True

        except Exception as e:
            logger.error(f"Error tracking access for {doc_hash}: {e}")
            return False

    def _recalculate_importance(self, doc_hash: str, metadata: Dict) -> float:
        """
        Recalculate document importance score.

        From docs/diagrams.md:958-989 (Importance Scoring).

        Formula:
          base = log(1 + access_count) / 10
          recency_factor = 1.2 if accessed in last 7 days else 1.0
          emotion_boost = avg_emotional_intensity in references (future)
          link_boost = link_count * 0.1 (future)

          importance = min(1.0, base * recency_factor + emotion_boost + link_boost)

        Args:
            doc_hash: Document hash
            metadata: Document metadata

        Returns:
            float: Importance score (0.0-1.0)
        """
        access_count = metadata.get("access_count", 0)
        last_accessed = metadata.get("last_accessed")

        # Base score from access count
        base = math.log(1 + access_count) / 10

        # Recency factor
        recency_factor = 1.0
        if last_accessed:
            try:
                last_dt = datetime.fromisoformat(last_accessed)
                days_since = (datetime.now() - last_dt).days
                if days_since < 7:
                    recency_factor = 1.2
            except:
                pass

        # TODO: emotion_boost from experiential notes that reference this doc
        emotion_boost = 0.0

        # TODO: link_boost from memory links
        link_boost = 0.0

        # Calculate final importance
        importance = min(1.0, base * recency_factor + emotion_boost + link_boost)

        # Update importance_map
        try:
            importance_map = json.loads(self.importance_map_path.read_text())
            importance_map[doc_hash] = {
                "importance": importance,
                "access_count": access_count,
                "last_accessed": last_accessed,
                "updated_at": datetime.now().isoformat()
            }
            self.importance_map_path.write_text(json.dumps(importance_map, indent=2))
        except Exception as e:
            logger.error(f"Error updating importance map: {e}")

        logger.debug(f"Importance for {doc_hash}: {importance:.3f} (access={access_count}, base={base:.3f}, recency={recency_factor})")

        return importance

    def _update_index(self, doc_hash: str, metadata: Dict):
        """Update master index with document."""
        try:
            index = json.loads(self.index_path.read_text())

            # Ensure documents key exists and is a dict
            if "documents" not in index or not isinstance(index["documents"], dict):
                index["documents"] = {}

            index["documents"][doc_hash] = {
                "source_path": metadata["source_path"],
                "content_type": metadata["content_type"],
                "tags": metadata["tags"],
                "first_accessed": metadata["first_accessed"],
                "size": metadata["size"]
            }

            index["last_updated"] = datetime.now().isoformat()

            self.index_path.write_text(json.dumps(index, indent=2))

        except Exception as e:
            logger.error(f"Error updating index: {e}")

    def search_library(self,
                      query: str,
                      limit: int = 5,
                      content_types: Optional[List[str]] = None,
                      tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search Library for relevant documents.

        From docs/diagrams.md:921-956 (Retrieval During Reconstruct).

        Args:
            query: Search query
            limit: Max results
            content_types: Filter by content types
            tags: Filter by tags

        Returns:
            List of documents with excerpts
        """
        results = []

        try:
            # If no embedding manager, fall back to keyword search
            if not self.embedding_manager:
                return self._keyword_search(query, limit, content_types, tags)

            # 1. Generate query embedding
            query_embedding = self.embedding_manager.embed(query)

            # 2. Scan all documents and calculate similarity
            for doc_dir in self.documents_path.iterdir():
                if not doc_dir.is_dir():
                    continue

                doc_hash = doc_dir.name
                metadata_file = doc_dir / "metadata.json"

                if not metadata_file.exists():
                    continue

                metadata = json.loads(metadata_file.read_text())

                # Apply filters
                if content_types and metadata.get("content_type") not in content_types:
                    continue

                if tags:
                    doc_tags = metadata.get("tags", [])
                    if not any(tag in doc_tags for tag in tags):
                        continue

                # Calculate similarity if embedding exists
                if "embedding" in metadata:
                    doc_embedding = metadata["embedding"]
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                else:
                    similarity = 0.0

                # Load content excerpt
                content_file = doc_dir / "content.md"
                content = content_file.read_text()
                excerpt = " ".join(content.split()[:200])  # First 200 words

                results.append({
                    "doc_id": doc_hash,
                    "source": metadata.get("source_path", "unknown"),
                    "excerpt": excerpt,
                    "content_type": metadata.get("content_type", "unknown"),
                    "access_count": metadata.get("access_count", 0),
                    "importance": metadata.get("importance_score", 0.0),
                    "similarity": similarity,
                    "tags": metadata.get("tags", [])
                })

            # 3. Sort by similarity and limit
            results.sort(key=lambda x: x["similarity"], reverse=True)
            results = results[:limit]

            # 4. Update access for retrieved documents
            for result in results:
                self.track_access(result["doc_id"], f"search: {query}")

            logger.info(f"Library search for '{query}': {len(results)} results")

            return results

        except Exception as e:
            logger.error(f"Error searching library: {e}")
            return []

    def _keyword_search(self,
                       query: str,
                       limit: int,
                       content_types: Optional[List[str]],
                       tags: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Fallback keyword search when no embeddings available."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for doc_dir in self.documents_path.iterdir():
            if not doc_dir.is_dir():
                continue

            doc_hash = doc_dir.name
            metadata_file = doc_dir / "metadata.json"
            content_file = doc_dir / "content.md"

            if not metadata_file.exists() or not content_file.exists():
                continue

            metadata = json.loads(metadata_file.read_text())

            # Apply filters
            if content_types and metadata.get("content_type") not in content_types:
                continue

            if tags:
                doc_tags = metadata.get("tags", [])
                if not any(tag in doc_tags for tag in tags):
                    continue

            # Keyword matching
            content = content_file.read_text().lower()
            matches = sum(1 for word in query_words if word in content)
            score = matches / len(query_words) if query_words else 0.0

            if score > 0:
                excerpt = " ".join(content.split()[:200])
                results.append({
                    "doc_id": doc_hash,
                    "source": metadata.get("source_path", "unknown"),
                    "excerpt": excerpt,
                    "content_type": metadata.get("content_type", "unknown"),
                    "access_count": metadata.get("access_count", 0),
                    "importance": metadata.get("importance_score", 0.0),
                    "similarity": score,
                    "tags": metadata.get("tags", [])
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            import numpy as np
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def get_document(self, doc_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full document by hash.

        Args:
            doc_hash: Document hash ID

        Returns:
            Dict with content and metadata, or None
        """
        doc_dir = self.documents_path / doc_hash

        if not doc_dir.exists():
            logger.warning(f"Document {doc_hash} not found")
            return None

        try:
            metadata_file = doc_dir / "metadata.json"
            content_file = doc_dir / "content.md"

            metadata = json.loads(metadata_file.read_text())
            content = content_file.read_text()

            # Track access
            self.track_access(doc_hash, "retrieve_full")

            return {
                "doc_id": doc_hash,
                "content": content,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error retrieving document {doc_hash}: {e}")
            return None

    def get_most_important_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most important documents by importance score.

        From docs/diagrams.md:958-989.

        Args:
            limit: Max number of documents

        Returns:
            List of documents sorted by importance
        """
        try:
            importance_map = json.loads(self.importance_map_path.read_text())

            # Sort by importance
            sorted_docs = sorted(
                importance_map.items(),
                key=lambda x: x[1].get("importance", 0.0),
                reverse=True
            )

            results = []
            for doc_hash, info in sorted_docs[:limit]:
                doc_dir = self.documents_path / doc_hash
                metadata_file = doc_dir / "metadata.json"

                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    results.append({
                        "doc_id": doc_hash,
                        "source": metadata.get("source_path", "unknown"),
                        "importance": info["importance"],
                        "access_count": info["access_count"],
                        "last_accessed": info["last_accessed"],
                        "tags": metadata.get("tags", [])
                    })

            return results

        except Exception as e:
            logger.error(f"Error getting most important documents: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get library statistics.

        Returns:
            Dict with stats
        """
        try:
            index = json.loads(self.index_path.read_text())
            importance_map = json.loads(self.importance_map_path.read_text())
            access_log = json.loads(self.access_log_path.read_text())

            # Ensure backward compatibility
            if not isinstance(access_log, list):
                access_log = []
            if not isinstance(index, dict):
                index = {"documents": {}}
            if "documents" not in index:
                index["documents"] = {}

            total_docs = len(index.get("documents", {}))
            total_accesses = len(access_log)

            # Content type distribution
            content_types = {}
            for doc_info in index.get("documents", {}).values():
                ct = doc_info.get("content_type", "unknown")
                content_types[ct] = content_types.get(ct, 0) + 1

            # Average importance
            importances = [info.get("importance", 0.0) for info in importance_map.values()]
            avg_importance = sum(importances) / len(importances) if importances else 0.0

            return {
                "total_documents": total_docs,
                "total_accesses": total_accesses,
                "content_types": content_types,
                "average_importance": avg_importance,
                "most_important": self.get_most_important_documents(5)
            }

        except Exception as e:
            logger.error(f"Error getting library stats: {e}")
            import traceback
            traceback.print_exc()
            return {
                "total_documents": 0,
                "total_accesses": 0,
                "content_types": {},
                "average_importance": 0.0,
                "most_important": []
            }
