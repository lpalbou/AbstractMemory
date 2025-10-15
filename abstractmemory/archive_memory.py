"""
Archive Memory System for AbstractMemory.

The Archive is the AI's "subconscious" - everything it has ever read/learned.
- Every file referenced (@filename) gets stored here permanently
- Tracks access patterns: when learned, last accessed, access count
- Searchable but not actively loaded in context
- Uses semantic relationships and metadata
- Never deleted - grows over time like human long-term memory

Structure:
archive/
├── files/{file_hash}/
│   ├── content.md (full file content)
│   ├── metadata.json (access tracking, semantic info)
│   └── relationships.json (semantic relationships)
├── index/
│   ├── by_path.json (path → file_hash mapping)
│   ├── by_date.json (chronological access)
│   ├── by_frequency.json (most accessed files)
│   └── by_concepts.json (concept → files mapping)
└── stats.json (global archive statistics)
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)


class ArchiveMemory:
    """
    Archive Memory System - AI's subconscious file memory.
    
    Stores every file ever read with comprehensive metadata and access tracking.
    Acts as long-term memory that can be searched but isn't actively loaded.
    """
    
    def __init__(self, base_path: Path, embedding_manager=None, knowledge_graph=None):
        """
        Initialize Archive Memory system.
        
        Args:
            base_path: Base memory path
            embedding_manager: For semantic indexing
            knowledge_graph: For relationship storage
        """
        self.base_path = Path(base_path)
        self.archive_path = self.base_path / "archive"
        self.files_path = self.archive_path / "files"
        self.index_path = self.archive_path / "index"
        
        # Create directory structure
        self.archive_path.mkdir(parents=True, exist_ok=True)
        self.files_path.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        self.embedding_manager = embedding_manager
        self.knowledge_graph = knowledge_graph
        
        # Initialize indices
        self._init_indices()
        
        logger.info(f"📚 [ArchiveMemory] Initialized at {self.archive_path}")
    
    def _init_indices(self):
        """Initialize or load archive indices."""
        
        # Index files
        self.path_index_file = self.index_path / "by_path.json"
        self.date_index_file = self.index_path / "by_date.json"
        self.frequency_index_file = self.index_path / "by_frequency.json"
        self.concepts_index_file = self.index_path / "by_concepts.json"
        self.stats_file = self.archive_path / "stats.json"
        
        # Load or create indices
        self.path_index = self._load_json(self.path_index_file, {})
        self.date_index = self._load_json(self.date_index_file, [])
        self.frequency_index = self._load_json(self.frequency_index_file, {})
        self.concepts_index = self._load_json(self.concepts_index_file, {})
        self.stats = self._load_json(self.stats_file, {
            "total_files": 0,
            "total_accesses": 0,
            "first_file_date": None,
            "last_access_date": None,
            "most_accessed_file": None,
            "unique_concepts": 0
        })
        
        logger.debug(f"📊 [ArchiveMemory] Loaded indices: {self.stats['total_files']} files, {self.stats['total_accesses']} accesses")
    
    def _load_json(self, file_path: Path, default: Any) -> Any:
        """Load JSON file or return default."""
        try:
            if file_path.exists():
                return json.loads(file_path.read_text())
            return default
        except Exception as e:
            logger.warning(f"⚠️  [ArchiveMemory] Failed to load {file_path}: {e}")
            return default
    
    def _save_json(self, file_path: Path, data: Any):
        """Save data to JSON file."""
        try:
            file_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"❌ [ArchiveMemory] Failed to save {file_path}: {e}")
    
    def archive_file(self, file_path: Path, content: str, user_id: str, 
                    access_context: str = "file_reference") -> Dict[str, Any]:
        """
        Archive a file in the subconscious memory system.
        
        Args:
            file_path: Path to the original file
            content: File content
            user_id: User who accessed the file
            access_context: Context of access (file_reference, search, etc.)
            
        Returns:
            Dict: Archive metadata including file_hash, access info
        """
        logger.debug(f"📚 [ArchiveMemory] Archiving file: {file_path}")
        
        # Generate file hash for storage
        file_hash = self._generate_file_hash(file_path, content)
        archive_dir = self.files_path / file_hash
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists in archive
        existing_metadata = self._get_file_metadata(file_hash)
        is_new_file = existing_metadata is None
        
        now = datetime.now().isoformat()
        
        if is_new_file:
            # New file - create full archive entry
            logger.info(f"📥 [ArchiveMemory] New file archived: {file_path.name}")
            
            # Store content
            content_file = archive_dir / "content.md"
            content_file.write_text(content)
            
            # Create metadata
            metadata = {
                "file_hash": file_hash,
                "original_path": str(file_path.resolve()),
                "file_name": file_path.name,
                "file_extension": file_path.suffix.lower(),
                "content_size": len(content),
                "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                
                # Access tracking
                "first_learned": now,
                "last_accessed": now,
                "access_count": 1,
                "accessed_by_users": [user_id],
                "access_contexts": [access_context],
                
                # Semantic information
                "concepts": self._extract_concepts(file_path, content),
                "semantic_type": self._determine_semantic_type(file_path),
                "language": self._detect_language(file_path),
                
                # Archive metadata
                "archive_created": now,
                "archive_version": "1.0"
            }
            
            # Update global stats
            self.stats["total_files"] += 1
            if self.stats["first_file_date"] is None:
                self.stats["first_file_date"] = now
            
        else:
            # Existing file - update access tracking
            logger.info(f"🔄 [ArchiveMemory] File re-accessed: {file_path.name}")
            metadata = existing_metadata.copy()
            
            # Update access tracking
            metadata["last_accessed"] = now
            metadata["access_count"] += 1
            
            # Track unique users and contexts
            if user_id not in metadata["accessed_by_users"]:
                metadata["accessed_by_users"].append(user_id)
            if access_context not in metadata["access_contexts"]:
                metadata["access_contexts"].append(access_context)
        
        # Save metadata
        metadata_file = archive_dir / "metadata.json"
        self._save_json(metadata_file, metadata)
        
        # Create/update semantic relationships
        relationships = self._create_semantic_relationships(metadata, user_id)
        relationships_file = archive_dir / "relationships.json"
        self._save_json(relationships_file, relationships)
        
        # Update indices
        self._update_indices(file_hash, metadata)
        
        # Update global stats
        self.stats["total_accesses"] += 1
        self.stats["last_access_date"] = now
        self._update_most_accessed(file_hash, metadata["access_count"])
        self._save_json(self.stats_file, self.stats)
        
        logger.info(f"✅ [ArchiveMemory] File archived: {file_hash} (access #{metadata['access_count']})")
        
        return {
            "file_hash": file_hash,
            "is_new_file": is_new_file,
            "access_count": metadata["access_count"],
            "concepts": metadata["concepts"],
            "archive_path": str(archive_dir)
        }
    
    def _generate_file_hash(self, file_path: Path, content: str) -> str:
        """Generate unique hash for file based on path and content."""
        # Use path + content hash to handle file moves and content changes
        path_str = str(file_path.resolve())
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        path_hash = hashlib.sha256(path_str.encode()).hexdigest()[:8]
        
        return f"{path_hash}_{content_hash}"
    
    def _get_file_metadata(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Get existing file metadata if it exists."""
        metadata_file = self.files_path / file_hash / "metadata.json"
        if metadata_file.exists():
            return self._load_json(metadata_file, None)
        return None
    
    def _extract_concepts(self, file_path: Path, content: str) -> List[str]:
        """Extract concepts from file path and content."""
        concepts = []
        
        # Extract from filename
        filename_parts = file_path.stem.replace('_', ' ').replace('-', ' ').split()
        concepts.extend(filename_parts)
        
        # Extract from directory structure
        for part in file_path.parts[:-1]:
            if part not in ['.', '..', '/', '\\']:
                dir_parts = part.replace('_', ' ').replace('-', ' ').split()
                concepts.extend(dir_parts)
        
        # Extract from content (simple keyword extraction)
        if file_path.suffix.lower() in ['.md', '.txt', '.rst']:
            # For text files, extract from headers and first lines
            lines = content.split('\n')[:10]  # First 10 lines
            for line in lines:
                if line.startswith('#') or line.startswith('##'):
                    # Markdown headers
                    header_text = line.lstrip('#').strip()
                    concepts.extend(header_text.split())
        
        # Filter and clean concepts
        filtered_concepts = []
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        
        for concept in concepts:
            clean_concept = concept.lower().strip('.,!?()[]{}":;')
            if len(clean_concept) > 2 and clean_concept not in common_words and clean_concept.isalpha():
                filtered_concepts.append(clean_concept)
        
        return list(set(filtered_concepts))  # Remove duplicates
    
    def _determine_semantic_type(self, file_path: Path) -> str:
        """Determine semantic type using Dublin Core Terms."""
        ext = file_path.suffix.lower()
        
        if ext in ['.md', '.txt', '.rst']:
            return 'dcterms:Text'
        elif ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.go']:
            return 'schema:SoftwareSourceCode'
        elif ext in ['.json', '.xml', '.yaml', '.yml', '.csv']:
            return 'schema:Dataset'
        elif ext in ['.html', '.htm']:
            return 'schema:WebPage'
        else:
            return 'dcterms:Text'
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming/markup language."""
        ext = file_path.suffix.lower()
        
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
            '.rs': 'rust', '.go': 'go', '.rb': 'ruby', '.php': 'php',
            '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
            '.md': 'markdown', '.txt': 'text', '.sh': 'bash',
            '.sql': 'sql', '.r': 'r', '.m': 'matlab'
        }
        
        return lang_map.get(ext, 'text')
    
    def _create_semantic_relationships(self, metadata: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create semantic relationships for the archived file."""
        
        relationships = {
            "user_relationships": [],
            "concept_relationships": [],
            "file_relationships": [],
            "temporal_relationships": []
        }
        
        file_hash = metadata["file_hash"]
        
        # User relationships
        relationships["user_relationships"].append({
            "type": "dcterms:creator",
            "subject": f"ex:person-{user_id}",
            "predicate": "dcterms:references",
            "object": f"ex:archived-file-{file_hash}",
            "confidence": 0.95,
            "created": datetime.now().isoformat()
        })
        
        # Concept relationships
        for concept in metadata["concepts"]:
            relationships["concept_relationships"].append({
                "type": "schema:about",
                "subject": f"ex:archived-file-{file_hash}",
                "predicate": "schema:about",
                "object": f"ex:concept-{concept}",
                "confidence": 0.7,
                "created": datetime.now().isoformat()
            })
        
        # Store in knowledge graph if available
        if self.knowledge_graph:
            try:
                from abstractmemory.storage.knowledge_graph import GraphTriple
                
                # Add to knowledge graph
                for rel in relationships["user_relationships"]:
                    triple = GraphTriple(
                        subject=rel["subject"],
                        predicate=rel["predicate"],
                        object=rel["object"],
                        confidence=rel["confidence"],
                        timestamp=datetime.now(),
                        source="archive_memory",
                        importance=0.6,
                        relationship_type="structural"
                    )
                    self.knowledge_graph.add_triple(triple)
                
                logger.debug(f"🕸️  [ArchiveMemory] Added relationships to knowledge graph")
                
            except Exception as e:
                logger.warning(f"⚠️  [ArchiveMemory] Failed to add to knowledge graph: {e}")
        
        return relationships
    
    def _update_indices(self, file_hash: str, metadata: Dict[str, Any]):
        """Update all archive indices."""
        
        # Path index
        original_path = metadata["original_path"]
        self.path_index[original_path] = file_hash
        self._save_json(self.path_index_file, self.path_index)
        
        # Date index (chronological access)
        date_entry = {
            "file_hash": file_hash,
            "file_name": metadata["file_name"],
            "accessed": metadata["last_accessed"],
            "access_count": metadata["access_count"]
        }
        
        # Remove old entry if exists
        self.date_index = [entry for entry in self.date_index if entry["file_hash"] != file_hash]
        self.date_index.append(date_entry)
        self.date_index.sort(key=lambda x: x["accessed"], reverse=True)
        self._save_json(self.date_index_file, self.date_index)
        
        # Frequency index
        self.frequency_index[file_hash] = {
            "file_name": metadata["file_name"],
            "access_count": metadata["access_count"],
            "last_accessed": metadata["last_accessed"]
        }
        self._save_json(self.frequency_index_file, self.frequency_index)
        
        # Concepts index
        for concept in metadata["concepts"]:
            if concept not in self.concepts_index:
                self.concepts_index[concept] = []
            
            # Remove old entry if exists
            self.concepts_index[concept] = [
                entry for entry in self.concepts_index[concept] 
                if entry["file_hash"] != file_hash
            ]
            
            # Add updated entry
            self.concepts_index[concept].append({
                "file_hash": file_hash,
                "file_name": metadata["file_name"],
                "access_count": metadata["access_count"]
            })
        
        self._save_json(self.concepts_index_file, self.concepts_index)
        
        # Update unique concepts count
        self.stats["unique_concepts"] = len(self.concepts_index)
    
    def _update_most_accessed(self, file_hash: str, access_count: int):
        """Update most accessed file tracking."""
        current_most = self.stats.get("most_accessed_file")
        
        if current_most is None or access_count > current_most.get("access_count", 0):
            self.stats["most_accessed_file"] = {
                "file_hash": file_hash,
                "access_count": access_count
            }
    
    def search_archive(self, query: str, search_type: str = "content", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search the archive memory.
        
        Args:
            query: Search query
            search_type: Type of search (content, concepts, path, recent)
            limit: Maximum results
            
        Returns:
            List of matching archive entries
        """
        logger.debug(f"🔍 [ArchiveMemory] Searching archive: '{query}' (type: {search_type})")
        
        results = []
        
        if search_type == "concepts":
            # Search by concepts
            query_lower = query.lower()
            for concept, files in self.concepts_index.items():
                if query_lower in concept:
                    for file_info in files:
                        metadata = self._get_file_metadata(file_info["file_hash"])
                        if metadata:
                            results.append({
                                "file_hash": file_info["file_hash"],
                                "file_name": metadata["file_name"],
                                "original_path": metadata["original_path"],
                                "access_count": metadata["access_count"],
                                "last_accessed": metadata["last_accessed"],
                                "match_type": "concept",
                                "match_value": concept
                            })
        
        elif search_type == "path":
            # Search by file path
            query_lower = query.lower()
            for path, file_hash in self.path_index.items():
                if query_lower in path.lower():
                    metadata = self._get_file_metadata(file_hash)
                    if metadata:
                        results.append({
                            "file_hash": file_hash,
                            "file_name": metadata["file_name"],
                            "original_path": metadata["original_path"],
                            "access_count": metadata["access_count"],
                            "last_accessed": metadata["last_accessed"],
                            "match_type": "path",
                            "match_value": path
                        })
        
        elif search_type == "recent":
            # Return recent files
            results = []
            for entry in self.date_index[:limit]:
                metadata = self._get_file_metadata(entry["file_hash"])
                if metadata:
                    results.append({
                        "file_hash": entry["file_hash"],
                        "file_name": metadata["file_name"],
                        "original_path": metadata["original_path"],
                        "access_count": metadata["access_count"],
                        "last_accessed": metadata["last_accessed"],
                        "match_type": "recent",
                        "match_value": metadata["last_accessed"]
                    })
        
        elif search_type == "frequent":
            # Return most frequently accessed files
            sorted_files = sorted(
                self.frequency_index.items(),
                key=lambda x: x[1]["access_count"],
                reverse=True
            )
            
            for file_hash, file_info in sorted_files[:limit]:
                metadata = self._get_file_metadata(file_hash)
                if metadata:
                    results.append({
                        "file_hash": file_hash,
                        "file_name": metadata["file_name"],
                        "original_path": metadata["original_path"],
                        "access_count": metadata["access_count"],
                        "last_accessed": metadata["last_accessed"],
                        "match_type": "frequent",
                        "match_value": metadata["access_count"]
                    })
        
        # Sort results by relevance (access count + recency)
        results.sort(key=lambda x: (x["access_count"], x["last_accessed"]), reverse=True)
        
        logger.info(f"🔍 [ArchiveMemory] Found {len(results)} archive matches")
        return results[:limit]
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """Get comprehensive archive statistics."""
        
        # Calculate additional stats
        if self.frequency_index:
            avg_access_count = sum(info["access_count"] for info in self.frequency_index.values()) / len(self.frequency_index)
            max_access_count = max(info["access_count"] for info in self.frequency_index.values())
        else:
            avg_access_count = 0
            max_access_count = 0
        
        stats = self.stats.copy()
        stats.update({
            "average_access_count": round(avg_access_count, 2),
            "max_access_count": max_access_count,
            "archive_size_mb": self._calculate_archive_size(),
            "top_concepts": self._get_top_concepts(5),
            "recent_files": len([entry for entry in self.date_index if self._is_recent(entry["accessed"])])
        })
        
        return stats
    
    def _calculate_archive_size(self) -> float:
        """Calculate total archive size in MB."""
        try:
            total_size = 0
            for file_dir in self.files_path.iterdir():
                if file_dir.is_dir():
                    for file in file_dir.rglob("*"):
                        if file.is_file():
                            total_size += file.stat().st_size
            return round(total_size / (1024 * 1024), 2)
        except Exception:
            return 0.0
    
    def _get_top_concepts(self, limit: int) -> List[Dict[str, Any]]:
        """Get top concepts by file count."""
        concept_counts = [
            {"concept": concept, "file_count": len(files)}
            for concept, files in self.concepts_index.items()
        ]
        concept_counts.sort(key=lambda x: x["file_count"], reverse=True)
        return concept_counts[:limit]
    
    def _is_recent(self, date_str: str, days: int = 7) -> bool:
        """Check if date is within recent days."""
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            now = datetime.now()
            return (now - date).days <= days
        except Exception:
            return False
    
    def get_all_files(self, sort_by: str = "last_accessed", limit: int = None) -> List[Dict[str, Any]]:
        """
        Get all archived files with metadata for table display.
        
        Args:
            sort_by: Sort criteria (last_accessed, access_count, file_name, size)
            limit: Maximum number of files to return
            
        Returns:
            List of file metadata dictionaries
        """
        logger.debug(f"📋 [ArchiveMemory] Getting all files (sort: {sort_by}, limit: {limit})")
        
        files = []
        
        # Get all files from path index
        for original_path, file_hash in self.path_index.items():
            metadata = self._get_file_metadata(file_hash)
            if metadata:
                # Calculate file size in KB/MB
                size_bytes = metadata.get("content_size", 0)
                if size_bytes < 1024:
                    size_display = f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    size_display = f"{size_bytes/1024:.1f}KB"
                else:
                    size_display = f"{size_bytes/(1024*1024):.1f}MB"
                
                # Format dates
                last_accessed = metadata.get("last_accessed", "")
                if last_accessed:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                        last_accessed_display = dt.strftime("%m-%d %H:%M")
                    except:
                        last_accessed_display = last_accessed[:10]
                else:
                    last_accessed_display = "Unknown"
                
                first_learned = metadata.get("first_learned", "")
                if first_learned:
                    try:
                        dt = datetime.fromisoformat(first_learned.replace('Z', '+00:00'))
                        first_learned_display = dt.strftime("%m-%d %H:%M")
                    except:
                        first_learned_display = first_learned[:10]
                else:
                    first_learned_display = "Unknown"
                
                files.append({
                    "file_hash": file_hash,
                    "file_name": metadata.get("file_name", "Unknown"),
                    "original_path": original_path,
                    "size_display": size_display,
                    "size_bytes": size_bytes,
                    "access_count": metadata.get("access_count", 0),
                    "last_accessed": last_accessed,
                    "last_accessed_display": last_accessed_display,
                    "first_learned": first_learned,
                    "first_learned_display": first_learned_display,
                    "file_extension": metadata.get("file_extension", ""),
                    "semantic_type": metadata.get("semantic_type", "unknown"),
                    "concepts_count": len(metadata.get("concepts", [])),
                    "users_count": len(metadata.get("accessed_by_users", []))
                })
        
        # Sort files
        if sort_by == "last_accessed":
            files.sort(key=lambda x: x["last_accessed"], reverse=True)
        elif sort_by == "access_count":
            files.sort(key=lambda x: x["access_count"], reverse=True)
        elif sort_by == "file_name":
            files.sort(key=lambda x: x["file_name"].lower())
        elif sort_by == "size":
            files.sort(key=lambda x: x["size_bytes"], reverse=True)
        elif sort_by == "first_learned":
            files.sort(key=lambda x: x["first_learned"], reverse=True)
        
        # Apply limit
        if limit:
            files = files[:limit]
        
        logger.debug(f"📋 [ArchiveMemory] Returning {len(files)} files")
        return files
