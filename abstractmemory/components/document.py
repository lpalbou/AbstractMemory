"""
Document Memory Component - Storage and indexing of files/documents.

This component is specifically designed to store and retrieve documents that
have been read or processed by agents, providing semantic search capabilities
over document content while maintaining document metadata and access patterns.

Separate from other memory types:
- Core: Identity, values, relationships
- Working: Short-term conversation context
- Semantic: Validated facts and concepts
- Episodic: Historical events and interactions
- Document: Files, documents, and their content (THIS MODULE)
"""

import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from ..core.interfaces import IMemoryComponent, MemoryItem


class DocumentMemory(IMemoryComponent):
    """
    Memory component for storing and indexing documents/files.

    Key features:
    - Stores document content with metadata (filepath, size, type, etc.)
    - Tracks access patterns (read count, last accessed)
    - Content chunking for semantic search
    - Deduplication by content hash
    - Semantic search over document chunks
    """

    def __init__(self, embedding_provider=None):
        """
        Initialize DocumentMemory.

        Args:
            embedding_provider: Provider for semantic embeddings (optional)

        Note: Full document content is always stored. Chunking is only used
              for semantic search purposes, not for storage limitations.
        """
        self.documents: Dict[str, Dict] = {}  # doc_id -> document data
        self.file_index: Dict[str, str] = {}  # filepath -> doc_id
        self.content_hashes: Dict[str, str] = {}  # content_hash -> doc_id
        self.chunks: Dict[str, List[Dict]] = {}  # doc_id -> chunks for search
        self.embedding_provider = embedding_provider

    def add(self, item: MemoryItem) -> str:
        """
        Add a document to memory.

        Args:
            item: MemoryItem with document content and metadata
                  Expected metadata: filepath, file_type, file_size

        Returns:
            Document ID
        """
        content = str(item.content)
        filepath = item.metadata.get('filepath', 'unknown') if item.metadata else 'unknown'

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Enhanced duplicate detection: check both content hash AND filepath
        existing_doc_id = None
        duplicate_reason = None

        # Check if we already have this exact content (by hash)
        if content_hash in self.content_hashes:
            existing_doc_id = self.content_hashes[content_hash]
            duplicate_reason = f"identical content (hash: {content_hash[:12]}...)"

        # Check if we already have this filepath (even with different content)
        elif filepath != 'unknown' and filepath in self.file_index:
            existing_doc_id = self.file_index[filepath]
            duplicate_reason = f"same filepath: {filepath}"

        # Handle duplicates with AbstractCore logging
        if existing_doc_id:
            try:
                from abstractcore.logger import get_logger
                logger = get_logger(__name__)
                logger.info(f"Document already stored - {duplicate_reason}. Updating access count for doc_id: {existing_doc_id}")
            except ImportError:
                # Fallback to standard logging if AbstractCore not available
                import logging
                logging.info(f"Document already stored - {duplicate_reason}. Updating access count for doc_id: {existing_doc_id}")

            self._update_access_count(existing_doc_id)
            return existing_doc_id

        # Create new document entry
        doc_id = f"doc_{len(self.documents)}_{int(datetime.now().timestamp())}"

        # Store FULL content - no truncation for storage
        document_data = {
            'doc_id': doc_id,
            'filepath': filepath,
            'content': content,  # Store complete content
            'content_hash': content_hash,
            'content_size': len(content),
            'file_type': item.metadata.get('file_type', self._infer_file_type(filepath)) if item.metadata else self._infer_file_type(filepath),
            'file_size': item.metadata.get('file_size', len(content)) if item.metadata else len(content),
            'added_at': datetime.now(),
            'last_accessed': datetime.now(),
            'access_count': 1,
            'ingestion_time': item.ingestion_time,
            'event_time': item.event_time,
            'confidence': item.confidence,
            'metadata': item.metadata or {}
        }

        # Store document
        self.documents[doc_id] = document_data
        self.file_index[filepath] = doc_id
        self.content_hashes[content_hash] = doc_id

        # Create searchable chunks if embedding provider available
        if self.embedding_provider:
            self._create_document_chunks(doc_id, content)

        return doc_id

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """
        Retrieve documents matching the query.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of MemoryItems for matching documents
        """
        results = []

        # If embedding provider available, use semantic search
        if self.embedding_provider and self.chunks:
            results.extend(self._semantic_search(query, limit))

        # Also do keyword search for broader coverage
        keyword_results = self._keyword_search(query, limit)

        # Combine and deduplicate results
        seen_doc_ids = {item.metadata['doc_id'] for item in results}
        for result in keyword_results:
            if result.metadata['doc_id'] not in seen_doc_ids:
                results.append(result)
                seen_doc_ids.add(result.metadata['doc_id'])

        # Sort by relevance (confidence) and limit
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

    def consolidate(self) -> int:
        """
        Consolidate document memory (cleanup, optimize chunks).

        Returns:
            Number of operations performed
        """
        operations = 0

        # Remove duplicate chunks
        if self.chunks:
            for doc_id, chunks in self.chunks.items():
                unique_chunks = []
                seen_content = set()

                for chunk in chunks:
                    chunk_content = chunk['content']
                    if chunk_content not in seen_content:
                        unique_chunks.append(chunk)
                        seen_content.add(chunk_content)
                    else:
                        operations += 1

                self.chunks[doc_id] = unique_chunks

        # Update access patterns
        now = datetime.now()
        for doc_data in self.documents.values():
            # Age-based confidence adjustment
            days_old = (now - doc_data['added_at']).days
            if days_old > 30:
                # Slightly reduce confidence for very old documents
                doc_data['confidence'] = max(0.1, doc_data['confidence'] * 0.95)
                operations += 1

        return operations

    def search_documents(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search documents and return detailed document information.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of document dictionaries with metadata
        """
        memory_items = self.retrieve(query, limit)
        documents = []

        for item in memory_items:
            doc_id = item.metadata.get('doc_id')
            if doc_id and doc_id in self.documents:
                doc_data = self.documents[doc_id].copy()
                self._update_access_count(doc_id)  # Track access
                documents.append(doc_data)

        return documents

    def get_document_by_filepath(self, filepath: str) -> Optional[Dict]:
        """Get document by filepath."""
        doc_id = self.file_index.get(filepath)
        if doc_id:
            self._update_access_count(doc_id)
            return self.documents[doc_id].copy()
        return None

    def get_document_summary(self) -> Dict:
        """Get summary statistics about stored documents."""
        if not self.documents:
            return {'total_documents': 0}

        total_docs = len(self.documents)
        total_size = sum(doc['content_size'] for doc in self.documents.values())
        file_types = {}

        for doc in self.documents.values():
            file_type = doc.get('file_type', 'unknown')
            file_types[file_type] = file_types.get(file_type, 0) + 1

        most_accessed = max(self.documents.values(), key=lambda x: x['access_count'])

        return {
            'total_documents': total_docs,
            'total_content_size': total_size,
            'file_types': file_types,
            'most_accessed_document': {
                'filepath': most_accessed['filepath'],
                'access_count': most_accessed['access_count']
            },
            'has_semantic_search': self.embedding_provider is not None,
            'total_chunks': sum(len(chunks) for chunks in self.chunks.values()) if self.chunks else 0
        }

    def _update_access_count(self, doc_id: str):
        """Update document access statistics."""
        if doc_id in self.documents:
            self.documents[doc_id]['access_count'] += 1
            self.documents[doc_id]['last_accessed'] = datetime.now()

    def _infer_file_type(self, filepath: str) -> str:
        """Infer file type from filepath."""
        try:
            suffix = Path(filepath).suffix.lower()
            type_map = {
                '.txt': 'text',
                '.md': 'markdown',
                '.py': 'python',
                '.js': 'javascript',
                '.json': 'json',
                '.html': 'html',
                '.css': 'css',
                '.pdf': 'pdf',
                '.doc': 'document',
                '.docx': 'document',
                '.log': 'log'
            }
            return type_map.get(suffix, 'unknown')
        except:
            return 'unknown'

    def _create_document_chunks(self, doc_id: str, content: str):
        """Create searchable chunks for semantic search."""
        # Simple chunking strategy - can be enhanced
        chunk_size = 500  # characters per chunk
        overlap = 50     # character overlap between chunks

        chunks = []
        start = 0

        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_content = content[start:end]

            # Create chunk with metadata
            chunk = {
                'content': chunk_content,
                'start_pos': start,
                'end_pos': end,
                'doc_id': doc_id,
                'chunk_id': len(chunks)
            }

            chunks.append(chunk)

            # Move start position with overlap
            start = end - overlap
            if start >= len(content):
                break

        self.chunks[doc_id] = chunks

    def _semantic_search(self, query: str, limit: int) -> List[MemoryItem]:
        """Perform semantic search using embeddings."""
        if not self.embedding_provider or not self.chunks:
            return []

        try:
            # Generate query embedding
            query_embedding = self.embedding_provider.generate_embedding(query)

            # Score all chunks (simplified - in production, use vector database)
            chunk_scores = []

            for doc_id, doc_chunks in self.chunks.items():
                for chunk in doc_chunks:
                    # For demonstration - in reality, pre-compute and store embeddings
                    chunk_embedding = self.embedding_provider.generate_embedding(chunk['content'])

                    # Simple cosine similarity (simplified)
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)

                    chunk_scores.append((similarity, doc_id, chunk))

            # Sort by similarity and get top results
            chunk_scores.sort(key=lambda x: x[0], reverse=True)

            # Convert to MemoryItems
            results = []
            seen_docs = set()

            for similarity, doc_id, chunk in chunk_scores[:limit * 2]:  # Get more to account for duplicates
                if doc_id not in seen_docs and doc_id in self.documents:
                    doc_data = self.documents[doc_id]

                    # Create MemoryItem with document content and high confidence for good matches
                    memory_item = MemoryItem(
                        content=doc_data['content'],
                        event_time=doc_data['event_time'],
                        ingestion_time=doc_data['ingestion_time'],
                        confidence=min(1.0, similarity * 1.2),  # Boost good semantic matches
                        metadata={
                            'doc_id': doc_id,
                            'filepath': doc_data['filepath'],
                            'file_type': doc_data['file_type'],
                            'access_count': doc_data['access_count'],
                            'semantic_similarity': similarity,
                            'matching_chunk': chunk['content'][:200] + '...' if len(chunk['content']) > 200 else chunk['content']
                        }
                    )

                    results.append(memory_item)
                    seen_docs.add(doc_id)

                    if len(results) >= limit:
                        break

            return results

        except Exception as e:
            # Fallback to keyword search if semantic search fails
            return []

    def _keyword_search(self, query: str, limit: int) -> List[MemoryItem]:
        """Perform keyword-based search."""
        results = []
        query_words = query.lower().split()

        for doc_id, doc_data in self.documents.items():
            content_lower = doc_data['content'].lower()
            filepath_lower = doc_data['filepath'].lower()

            # Calculate keyword match score
            matches = sum(1 for word in query_words if word in content_lower or word in filepath_lower)

            if matches > 0:
                confidence = min(1.0, matches / len(query_words))

                memory_item = MemoryItem(
                    content=doc_data['content'],
                    event_time=doc_data['event_time'],
                    ingestion_time=doc_data['ingestion_time'],
                    confidence=confidence,
                    metadata={
                        'doc_id': doc_id,
                        'filepath': doc_data['filepath'],
                        'file_type': doc_data['file_type'],
                        'access_count': doc_data['access_count'],
                        'keyword_matches': matches,
                        'match_type': 'keyword'
                    }
                )

                results.append(memory_item)

        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize DocumentMemory to dictionary."""
        # Convert datetime objects to ISO strings
        documents_data = {}

        for doc_id, doc_data in self.documents.items():
            serialized_doc = doc_data.copy()
            serialized_doc['added_at'] = doc_data['added_at'].isoformat()
            serialized_doc['last_accessed'] = doc_data['last_accessed'].isoformat()
            serialized_doc['ingestion_time'] = doc_data['ingestion_time'].isoformat() if doc_data['ingestion_time'] else None
            serialized_doc['event_time'] = doc_data['event_time'].isoformat() if doc_data['event_time'] else None
            documents_data[doc_id] = serialized_doc

        return {
            'documents': documents_data,
            'file_index': self.file_index,
            'content_hashes': self.content_hashes,
            # Note: chunks and embeddings not serialized (would be too large)
            # They can be regenerated from content if needed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedding_provider=None) -> 'DocumentMemory':
        """Deserialize DocumentMemory from dictionary."""
        instance = cls(embedding_provider=embedding_provider)

        # Restore documents
        documents_data = data.get('documents', {})
        for doc_id, doc_data in documents_data.items():
            # Restore datetime objects
            try:
                doc_data['added_at'] = datetime.fromisoformat(doc_data['added_at'])
                doc_data['last_accessed'] = datetime.fromisoformat(doc_data['last_accessed'])
                doc_data['ingestion_time'] = datetime.fromisoformat(doc_data['ingestion_time']) if doc_data.get('ingestion_time') else None
                doc_data['event_time'] = datetime.fromisoformat(doc_data['event_time']) if doc_data.get('event_time') else None
            except (ValueError, TypeError):
                # Use current time as fallback
                doc_data['added_at'] = datetime.now()
                doc_data['last_accessed'] = datetime.now()
                doc_data['ingestion_time'] = None
                doc_data['event_time'] = None

            instance.documents[doc_id] = doc_data

            # Regenerate chunks if embedding provider available
            if instance.embedding_provider:
                instance._create_document_chunks(doc_id, doc_data['content'])

        # Restore indices
        instance.file_index = data.get('file_index', {})
        instance.content_hashes = data.get('content_hashes', {})

        return instance