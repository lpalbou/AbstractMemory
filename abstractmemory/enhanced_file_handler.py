"""
Enhanced File Reference Handler for AbstractMemory.

Handles @filename references with:
1. Semantic storage in filesystem with metadata
2. LanceDB indexing for semantic search
3. Knowledge Graph relationships using semantic models
4. Typed relationships from AbstractCore semantic models
"""

import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from abstractllm.utils.structured_logging import get_logger

logger = get_logger(__name__)


class EnhancedFileHandler:
    """Enhanced file reference handler with semantic storage and KG relationships."""
    
    def __init__(self, memory_session, triple_storage_manager=None):
        """
        Initialize enhanced file handler.
        
        Args:
            memory_session: MemorySession instance
            triple_storage_manager: TripleStorageManager for cross-layer storage
        """
        self.memory_session = memory_session
        self.triple_storage_manager = triple_storage_manager
        self.base_path = memory_session.memory_base_path
        self.library_path = self.base_path / "library"
        
        # Initialize Archive Memory (AI's subconscious)
        from abstractmemory.archive_memory import ArchiveMemory
        self.archive_memory = ArchiveMemory(
            base_path=self.base_path,
            embedding_manager=getattr(memory_session, 'embedding_manager', None),
            knowledge_graph=getattr(triple_storage_manager, 'knowledge_graph', None) if triple_storage_manager else None
        )
        
        # Semantic relationship types from AbstractCore semantic models
        self.semantic_relationships = {
            # Document relationships (Dublin Core Terms)
            'references': 'dcterms:references',
            'is_referenced_by': 'dcterms:isReferencedBy',
            'is_part_of': 'dcterms:isPartOf',
            'has_part': 'dcterms:hasPart',
            'requires': 'dcterms:requires',
            'is_required_by': 'dcterms:isRequiredBy',
            
            # Content relationships (Schema.org)
            'mentions': 'schema:mentions',
            'is_mentioned_in': 'schema:mentionedIn',
            'about': 'schema:about',
            'describes': 'schema:describes',
            'illustrates': 'schema:illustrates',
            'explains': 'schema:explains',
            
            # Evidential relationships (CiTO)
            'supports': 'cito:supports',
            'is_supported_by': 'cito:isSupportedBy',
            'discusses': 'cito:discusses',
            'is_discussed_by': 'cito:isDiscussedBy',
            'uses_data_from': 'cito:usesDataFrom',
            'provides_data_for': 'cito:providesDataFor'
        }
        
        logger.debug("🔧 [EnhancedFileHandler] Initialized with semantic relationships")
    
    def process_file_references(self, user_input: str, user_id: str, location: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process @filename references with enhanced semantic storage.
        
        Args:
            user_input: Raw user input with @filename references
            user_id: User identifier
            location: Location context
            
        Returns:
            Tuple of (enhanced_prompt, processed_files_metadata)
        """
        logger.debug(f"🔍 [EnhancedFileHandler] Processing file references in user input")
        
        # Find all @filename patterns
        pattern = r'@([^\s@]+(?:\.[^\s@]*)?)'
        matches = re.findall(pattern, user_input)
        
        if not matches:
            logger.debug("ℹ️  [EnhancedFileHandler] No file references found")
            return user_input, []
        
        logger.debug(f"📁 [EnhancedFileHandler] Found {len(matches)} file references: {matches}")
        
        # Process each file reference
        file_contents = []
        processed_files = []
        
        for filename in matches:
            try:
                file_metadata = self._process_single_file(filename, user_id, location)
                if file_metadata:
                    file_contents.append(file_metadata['formatted_content'])
                    processed_files.append(file_metadata)
                    
            except Exception as e:
                logger.error(f"❌ [EnhancedFileHandler] Error processing {filename}: {e}")
                continue
        
        # Create enhanced prompt
        if file_contents:
            enhanced_prompt = f"{user_input}\n\n{''.join(file_contents)}"
            logger.info(f"✅ [EnhancedFileHandler] Enhanced prompt with {len(processed_files)} files")
        else:
            enhanced_prompt = user_input
            logger.debug("ℹ️  [EnhancedFileHandler] No files successfully processed")
        
        return enhanced_prompt, processed_files
    
    def _process_single_file(self, filename: str, user_id: str, location: str) -> Optional[Dict[str, Any]]:
        """Process a single file reference with semantic storage."""
        
        logger.debug(f"📄 [EnhancedFileHandler] Processing file: {filename}")
        
        # Resolve file path
        file_path = self._resolve_file_path(filename)
        if not file_path:
            return None
        
        # Read file content
        try:
            content = file_path.read_text(encoding='utf-8')
            logger.debug(f"📖 [EnhancedFileHandler] Read {len(content)} chars from {file_path}")
        except Exception as e:
            logger.error(f"❌ [EnhancedFileHandler] Cannot read file {file_path}: {e}")
            return None
        
        # Generate document ID
        doc_id = self._generate_document_id(file_path, content)
        
        # Extract metadata
        metadata = self._extract_file_metadata(file_path, content, user_id, location)
        
        # 1. ARCHIVE FIRST: Store in Archive Memory (AI's subconscious)
        archive_result = self.archive_memory.archive_file(
            file_path=file_path,
            content=content,
            user_id=user_id,
            access_context="file_reference"
        )
        
        logger.info(f"📚 [EnhancedFileHandler] File archived: {archive_result['file_hash']} "
                   f"({'new' if archive_result['is_new_file'] else 'existing'}, "
                   f"access #{archive_result['access_count']})")
        
        # 2. Store in triple storage system (active memory)
        storage_ids = self._store_in_triple_storage(doc_id, content, metadata)
        
        # 3. Create knowledge graph relationships
        self._create_semantic_relationships(doc_id, metadata, user_id)
        
        # Format content for prompt injection
        formatted_content = self._format_file_content(file_path, content)
        
        return {
            'doc_id': doc_id,
            'file_path': str(file_path),
            'content': content,
            'metadata': metadata,
            'storage_ids': storage_ids,
            'archive_result': archive_result,
            'formatted_content': formatted_content
        }
    
    def _resolve_file_path(self, filename: str) -> Optional[Path]:
        """Resolve filename to actual file path."""
        
        try:
            # Handle different path types
            if filename.startswith('/'):
                # Absolute path
                file_path = Path(filename)
            elif filename.startswith('./') or filename.startswith('../'):
                # Relative path with explicit prefix
                file_path = Path(filename).resolve()
            else:
                # Simple filename - look in current directory first, then workspace
                file_path = Path(filename)
                if not file_path.exists():
                    # Try in workspace root
                    workspace_path = Path.cwd() / filename
                    if workspace_path.exists():
                        file_path = workspace_path
            
            # Validate file
            if not file_path.exists():
                logger.warning(f"⚠️  [EnhancedFileHandler] File not found: {filename}")
                return None
            
            if not file_path.is_file():
                logger.warning(f"⚠️  [EnhancedFileHandler] Not a file: {filename}")
                return None
            
            # Check file size (limit to 1MB for safety)
            file_size = file_path.stat().st_size
            if file_size > 1024 * 1024:  # 1MB
                logger.warning(f"⚠️  [EnhancedFileHandler] File too large (>{file_size/1024/1024:.1f}MB): {filename}")
                return None
            
            return file_path
            
        except Exception as e:
            logger.error(f"❌ [EnhancedFileHandler] Error resolving path {filename}: {e}")
            return None
    
    def _generate_document_id(self, file_path: Path, content: str) -> str:
        """Generate unique document ID based on path and content hash."""
        
        # Create hash from path and content
        path_str = str(file_path.resolve())
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]
        path_hash = hashlib.sha256(path_str.encode('utf-8')).hexdigest()[:8]
        
        doc_id = f"doc_{path_hash}_{content_hash}"
        logger.debug(f"🆔 [EnhancedFileHandler] Generated document ID: {doc_id}")
        
        return doc_id
    
    def _extract_file_metadata(self, file_path: Path, content: str, user_id: str, location: str) -> Dict[str, Any]:
        """Extract comprehensive metadata from file."""
        
        stat = file_path.stat()
        now = datetime.now().isoformat()
        
        # Determine file type and language
        file_ext = file_path.suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
            '.rs': 'rust', '.go': 'go', '.rb': 'ruby', '.php': 'php',
            '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
            '.md': 'markdown', '.txt': 'text', '.sh': 'bash',
            '.sql': 'sql', '.r': 'r', '.m': 'matlab'
        }
        language = lang_map.get(file_ext, 'text')
        
        # Extract semantic type based on Dublin Core Terms
        semantic_type = self._determine_semantic_type(file_path, content)
        
        metadata = {
            # Dublin Core Terms metadata
            'dcterms:identifier': str(file_path.resolve()),
            'dcterms:title': file_path.name,
            'dcterms:description': f"File referenced in conversation by {user_id}",
            'dcterms:created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'dcterms:modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'dcterms:format': f"text/{language}",
            'dcterms:extent': len(content),
            
            # Schema.org metadata
            'schema:name': file_path.name,
            'schema:encodingFormat': f"text/{language}",
            'schema:contentSize': len(content),
            
            # AbstractMemory specific
            'file_path': str(file_path.resolve()),
            'file_name': file_path.name,
            'file_extension': file_ext,
            'language': language,
            'semantic_type': semantic_type,
            'size_bytes': stat.st_size,
            'accessed_by': user_id,
            'accessed_at': now,
            'access_location': location,
            'access_context': 'file_reference'
        }
        
        logger.debug(f"📊 [EnhancedFileHandler] Extracted metadata for {file_path.name}")
        return metadata
    
    def _determine_semantic_type(self, file_path: Path, content: str) -> str:
        """Determine semantic type using Dublin Core Terms."""
        
        # Map file types to Dublin Core Terms
        if file_path.suffix.lower() in ['.md', '.txt', '.rst']:
            return 'dcterms:Text'
        elif file_path.suffix.lower() in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.go']:
            return 'schema:SoftwareSourceCode'
        elif file_path.suffix.lower() in ['.json', '.xml', '.yaml', '.yml', '.csv']:
            return 'schema:Dataset'
        elif file_path.suffix.lower() in ['.html', '.htm']:
            return 'schema:WebPage'
        else:
            return 'dcterms:Text'  # Default to text document
    
    def _store_in_triple_storage(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Store document in triple storage system."""
        
        if not self.triple_storage_manager:
            logger.debug("⚠️  [EnhancedFileHandler] No triple storage manager available")
            return {}
        
        logger.debug(f"💾 [EnhancedFileHandler] Storing document in triple storage: {doc_id}")
        
        # Use the high-level remember() interface
        storage_ids = self.triple_storage_manager.remember(
            content=content,
            item_type="document",
            user_id=metadata.get('accessed_by', 'unknown'),
            location=metadata.get('access_location', 'unknown'),
            importance=0.8,  # Files referenced are generally important
            metadata=metadata,
            relationships=[]  # Will be added separately
        )
        
        logger.debug(f"✅ [EnhancedFileHandler] Document stored across {len(storage_ids)} layers")
        return storage_ids
    
    def _create_semantic_relationships(self, doc_id: str, metadata: Dict[str, Any], user_id: str):
        """Create semantic relationships in knowledge graph."""
        
        if not self.triple_storage_manager or not self.triple_storage_manager.knowledge_graph:
            logger.debug("⚠️  [EnhancedFileHandler] No knowledge graph available for relationships")
            return
        
        logger.debug(f"🕸️  [EnhancedFileHandler] Creating semantic relationships for {doc_id}")
        
        try:
            from abstractmemory.storage.knowledge_graph import GraphTriple
            
            # Create document entity
            doc_entity = f"ex:document-{doc_id}"
            user_entity = f"ex:person-{user_id}"
            
            # Create relationships
            relationships = []
            
            # 1. User references document (dcterms:references)
            relationships.append(GraphTriple(
                subject=user_entity,
                predicate='dcterms:references',
                object=doc_entity,
                confidence=0.95,
                timestamp=datetime.now(),
                source='file_reference',
                importance=0.8,
                relationship_type='structural'
            ))
            
            # 2. Document is referenced by user (inverse)
            relationships.append(GraphTriple(
                subject=doc_entity,
                predicate='dcterms:isReferencedBy',
                object=user_entity,
                confidence=0.95,
                timestamp=datetime.now(),
                source='file_reference',
                importance=0.8,
                relationship_type='structural'
            ))
            
            # 3. Document describes/explains concepts (if code file)
            if metadata.get('semantic_type') == 'schema:SoftwareSourceCode':
                # Extract concepts from filename/path
                concepts = self._extract_concepts_from_path(metadata['file_path'])
                for concept in concepts:
                    concept_entity = f"ex:concept-{concept.lower().replace(' ', '-')}"
                    
                    relationships.append(GraphTriple(
                        subject=doc_entity,
                        predicate='schema:about',
                        object=concept_entity,
                        confidence=0.7,
                        timestamp=datetime.now(),
                        source='file_reference',
                        importance=0.6,
                        relationship_type='content'
                    ))
            
            # Store relationships in knowledge graph
            for relationship in relationships:
                self.triple_storage_manager.knowledge_graph.add_triple(relationship)
            
            logger.info(f"✅ [EnhancedFileHandler] Created {len(relationships)} semantic relationships")
            
        except Exception as e:
            logger.error(f"❌ [EnhancedFileHandler] Error creating semantic relationships: {e}")
    
    def _extract_concepts_from_path(self, file_path: str) -> List[str]:
        """Extract concepts from file path for semantic relationships."""
        
        path = Path(file_path)
        concepts = []
        
        # Extract from filename (remove extension)
        filename_parts = path.stem.replace('_', ' ').replace('-', ' ').split()
        concepts.extend(filename_parts)
        
        # Extract from directory names
        for part in path.parts[:-1]:  # Exclude filename
            if part not in ['.', '..', '/', '\\']:
                dir_parts = part.replace('_', ' ').replace('-', ' ').split()
                concepts.extend(dir_parts)
        
        # Filter out common words and short words
        filtered_concepts = []
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        for concept in concepts:
            if len(concept) > 2 and concept.lower() not in common_words:
                filtered_concepts.append(concept)
        
        return list(set(filtered_concepts))  # Remove duplicates
    
    def _format_file_content(self, file_path: Path, content: str) -> str:
        """Format file content for prompt injection."""
        
        # Determine language for syntax highlighting
        file_ext = file_path.suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
            '.rs': 'rust', '.go': 'go', '.rb': 'ruby', '.php': 'php',
            '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
            '.md': 'markdown', '.txt': 'text', '.sh': 'bash',
            '.sql': 'sql', '.r': 'r', '.m': 'matlab'
        }
        language = lang_map.get(file_ext, 'text')
        
        # Format with semantic metadata
        formatted_content = f"""

[Referenced File: {file_path}]
Type: {language} | Size: {len(content)} chars | Semantic Type: Document
```{language}
{content}
```
"""
        
        return formatted_content
