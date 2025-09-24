"""
LanceDB Storage Backend with SQL + Vector Search via AbstractCore embeddings.
Provides powerful querying capabilities for AI memory.
"""

import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from ..core.interfaces import IStorage
from ..embeddings import create_embedding_adapter

logger = logging.getLogger(__name__)

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logger.warning("LanceDB not available. Install with: pip install lancedb")


class LanceDBStorage(IStorage):
    """
    LanceDB storage with vector embeddings from AbstractCore.

    Tables:
    - interactions: Verbatim user-agent interactions with embeddings
    - experiential_notes: AI reflections and insights with embeddings
    - links: Bidirectional relationships between interactions and notes
    - memory_components: Snapshots of memory components
    """

    def __init__(self, uri: str, embedding_provider: Optional[Any] = None):
        """
        Initialize LanceDB storage.

        Args:
            uri: LanceDB connection URI (e.g., "./lance.db")
            embedding_provider: AbstractCore instance for generating embeddings

        Raises:
            ImportError: If LanceDB is not installed
            ValueError: If no embedding provider is provided
        """
        if not LANCEDB_AVAILABLE:
            raise ImportError("LanceDB is required but not installed. Install with: pip install lancedb")

        if embedding_provider is None:
            raise ValueError(
                "LanceDB storage requires a real embedding provider for semantic search. "
                "Please provide an AbstractCore EmbeddingManager or other embedding provider."
            )

        self.uri = uri
        self.embedding_adapter = create_embedding_adapter(embedding_provider)
        self.db = lancedb.connect(uri)

        # Initialize tables and check embedding consistency
        self._init_tables()
        self._check_embedding_consistency()

    def _init_tables(self):
        """Initialize LanceDB tables with schemas"""

        # Interactions table schema
        interactions_schema = [
            {"name": "id", "type": "string"},
            {"name": "user_id", "type": "string"},
            {"name": "timestamp", "type": "timestamp"},
            {"name": "user_input", "type": "string"},
            {"name": "agent_response", "type": "string"},
            {"name": "topic", "type": "string"},
            {"name": "metadata", "type": "string"},  # JSON string
            {"name": "embedding", "type": "vector"}  # Vector embedding
        ]

        # Experiential notes table schema
        notes_schema = [
            {"name": "id", "type": "string"},
            {"name": "timestamp", "type": "timestamp"},
            {"name": "reflection", "type": "string"},
            {"name": "interaction_id", "type": "string"},
            {"name": "note_type", "type": "string"},
            {"name": "metadata", "type": "string"},  # JSON string
            {"name": "embedding", "type": "vector"}  # Vector embedding
        ]

        # Links table schema
        links_schema = [
            {"name": "interaction_id", "type": "string"},
            {"name": "note_id", "type": "string"},
            {"name": "created", "type": "timestamp"},
            {"name": "link_type", "type": "string"}
        ]

        # Memory components table schema
        components_schema = [
            {"name": "component_name", "type": "string"},
            {"name": "timestamp", "type": "timestamp"},
            {"name": "data", "type": "string"},  # JSON string
            {"name": "version", "type": "int64"}
        ]

        # Create tables if they don't exist
        import pandas as pd

        try:
            self.interactions_table = self.db.open_table("interactions")
        except (FileNotFoundError, ValueError):
            # Create table with proper schema and sample data
            import pyarrow as pa

            # Get actual embedding dimension from adapter
            test_embedding = self.embedding_adapter.generate_embedding("test")
            embedding_dim = len(test_embedding)

            # Create proper schema with fixed-size list for embeddings
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("timestamp", pa.timestamp('us')),
                pa.field("user_input", pa.string()),
                pa.field("agent_response", pa.string()),
                pa.field("topic", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field("embedding", pa.list_(pa.float32(), embedding_dim))
            ])

            # Create empty table with proper schema
            self.interactions_table = self.db.create_table("interactions", schema=schema)

        try:
            self.notes_table = self.db.open_table("experiential_notes")
        except (FileNotFoundError, ValueError):
            # Create notes table with proper schema
            notes_schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("timestamp", pa.timestamp('us')),
                pa.field("reflection", pa.string()),
                pa.field("interaction_id", pa.string()),
                pa.field("note_type", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field("embedding", pa.list_(pa.float32(), embedding_dim))
            ])
            self.notes_table = self.db.create_table("experiential_notes", schema=notes_schema)

        try:
            self.links_table = self.db.open_table("links")
        except (FileNotFoundError, ValueError):
            sample_data = pd.DataFrame([{
                "interaction_id": "sample_int",
                "note_id": "sample_note",
                "created": datetime.now(),
                "link_type": "bidirectional"
            }])
            self.links_table = self.db.create_table("links", sample_data)
            self.links_table.delete("interaction_id = 'sample_int'")

        try:
            self.components_table = self.db.open_table("memory_components")
        except (FileNotFoundError, ValueError):
            sample_data = pd.DataFrame([{
                "component_name": "sample",
                "timestamp": datetime.now(),
                "data": "{}",
                "version": 1
            }])
            self.components_table = self.db.create_table("memory_components", sample_data)
            self.components_table.delete("component_name = 'sample'")

        # Embedding metadata table for consistency tracking
        try:
            self.embedding_metadata_table = self.db.open_table("embedding_metadata")
        except (FileNotFoundError, ValueError):
            sample_data = pd.DataFrame([{
                "key": "sample",
                "value": "{}",
                "created_at": datetime.now()
            }])
            self.embedding_metadata_table = self.db.create_table("embedding_metadata", sample_data)
            self.embedding_metadata_table.delete("key = 'sample'")

    def _check_embedding_consistency(self) -> None:
        """Check for embedding model consistency with previously stored data."""
        try:
            # Get current embedding model info
            current_info = self.embedding_adapter.get_embedding_info()

            # Try to retrieve previously stored embedding info
            stored_info_df = self.embedding_metadata_table.search().where("key = 'embedding_model_info'").to_pandas()

            if len(stored_info_df) > 0:
                # We have previously stored embedding info
                import json
                stored_info = json.loads(stored_info_df.iloc[0]['value'])

                # Check consistency and warn if needed
                self.embedding_adapter.warn_about_consistency(stored_info)
            else:
                # First time - store the current embedding info
                self._store_embedding_info(current_info)
                logger.info(f"Stored embedding model info for consistency tracking: {current_info}")

        except Exception as e:
            logger.warning(f"Failed to check embedding consistency: {e}")

    def _store_embedding_info(self, embedding_info: dict) -> None:
        """Store embedding model information for consistency tracking."""
        try:
            import json
            import pandas as pd

            # Delete any existing embedding_model_info records
            try:
                self.embedding_metadata_table.delete("key = 'embedding_model_info'")
            except:
                pass  # Table might be empty

            # Store new info
            data = pd.DataFrame([{
                "key": "embedding_model_info",
                "value": json.dumps(embedding_info),
                "created_at": datetime.now()
            }])

            self.embedding_metadata_table.add(data)
            logger.debug(f"Stored embedding model info: {embedding_info}")

        except Exception as e:
            logger.error(f"Failed to store embedding info: {e}")

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using embedding adapter"""
        return self.embedding_adapter.generate_embedding(text)

    def save_interaction(self, user_id: str, timestamp: datetime,
                        user_input: str, agent_response: str,
                        topic: str, metadata: Optional[Dict] = None) -> str:
        """Save verbatim interaction with vector embedding"""

        interaction_id = f"int_{uuid.uuid4().hex[:8]}"

        # Generate embedding for the full interaction
        interaction_text = f"{user_input} {agent_response}"
        embedding = self._generate_embedding(interaction_text)

        # Prepare data
        import json
        import pandas as pd

        data = {
            "id": interaction_id,
            "user_id": user_id,
            "timestamp": timestamp,
            "user_input": user_input,
            "agent_response": agent_response,
            "topic": topic,
            "metadata": json.dumps(metadata or {}),
            "embedding": [float(x) for x in embedding]  # Ensure float32 compatibility
        }

        # Insert into table
        df = pd.DataFrame([data])

        try:
            self.interactions_table.add(df)
            logger.debug(f"Saved interaction {interaction_id} to LanceDB")
        except Exception as e:
            logger.error(f"Failed to save interaction to LanceDB: {e}")
            raise

        return interaction_id

    def save_experiential_note(self, timestamp: datetime, reflection: str,
                              interaction_id: str, note_type: str = "reflection",
                              metadata: Optional[Dict] = None) -> str:
        """Save AI experiential note with vector embedding"""

        note_id = f"note_{uuid.uuid4().hex[:8]}"

        # Generate embedding for the reflection
        embedding = self._generate_embedding(reflection)

        # Prepare data
        import json
        import pandas as pd

        data = {
            "id": note_id,
            "timestamp": timestamp,
            "reflection": reflection,
            "interaction_id": interaction_id,
            "note_type": note_type,
            "metadata": json.dumps(metadata or {}),
            "embedding": [float(x) for x in embedding]  # Ensure float32 compatibility
        }

        # Insert into table
        df = pd.DataFrame([data])

        try:
            self.notes_table.add(df)
            logger.debug(f"Saved experiential note {note_id} to LanceDB")
        except Exception as e:
            logger.error(f"Failed to save experiential note to LanceDB: {e}")
            raise

        return note_id

    def link_interaction_to_note(self, interaction_id: str, note_id: str) -> None:
        """Create bidirectional link between interaction and note"""

        import pandas as pd

        link_data = {
            "interaction_id": interaction_id,
            "note_id": note_id,
            "created": datetime.now(),
            "link_type": "bidirectional"
        }

        df = pd.DataFrame([link_data])

        try:
            self.links_table.add(df)
            logger.debug(f"Created link between {interaction_id} and {note_id}")
        except Exception as e:
            logger.error(f"Failed to create link in LanceDB: {e}")

    def search_interactions(self, query: str, user_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Dict]:
        """
        Search interactions using SQL filters and vector similarity.

        Combines:
        1. SQL filters for user_id, date range
        2. Text search in user_input, agent_response, topic
        3. Vector similarity search if embedding provider available
        """

        try:
            # Start with base query
            query_parts = []

            # Filter by user_id
            if user_id:
                query_parts.append(f"user_id = '{user_id}'")

            # Filter by date range
            if start_date:
                query_parts.append(f"timestamp >= '{start_date.isoformat()}'")
            if end_date:
                query_parts.append(f"timestamp <= '{end_date.isoformat()}'")

            # Build WHERE clause
            where_clause = " AND ".join(query_parts) if query_parts else None

            # Try vector search first if embedding adapter available
            if self.embedding_adapter:
                try:
                    query_embedding = self._generate_embedding(query)
                    if query_embedding:
                        # Vector similarity search
                        results = self.interactions_table.search(query_embedding, vector_column_name="embedding").limit(50)

                        # Apply additional filters
                        if where_clause:
                            results = results.where(where_clause)

                        df = results.to_pandas()

                        return self._convert_df_to_dicts(df)
                except Exception as e:
                    logger.warning(f"Vector search failed, falling back to text search: {e}")

            # Fallback to text search
            search_conditions = []
            query_lower = query.lower()

            # Search in multiple text fields
            search_conditions.extend([
                f"LOWER(user_input) LIKE '%{query_lower}%'",
                f"LOWER(agent_response) LIKE '%{query_lower}%'",
                f"LOWER(topic) LIKE '%{query_lower}%'"
            ])

            text_search = "(" + " OR ".join(search_conditions) + ")"

            # Combine with other filters
            if where_clause:
                final_where = f"({where_clause}) AND {text_search}"
            else:
                final_where = text_search

            # Execute search
            df = self.interactions_table.search().where(final_where).limit(100).to_pandas()

            return self._convert_df_to_dicts(df)

        except Exception as e:
            logger.error(f"Search failed in LanceDB: {e}")
            return []

    def _convert_df_to_dicts(self, df) -> List[Dict]:
        """Convert pandas DataFrame to list of dictionaries"""
        import json

        results = []
        for _, row in df.iterrows():
            try:
                result = {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], 'isoformat') else str(row["timestamp"]),
                    "user_input": row["user_input"],
                    "agent_response": row["agent_response"],
                    "topic": row["topic"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to convert row to dict: {e}")
                continue

        return results

    # IStorage interface implementation
    def save(self, key: str, value: Any) -> None:
        """Generic save for compatibility"""
        if "/" in key:
            component_name = key.split("/")[-1]
            self.save_memory_component(component_name, value)

    def load(self, key: str) -> Any:
        """Generic load for compatibility"""
        if "/" in key:
            component_name = key.split("/")[-1]
            return self.load_memory_component(component_name)
        return None

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if "/" in key:
            component_name = key.split("/")[-1]
            try:
                df = self.components_table.search().where(f"component_name = '{component_name}'").limit(1).to_pandas()
                return len(df) > 0
            except:
                return False
        return False

    def save_memory_component(self, component_name: str, component_data: Any) -> None:
        """Save memory component to LanceDB"""
        import json
        import pandas as pd

        # Convert component to JSON
        if hasattr(component_data, '__dict__'):
            data = component_data.__dict__
        else:
            data = component_data

        # Get next version number
        try:
            existing = self.components_table.search().where(f"component_name = '{component_name}'").to_pandas()
            version = existing["version"].max() + 1 if len(existing) > 0 else 1
        except:
            version = 1

        component_record = {
            "component_name": component_name,
            "timestamp": datetime.now(),
            "data": json.dumps(data, default=str),
            "version": version
        }

        df = pd.DataFrame([component_record])

        try:
            self.components_table.add(df)
            logger.debug(f"Saved {component_name} component version {version} to LanceDB")
        except Exception as e:
            logger.error(f"Failed to save {component_name} component: {e}")

    def load_memory_component(self, component_name: str) -> Optional[Any]:
        """Load latest memory component from LanceDB"""
        try:
            import json

            # Get latest version
            df = self.components_table.search().where(f"component_name = '{component_name}'").to_pandas()

            if len(df) == 0:
                return None

            # Get the latest version
            latest = df.loc[df["version"].idxmax()]

            return json.loads(latest["data"])

        except Exception as e:
            logger.error(f"Failed to load {component_name} component: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            interactions_count = len(self.interactions_table.search().limit(10000).to_pandas())
            notes_count = len(self.notes_table.search().limit(10000).to_pandas())
            links_count = len(self.links_table.search().limit(10000).to_pandas())
            components_count = len(self.components_table.search().limit(1000).to_pandas())

            stats = {
                "total_interactions": interactions_count,
                "total_notes": notes_count,
                "total_links": links_count,
                "total_components": components_count,
                "uri": self.uri,
                "embedding_provider_available": self.embedding_adapter is not None,
                "embedding_info": self.embedding_adapter.get_embedding_info() if self.embedding_adapter else None
            }

            # Add stored embedding model info for comparison
            try:
                stored_info_df = self.embedding_metadata_table.search().where("key = 'embedding_model_info'").to_pandas()
                if len(stored_info_df) > 0:
                    import json
                    stats["stored_embedding_info"] = json.loads(stored_info_df.iloc[0]['value'])
                    stats["embedding_consistency"] = self.embedding_adapter.check_consistency_with(stats["stored_embedding_info"]) if self.embedding_adapter else False
            except Exception as e:
                logger.debug(f"Could not retrieve stored embedding info: {e}")

            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "error": str(e),
                "uri": self.uri,
                "embedding_provider_available": self.embedding_adapter is not None,
                "embedding_info": self.embedding_adapter.get_embedding_info() if self.embedding_adapter else None
            }