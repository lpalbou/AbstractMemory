"""
MemorySession - Drop-in replacement for BasicSession with advanced memory capabilities.

Combines the simplicity of BasicSession with the power of AbstractMemory.
Auto-configures memory based on usage patterns while maintaining full compatibility.
"""

from typing import Optional, Dict, Any, Union, Iterator, List, Callable
from datetime import datetime
import logging
from dataclasses import dataclass, field

from .core.interfaces import MemoryItem

logger = logging.getLogger(__name__)

# Try to import BasicSession from AbstractCore (multiple possible import paths)
try:
    # Try new structure first
    from abstractllm.core.session import BasicSession
    from abstractllm.core.types import GenerateResponse
    from abstractllm.core.interface import AbstractLLMInterface
    _BASIC_SESSION_AVAILABLE = True
except ImportError:
    try:
        # Try alternative structure (Session instead of BasicSession)
        from abstractllm import Session as BasicSession, AbstractLLMInterface
        from abstractllm.types import GenerateResponse
        _BASIC_SESSION_AVAILABLE = True
    except ImportError:
        # Fallback for when AbstractCore is not available
        _BASIC_SESSION_AVAILABLE = False
        logger.warning("AbstractCore not available. MemorySession will have limited functionality.")


@dataclass
class MemoryConfig:
    """
    Configuration for memory injection in MemorySession.

    Allows fine-grained control over which memory tiers are included,
    how they are retrieved, and what tools are available to agents.
    """
    # Memory tier inclusion (core is always in system prompt)
    include_user: bool = True          # User profile information
    include_working: bool = True       # Recent context/conversations
    include_semantic: bool = True      # Learned facts and patterns
    include_episodic: bool = False     # Historical episodes (query-dependent)
    include_document: bool = True      # Document chunks (query-dependent)
    include_failures: bool = True      # Failure warnings
    include_storage: bool = True       # Stored interactions search
    include_knowledge_graph: bool = True  # Knowledge graph facts

    # Limits per memory tier
    max_items_per_tier: Dict[str, int] = field(default_factory=lambda: {
        'working': 5,
        'semantic': 3,
        'episodic': 3,
        'document': 2,     # Document chunks
        'storage': 3,
        'knowledge_graph': 3
    })

    # Episodic memory strategies
    episodic_strategy: str = "summary"  # "verbatim", "summary", "semantic_summary"
    episodic_max_length: int = 150      # Max chars per episode (for verbatim/summary)
    episodic_include_metadata: bool = True  # Include when/who/confidence in episodes

    # Retrieval and relevance
    relevance_threshold: float = 0.0   # Minimum relevance score (0.0 = no filtering)
    use_semantic_ranking: bool = True  # Use semantic similarity for ranking
    max_total_items: int = 15          # Overall limit on memory items
    temporal_weight: float = 0.2       # Weight for recency in ranking (0.0-1.0)

    # Context formatting
    compact_format: bool = False       # Use condensed format to save tokens
    show_confidence: bool = True       # Show confidence scores for facts
    show_timestamps: bool = False      # Include timestamps in context

    # Agent tool configuration
    enable_memory_tools: bool = False  # Provide memory tools to agents
    allowed_memory_operations: List[str] = field(default_factory=lambda: [
        "search_memory", "remember_fact", "get_user_profile"
    ])
    enable_self_editing: bool = False  # Allow agents to edit their core memory

    @classmethod
    def minimal(cls) -> 'MemoryConfig':
        """Minimal memory config for token efficiency"""
        return cls(
            include_working=True,
            include_semantic=False,
            include_episodic=False,
            include_storage=False,
            include_knowledge_graph=False,
            max_items_per_tier={'working': 3},
            compact_format=True,
            show_confidence=False,
            episodic_strategy="summary",
            enable_memory_tools=False
        )

    @classmethod
    def comprehensive(cls) -> 'MemoryConfig':
        """Comprehensive memory config for full context"""
        return cls(
            include_episodic=True,
            max_items_per_tier={
                'working': 8,
                'semantic': 5,
                'episodic': 5,
                'storage': 5,
                'knowledge_graph': 5
            },
            max_total_items=30,
            show_confidence=True,
            show_timestamps=True,
            episodic_strategy="semantic_summary",
            use_semantic_ranking=True,
            enable_memory_tools=True,
            allowed_memory_operations=["search_memory", "remember_fact", "get_user_profile", "update_core_memory"],
            enable_self_editing=True
        )

    @classmethod
    def agent_mode(cls) -> 'MemoryConfig':
        """Optimized config for autonomous agents"""
        return cls(
            include_episodic=True,
            episodic_strategy="semantic_summary",
            use_semantic_ranking=True,
            temporal_weight=0.3,
            enable_memory_tools=True,
            allowed_memory_operations=["search_memory", "remember_fact", "get_user_profile", "update_core_memory", "forget_outdated"],
            enable_self_editing=True,
            max_items_per_tier={
                'working': 6,
                'semantic': 4,
                'episodic': 4,
                'storage': 4,
                'knowledge_graph': 3
            },
            show_confidence=True
        )


class MemorySession:
    """
    Enhanced session that combines BasicSession simplicity with GroundedMemory power.

    Features:
    - Drop-in replacement for BasicSession API
    - Automatic memory management and context injection
    - Multi-user support with context separation
    - Progressive complexity - simple by default, configurable when needed
    - Smart memory auto-configuration based on usage patterns

    Usage Examples:

    # Simple usage - just like BasicSession
    session = MemorySession(provider)
    response = session.generate("Hello")

    # With memory persistence
    session = MemorySession(
        provider,
        memory_config={"storage": "dual", "path": "./memory"}
    )

    # Multi-user support
    response = session.generate("I love Python", user_id="alice")
    """

    def __init__(self,
                 provider: Optional[Any] = None,
                 system_prompt: Optional[str] = None,
                 tools: Optional[List[Callable]] = None,
                 memory_config: Optional[Union[Dict[str, Any], MemoryConfig]] = None,
                 default_memory_config: Optional[MemoryConfig] = None,
                 default_user_id: str = "default",
                 auto_add_memory_tools: bool = True,
                 embedding_provider: Optional[Any] = None):
        """
        Initialize MemorySession with automatic memory configuration.

        Args:
            provider: LLM provider (AbstractCore LLM interface)
            system_prompt: System prompt for the session
            tools: List of tools to register with session
            memory_config: Memory storage configuration (dict) or injection configuration (MemoryConfig)
            default_memory_config: Default memory injection configuration (MemoryConfig)
            default_user_id: Default user ID for interactions
            auto_add_memory_tools: Whether to automatically add memory tools for agents
            embedding_provider: Embedding provider for semantic search (auto-configured if None with storage)
        """
        # Initialize BasicSession if available
        if _BASIC_SESSION_AVAILABLE and provider is not None:
            self._basic_session = BasicSession(provider, system_prompt, tools)
            self.provider = provider
            self.system_prompt = system_prompt
            self.tools = tools or []
            self.messages = self._basic_session.messages
        else:
            # Minimal fallback when BasicSession not available
            self._basic_session = None
            self.provider = provider
            self.system_prompt = system_prompt
            self.tools = tools or []
            self.messages = []

        # Separate storage config from injection config
        if isinstance(memory_config, MemoryConfig):
            # New style: MemoryConfig for injection, no storage config
            self.storage_config = {}
            self.memory_injection_config = memory_config
        elif isinstance(memory_config, dict):
            # Old style: dict for storage config
            self.storage_config = memory_config
            self.memory_injection_config = default_memory_config or MemoryConfig()
        else:
            # No config provided
            self.storage_config = {}
            self.memory_injection_config = default_memory_config or MemoryConfig()

        self.default_user_id = default_user_id
        self.current_user_id = default_user_id

        # Auto-configure embedding provider for storage if needed
        self._configure_embedding_provider(embedding_provider)

        # Initialize memory system with smart defaults
        self.memory = self._auto_configure_memory()

        # Auto-add memory tools if enabled
        if auto_add_memory_tools and self.memory_injection_config.enable_memory_tools:
            memory_tools = self._create_memory_tools()
            if memory_tools:
                # Add memory tools to existing tools
                self.tools = (tools or []) + memory_tools

                # Re-initialize BasicSession with updated tools if available
                if _BASIC_SESSION_AVAILABLE and provider is not None:
                    self._basic_session = BasicSession(provider, system_prompt, self.tools)
                    self.messages = self._basic_session.messages

                logger.info(f"Added {len(memory_tools)} memory tools to MemorySession")

        # Track usage for adaptive behavior
        self._interaction_count = 0
        self._users_seen = set([default_user_id])

        logger.info(f"MemorySession initialized with memory type: {type(self.memory).__name__}")

    def _configure_embedding_provider(self, embedding_provider: Optional[Any]) -> None:
        """
        Auto-configure embedding provider for storage backends.

        Args:
            embedding_provider: Explicitly provided embedding provider, or None for auto-config
        """
        # Check if storage is configured
        storage_backend = self.storage_config.get("storage")
        storage_path = self.storage_config.get("path")

        # Only configure embeddings if storage is enabled
        if storage_backend or storage_path:
            if embedding_provider:
                # Use explicitly provided embedding provider
                self.storage_config["embedding_provider"] = embedding_provider
                logger.info("Using explicitly provided embedding provider for memory storage")
            elif not self.storage_config.get("embedding_provider"):
                # Auto-configure default embedding provider
                try:
                    from .embeddings.sentence_transformer_provider import create_sentence_transformer_provider
                    auto_embedder = create_sentence_transformer_provider("sentence-transformers/all-MiniLM-L6-v2")
                    self.storage_config["embedding_provider"] = auto_embedder
                    logger.info("Auto-configured all-MiniLM-L6-v2 embeddings for memory storage")
                except ImportError:
                    logger.warning(
                        "Cannot auto-configure embeddings: sentence-transformers not available. "
                        "Install with: pip install sentence-transformers"
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-configure embeddings: {e}")

    def _auto_configure_memory(self) -> Union[Any, Any]:
        """
        Auto-configure memory based on config and usage patterns.

        Smart defaults:
        - Use GroundedMemory for maximum capability
        - Enable storage if path/uri provided
        - Auto-configure embeddings for semantic search
        - Set reasonable capacity limits
        """
        # Extract configuration
        memory_type = self.storage_config.get("type", "grounded")
        storage_backend = self.storage_config.get("storage")
        storage_path = self.storage_config.get("path")
        storage_uri = self.storage_config.get("uri", "./memory.db")
        working_capacity = self.storage_config.get("working_capacity", 15)
        enable_kg = self.storage_config.get("enable_kg", True)
        embedding_provider = self.storage_config.get("embedding_provider")
        semantic_threshold = self.storage_config.get("semantic_threshold", 3)  # Default 3, allow override

        # Configure storage if path provided
        if storage_path and not storage_backend:
            storage_backend = "dual"  # Use dual storage by default

        # Import here to avoid circular imports
        from . import create_memory

        # Create memory with auto-configuration
        try:
            memory = create_memory(
                memory_type=memory_type,
                working_capacity=working_capacity,
                enable_kg=enable_kg,
                storage_backend=storage_backend,
                storage_path=storage_path,
                storage_uri=storage_uri,
                embedding_provider=embedding_provider,
                default_user_id=self.default_user_id,
                semantic_threshold=semantic_threshold
            )

            logger.info(f"Memory configured with storage: {storage_backend}, "
                       f"working_capacity: {working_capacity}, enable_kg: {enable_kg}")
            return memory

        except Exception as e:
            logger.warning(f"Failed to create advanced memory: {e}. Using basic GroundedMemory.")
            # Fallback to basic grounded memory without storage
            return create_memory("grounded", working_capacity=working_capacity)

    def _create_memory_tools(self) -> List[Callable]:
        """
        Create memory management tools for agents based on configuration.

        Returns:
            List of memory tool functions
        """
        try:
            # Import here to avoid circular imports
            from .tools import create_memory_tools

            # Create tools based on allowed operations
            all_tools = create_memory_tools(self)
            allowed_ops = set(self.memory_injection_config.allowed_memory_operations)

            # Filter tools based on configuration
            filtered_tools = []
            for tool_func in all_tools:
                tool_name = tool_func.__name__

                # Map tool names to operation names
                operation_mapping = {
                    'search_memory': 'search_memory',
                    'remember_fact': 'remember_fact',
                    'get_user_profile': 'get_user_profile',
                    'get_recent_context': 'get_user_profile',  # Same permission
                    'get_semantic_facts': 'remember_fact',     # Same permission
                    'update_core_memory': 'update_core_memory'
                }

                required_op = operation_mapping.get(tool_name, tool_name)
                if required_op in allowed_ops:
                    filtered_tools.append(tool_func)

            logger.debug(f"Created {len(filtered_tools)} memory tools from {len(allowed_ops)} allowed operations")
            return filtered_tools

        except ImportError as e:
            logger.warning(f"Could not import memory tools: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to create memory tools: {e}")
            return []

    def set_current_user(self, user_id: str, relationship: Optional[str] = None):
        """
        Set current user for context separation.

        Args:
            user_id: User identifier
            relationship: Relationship to the agent (e.g., "owner", "colleague")
        """
        self.current_user_id = user_id
        self._users_seen.add(user_id)

        # Update memory's current user
        if hasattr(self.memory, 'set_current_user'):
            self.memory.set_current_user(user_id, relationship)
            logger.debug(f"Set current user to: {user_id}")

    # === Identity-based Memory System ===

    def load_identity(self, identity_path: str):
        """
        Load a specific identity with all its accumulated memories.

        Each identity represents a complete AI persona shaped by:
        - Core values and beliefs
        - Accumulated experiences
        - Learned patterns and behaviors
        - Relationships and interactions
        - Domain knowledge and skills

        Args:
            identity_path: Path to the identity storage directory
        """
        from .grounded_memory import MemoryIdentity

        try:
            # Load the identity
            identity = MemoryIdentity.load_from_path(identity_path)

            # Replace current memory with identity's memory
            self.memory = identity.memories
            self.current_identity = identity

            # CRITICAL: Set core values on the memory to enable subjective interpretation
            if identity.core_values:
                self.memory.set_core_values(identity.core_values)
                self.system_prompt = self._build_identity_prompt(identity)

                # Update BasicSession if available
                if self._basic_session:
                    self._basic_session.system_prompt = self.system_prompt

            logger.info(f"Loaded identity '{identity.identity_id}' from {identity_path}")
            return identity

        except Exception as e:
            logger.error(f"Failed to load identity from {identity_path}: {e}")
            raise

    def switch_identity(self, new_identity_path: str):
        """
        Switch to a different identity, saving the current one first.

        Args:
            new_identity_path: Path to the new identity to load
        """
        # Save current identity if one is loaded
        if hasattr(self, 'current_identity') and self.current_identity:
            try:
                self.current_identity.save()
                logger.info(f"Saved current identity '{self.current_identity.identity_id}'")
            except Exception as e:
                logger.warning(f"Failed to save current identity: {e}")

        # Load new identity
        self.load_identity(new_identity_path)

    def create_identity(self, identity_id: str, storage_root: str = "./identities",
                       core_values: Optional[Dict] = None) -> 'MemoryIdentity':
        """
        Create a new identity with specific core values and beliefs.

        Args:
            identity_id: Unique identifier for the identity
            storage_root: Root directory for storing identities
            core_values: Core values and beliefs that define this identity

        Returns:
            The created MemoryIdentity instance
        """
        from .grounded_memory import MemoryIdentity

        # Default core values
        if core_values is None:
            core_values = {
                "purpose": "Be helpful and truthful",
                "approach": "Thoughtful and analytical",
                "ethics": "Respect for users and transparency"
            }

        try:
            identity = MemoryIdentity.create_new(identity_id, storage_root, core_values)
            logger.info(f"Created new identity '{identity_id}' with {len(core_values)} core values")
            return identity

        except Exception as e:
            logger.error(f"Failed to create identity '{identity_id}': {e}")
            raise

    def save_current_identity(self):
        """Save the current identity's state to storage."""
        if hasattr(self, 'current_identity') and self.current_identity:
            try:
                self.current_identity.save()
                logger.info(f"Saved identity '{self.current_identity.identity_id}'")
            except Exception as e:
                logger.error(f"Failed to save current identity: {e}")
                raise
        else:
            logger.warning("No current identity to save")

    def get_identity_summary(self) -> Dict[str, Any]:
        """Get a summary of the current identity."""
        if hasattr(self, 'current_identity') and self.current_identity:
            return {
                "identity_id": self.current_identity.identity_id,
                "core_values": self.current_identity.core_values,
                "metadata": self.current_identity.metadata,
                "storage_path": str(self.current_identity.storage_path)
            }
        return {"identity_id": None, "status": "No identity loaded"}

    def _build_identity_prompt(self, identity: 'MemoryIdentity') -> str:
        """
        Build system prompt incorporating the identity's core values.

        Args:
            identity: The MemoryIdentity to build prompt for

        Returns:
            Enhanced system prompt with identity's core values
        """
        base_prompt = self.system_prompt or "You are a helpful AI assistant."

        if not identity.core_values:
            return base_prompt

        # Build core values section
        values_section = "\n=== Core Values & Identity ===\n"
        for key, value in identity.core_values.items():
            values_section += f"• {key.title()}: {value}\n"

        # Add metadata context
        if identity.metadata.get("primary_domain"):
            values_section += f"• Primary Domain: {identity.metadata['primary_domain']}\n"

        values_section += f"• Identity: {identity.identity_id}\n"

        return f"{base_prompt}\n{values_section}"

    def generate(self, prompt: str, user_id: Optional[str] = None,
                include_memory: bool = True, max_memory_items: int = 10,
                memory_config: Optional[MemoryConfig] = None,
                **kwargs) -> Union[Any, Iterator[Any]]:
        """
        Generate response with automatic memory context injection.

        Args:
            prompt: User input prompt
            user_id: User ID for context separation (uses current_user if None)
            include_memory: Whether to include memory context
            max_memory_items: Maximum memory items to include in context (legacy)
            memory_config: Override default memory injection configuration
            **kwargs: Additional arguments passed to BasicSession.generate()

        Returns:
            GenerateResponse (streaming or non-streaming based on provider)
        """
        if not self.provider:
            raise ValueError("No provider configured for MemorySession")

        # Determine effective user ID
        effective_user_id = user_id or self.current_user_id
        if user_id and user_id != self.current_user_id:
            self.set_current_user(user_id)

        # Determine effective memory config
        effective_memory_config = memory_config or self.memory_injection_config

        # Build enhanced system prompt with core memory + selective context
        enhanced_system_prompt = self._build_enhanced_system_prompt(
            prompt, effective_user_id, include_memory,
            effective_memory_config, max_memory_items
        )

        # Generate response using BasicSession or fallback
        if self._basic_session:
            # Use BasicSession if available
            original_system = self._basic_session.system_prompt
            try:
                # Temporarily update system prompt
                self._basic_session.system_prompt = enhanced_system_prompt
                response = self._basic_session.generate(prompt, **kwargs)
            finally:
                # Restore original system prompt
                self._basic_session.system_prompt = original_system
        else:
            # Minimal fallback when BasicSession not available
            if not hasattr(self.provider, 'generate'):
                raise ValueError("Provider must have generate() method")

            response = self.provider.generate(
                prompt=prompt,
                system_prompt=enhanced_system_prompt,
                tools=self.tools if 'tools' not in kwargs else kwargs.get('tools'),
                **{k: v for k, v in kwargs.items() if k != 'tools'}
            )

        # Track interaction in memory (handle both streaming and non-streaming)
        if hasattr(self.memory, 'add_interaction'):
            try:
                if hasattr(response, 'content') and response.content:
                    # Non-streaming response
                    self.memory.add_interaction(
                        user_input=prompt,
                        agent_response=response.content,
                        user_id=effective_user_id
                    )
                elif hasattr(response, '__iter__') and not isinstance(response, str):
                    # Streaming response - wrap to collect content
                    response = self._track_streaming_response(
                        response, prompt, effective_user_id
                    )
                else:
                    # Handle other response types
                    response_text = str(response) if response else ""
                    if response_text:
                        self.memory.add_interaction(
                            user_input=prompt,
                            agent_response=response_text,
                            user_id=effective_user_id
                        )

                self._interaction_count += 1
                logger.debug(f"Tracked interaction #{self._interaction_count} for user {effective_user_id}")

                # Auto-extract facts from user input for better memory recall
                self._auto_extract_facts(prompt, effective_user_id)

            except Exception as e:
                logger.warning(f"Failed to track interaction in memory: {e}")

        return response

    def _auto_extract_facts(self, user_input: str, user_id: str):
        """
        Automatically extract key facts from user input for better memory recall.

        Uses pattern matching to identify common fact patterns like:
        - "I'm [name]" -> name
        - "I love/prefer/use [thing]" -> preference
        - "I work on/with [thing]" -> work context
        """
        if not user_input or not user_id:
            return

        try:
            import re

            # Pattern-based fact extraction
            facts = []

            # Name extraction: "I'm Alice", "My name is Bob"
            name_patterns = [
                r"I'?m ([A-Z][a-z]+)",
                r"my name is ([A-Z][a-z]+)",
                r"call me ([A-Z][a-z]+)"
            ]

            for pattern in name_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for name in matches:
                    if len(name) > 1:  # Skip single letters
                        facts.append(f"User's name is {name}")

            # Preference extraction: "I love Python", "I prefer TypeScript"
            preference_patterns = [
                r"I (?:love|prefer|like|enjoy|use|work with) ([A-Za-z][A-Za-z\s\+\#\.]+?)(?:\s+(?:programming|development|language|framework|for|because|and|,|\.|$))",
                r"I'?m (?:working on|building|using|learning) ([A-Za-z][A-Za-z\s\+\#\.]+?)(?:\s+(?:projects?|development|applications?|for|because|and|,|\.|$))"
            ]

            for pattern in preference_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for tech in matches:
                    tech = tech.strip()
                    if len(tech) > 2 and not tech.lower() in ["the", "and", "for", "with"]:
                        facts.append(f"Uses/prefers {tech}")

            # Store extracted facts
            for fact in facts:
                self.learn_about_user(fact, user_id)
                logger.debug(f"Auto-extracted fact for {user_id}: {fact}")

        except Exception as e:
            logger.debug(f"Fact extraction failed (non-critical): {e}")

    def _track_streaming_response(self, response_iterator, prompt: str, user_id: str):
        """
        Wrap streaming response to collect content for memory tracking.

        Args:
            response_iterator: Streaming response iterator
            prompt: Original user prompt
            user_id: User ID for memory tracking

        Yields:
            Response chunks while collecting content for memory
        """
        collected_content = ""

        try:
            for chunk in response_iterator:
                yield chunk

                # Collect content for memory
                if hasattr(chunk, 'content') and chunk.content:
                    collected_content += chunk.content
        finally:
            # Track complete interaction after streaming finishes
            if collected_content and hasattr(self.memory, 'add_interaction'):
                try:
                    self.memory.add_interaction(
                        user_input=prompt,
                        agent_response=collected_content,
                        user_id=user_id
                    )
                    logger.debug(f"Tracked streaming interaction for user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to track streaming interaction: {e}")

    def _build_enhanced_system_prompt(self, prompt: str, user_id: str,
                                    include_memory: bool, memory_config: MemoryConfig,
                                    max_memory_items: int) -> str:
        """
        Build enhanced system prompt with core memory + selective context.

        Core memory is always included in system prompt (MemGPT/Letta pattern).
        Additional context is selectively included based on configuration.
        """
        # Start with base system prompt
        enhanced_system_prompt = self.system_prompt or ""

        # Always include core memory in system prompt (agent identity)
        if hasattr(self.memory, 'core') and hasattr(self.memory.core, 'get_context'):
            try:
                core_context = self.memory.core.get_context()
                if core_context:
                    enhanced_system_prompt = f"{enhanced_system_prompt}\n\n=== AGENT IDENTITY ===\n{core_context}"
            except Exception as e:
                logger.warning(f"Failed to get core memory context: {e}")

        # Add selective memory context if requested
        if include_memory:
            try:
                selective_context = self._build_selective_context(
                    prompt, user_id, memory_config, max_memory_items
                )
                if selective_context:
                    enhanced_system_prompt = f"{enhanced_system_prompt}\n\n=== MEMORY CONTEXT ===\n{selective_context}"
            except Exception as e:
                logger.warning(f"Failed to build selective memory context: {e}")

        return enhanced_system_prompt

    def _build_selective_context(self, query: str, user_id: str,
                               config: MemoryConfig, max_legacy_items: int) -> str:
        """
        Build selective memory context based on configuration.

        Args:
            query: Query for relevance matching
            user_id: User ID for context filtering
            config: Memory configuration specifying what to include
            max_legacy_items: Legacy max items parameter (for backward compatibility)

        Returns:
            Formatted selective memory context
        """
        context_parts = []

        # User profile (if enabled and available)
        if config.include_user and hasattr(self.memory, 'user_profiles'):
            user_profile = self.memory.user_profiles.get(user_id)
            if user_profile:
                profile_parts = [f"=== User Profile: {user_id} ==="]
                profile_parts.append(f"Relationship: {user_profile.get('relationship', 'unknown')}")
                profile_parts.append(f"Interactions: {user_profile.get('interaction_count', 0)}")

                # Show facts if available
                facts = user_profile.get('facts', [])
                if facts:
                    max_facts = min(3, len(facts))  # Limit user facts
                    profile_parts.append(f"Key facts: {', '.join(facts[:max_facts])}")

                context_parts.extend(profile_parts)

        # Semantic memory (learned facts)
        if config.include_semantic and hasattr(self.memory, 'semantic'):
            try:
                max_semantic = config.max_items_per_tier.get('semantic', 3)
                semantic_facts = self.memory.semantic.retrieve(query, limit=max_semantic)
                if semantic_facts:
                    context_parts.append("=== Learned Facts ===")
                    for fact in semantic_facts:
                        confidence_str = f" (confidence: {fact.confidence:.2f})" if config.show_confidence else ""
                        context_parts.append(f"- {fact.content}{confidence_str}")
            except Exception as e:
                logger.debug(f"Failed to retrieve semantic facts: {e}")

        # Failure warnings (if enabled)
        if config.include_failures and hasattr(self.memory, 'failure_patterns'):
            for pattern, count in self.memory.failure_patterns.items():
                if query.lower() in pattern.lower() and count >= 2:
                    context_parts.append(f"⚠️ Warning: Previous failures with similar action ({count} times)")
                    break

        # Working memory (recent context)
        if config.include_working and hasattr(self.memory, 'working'):
            try:
                max_working = config.max_items_per_tier.get('working', 5)
                working_items = self.memory.working.retrieve(query, limit=max_working)
                if working_items:
                    context_parts.append("=== Recent Context ===")
                    for item in working_items:
                        if isinstance(item.content, dict):
                            text = item.content.get('text', str(item.content))
                            if config.compact_format:
                                text = text[:100] + "..." if len(text) > 100 else text
                            context_parts.append(f"- {text}")
            except Exception as e:
                logger.debug(f"Failed to retrieve working memory: {e}")

        # Episodic memory (if enabled and query-relevant)
        if config.include_episodic and hasattr(self.memory, 'episodic'):
            try:
                max_episodic = config.max_items_per_tier.get('episodic', 2)
                episodes = self.memory.episodic.retrieve(query, limit=max_episodic)
                if episodes:
                    context_parts.append("=== Relevant Episodes ===")
                    formatted_episodes = self._format_episodes(episodes, config)
                    context_parts.extend(formatted_episodes)
            except Exception as e:
                logger.debug(f"Failed to retrieve episodic memory: {e}")

        # Stored interactions (semantic search if available)
        if (config.include_storage and hasattr(self.memory, 'storage_manager') and
            self.memory.storage_manager and hasattr(self.memory.storage_manager, 'search_interactions')):
            try:
                max_storage = config.max_items_per_tier.get('storage', 3)
                storage_results = self.memory.storage_manager.search_interactions(
                    query, user_id=user_id, limit=max_storage
                )
                if storage_results:
                    context_parts.append("=== Recent Interactions ===")
                    for result in storage_results:
                        if 'user_input' in result and 'agent_response' in result:
                            user_text = result['user_input'][:80] + "..." if len(result['user_input']) > 80 else result['user_input']
                            agent_text = result['agent_response'][:80] + "..." if len(result['agent_response']) > 80 else result['agent_response']
                            if config.compact_format:
                                context_parts.append(f"Q: {user_text} A: {agent_text}")
                            else:
                                context_parts.append(f"User: {user_text}")
                                context_parts.append(f"Agent: {agent_text}")
            except Exception as e:
                logger.debug(f"Failed to search stored interactions: {e}")

        # Document memory chunks (if enabled and available)
        if config.include_document and hasattr(self.memory, 'document'):
            try:
                max_document = config.max_items_per_tier.get('document', 2)
                document_chunks = self.memory.document.retrieve(query, limit=max_document)
                if document_chunks:
                    context_parts.append("=== Relevant Documents ===")
                    retrieved_content_hashes = set()  # Track to avoid duplicates

                    for chunk in document_chunks:
                        # Check for duplicates using content hash
                        import hashlib
                        content_hash = hashlib.md5(str(chunk.content).encode()).hexdigest()

                        if content_hash not in retrieved_content_hashes:
                            retrieved_content_hashes.add(content_hash)

                            filepath = chunk.metadata.get('filepath', 'unknown')
                            # Truncate chunk content for context (not storage!)
                            chunk_preview = str(chunk.content)[:500] + "..." if len(str(chunk.content)) > 500 else str(chunk.content)

                            if config.show_confidence:
                                confidence_str = f" (relevance: {chunk.confidence:.2f})"
                            else:
                                confidence_str = ""

                            context_parts.append(f"From {filepath}{confidence_str}:\n{chunk_preview}")

            except Exception as e:
                logger.debug(f"Failed to retrieve document chunks: {e}")

        # Knowledge graph facts (if enabled)
        if config.include_knowledge_graph and hasattr(self.memory, 'kg') and self.memory.kg:
            try:
                max_kg = config.max_items_per_tier.get('knowledge_graph', 3)
                facts = self.memory.kg.query_at_time(query, datetime.now())
                if facts and len(facts) > 0:
                    context_parts.append("=== Known Facts ===")
                    for fact in facts[:max_kg]:
                        context_parts.append(f"- {fact['subject']} {fact['predicate']} {fact['object']}")
            except Exception as e:
                logger.debug(f"Failed to retrieve knowledge graph facts: {e}")

        # Join context parts with appropriate spacing and prefix
        if context_parts:
            context_content = "\n\n".join(context_parts)
            return f"Here is what I remember on that topic:\n\n{context_content}"
        else:
            return ""

    def _format_episodes(self, episodes: List[Any], config: MemoryConfig) -> List[str]:
        """
        Format episodic memories based on strategy configuration.

        Args:
            episodes: List of episodic memory items
            config: Memory configuration with strategy settings

        Returns:
            List of formatted episode strings
        """
        formatted = []

        for episode in episodes:
            try:
                # Extract episode content and metadata
                content = str(episode.content) if hasattr(episode, 'content') else str(episode)
                metadata = {}

                # Try to extract metadata from different possible sources
                if hasattr(episode, 'event_time'):
                    metadata['when'] = episode.event_time.strftime("%Y-%m-%d %H:%M") if episode.event_time else None
                if hasattr(episode, 'metadata') and episode.metadata:
                    episode_meta = episode.metadata
                    if isinstance(episode_meta, dict):
                        # Look for relational context
                        relational = episode_meta.get('relational', {})
                        if isinstance(relational, dict):
                            metadata['who'] = relational.get('user_id')
                if hasattr(episode, 'confidence'):
                    metadata['confidence'] = round(episode.confidence, 2) if episode.confidence else None

                # Format based on strategy
                if config.episodic_strategy == "verbatim":
                    # Return full content, but limited by max_length
                    if len(content) > config.episodic_max_length:
                        episode_text = content[:config.episodic_max_length] + "..."
                    else:
                        episode_text = content

                elif config.episodic_strategy == "summary":
                    # Create structured summary
                    episode_text = self._create_episode_summary(content, config.episodic_max_length)

                elif config.episodic_strategy == "semantic_summary":
                    # Create semantic summary with key points
                    episode_text = self._create_semantic_summary(content, config.episodic_max_length)

                else:
                    # Default to summary strategy
                    episode_text = self._create_episode_summary(content, config.episodic_max_length)

                # Add metadata if enabled
                if config.episodic_include_metadata and metadata:
                    meta_parts = []
                    if metadata.get('when'):
                        meta_parts.append(f"When: {metadata['when']}")
                    if metadata.get('who'):
                        meta_parts.append(f"With: {metadata['who']}")
                    if metadata.get('confidence') and config.show_confidence:
                        meta_parts.append(f"Confidence: {metadata['confidence']}")

                    if meta_parts:
                        meta_str = " | ".join(meta_parts)
                        episode_text = f"[{meta_str}] {episode_text}"

                formatted.append(f"- {episode_text}")

            except Exception as e:
                logger.debug(f"Failed to format episode: {e}")
                # Fallback to simple string representation
                simple_content = str(episode)[:config.episodic_max_length]
                formatted.append(f"- {simple_content}")

        return formatted

    def _create_episode_summary(self, content: str, max_length: int) -> str:
        """Create structured summary of episode content."""
        # Simple approach: extract first sentence and key information
        sentences = content.split('. ')
        if len(sentences) > 0:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > max_length:
                return first_sentence[:max_length] + "..."
            elif len(sentences) > 1 and len(first_sentence) < max_length * 0.7:
                # Try to include second sentence if there's room
                second_sentence = sentences[1].strip()
                combined = f"{first_sentence}. {second_sentence}"
                if len(combined) <= max_length:
                    return combined
                else:
                    return first_sentence
            else:
                return first_sentence
        else:
            return content[:max_length] + ("..." if len(content) > max_length else "")

    def _create_semantic_summary(self, content: str, max_length: int) -> str:
        """Create semantic summary with key points extraction."""
        # For now, use a simple approach - in production could use LLM summarization

        # Look for key indicators (questions, actions, outcomes)
        key_patterns = [
            r'(asked|question|wondering|want to know).*?\?',
            r'(decided|chose|will|going to).*?[.!]',
            r'(learned|discovered|found|realized).*?[.!]',
            r'(problem|issue|error).*?[.!]',
            r'(solution|fixed|resolved).*?[.!]'
        ]

        import re
        key_points = []

        for pattern in key_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            key_points.extend([match for match in matches if len(match) < max_length * 0.8])

        if key_points:
            # Join key points, prioritizing shorter ones
            key_points.sort(key=len)
            summary = ""
            for point in key_points:
                if len(summary + point) <= max_length:
                    summary += point + " "
                else:
                    break
            return summary.strip()
        else:
            # Fallback to regular summary
            return self._create_episode_summary(content, max_length)

    def get_memory_context(self, query: str, user_id: Optional[str] = None,
                          max_items: int = 10) -> str:
        """
        Explicitly get memory context for a query.

        Args:
            query: Query to search memory with
            user_id: User ID for context (uses current_user if None)
            max_items: Maximum items to retrieve

        Returns:
            Formatted memory context string
        """
        if not hasattr(self.memory, 'get_full_context'):
            return ""

        effective_user_id = user_id or self.current_user_id

        try:
            return self.memory.get_full_context(query, max_items, effective_user_id)
        except Exception as e:
            logger.warning(f"Failed to get memory context: {e}")
            return ""

    def learn_about_user(self, fact: str, user_id: Optional[str] = None):
        """
        Explicitly learn a fact about the user.

        Args:
            fact: Fact to learn about the user
            user_id: User ID (uses current_user if None)
        """
        if hasattr(self.memory, 'learn_about_user'):
            effective_user_id = user_id or self.current_user_id
            self.memory.learn_about_user(fact, effective_user_id)
            logger.debug(f"Learned about user {effective_user_id}: {fact}")

    def search_memory(self, query: str, user_id: Optional[str] = None,
                     limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search stored interactions and memories.

        Args:
            query: Search query
            user_id: User ID to filter by (uses current_user if None)
            limit: Maximum results to return

        Returns:
            List of matching memory items
        """
        if not hasattr(self.memory, 'search_stored_interactions'):
            return []

        effective_user_id = user_id or self.current_user_id

        try:
            # Try with limit parameter first, fallback without if not supported
            try:
                return self.memory.search_stored_interactions(
                    query, effective_user_id, limit=limit
                )
            except TypeError:
                # Method doesn't support limit parameter, call without it
                results = self.memory.search_stored_interactions(query, effective_user_id)
                # Apply limit manually
                return results[:limit] if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []

    def get_working_memory(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent working memory items.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of recent memory items
        """
        if not hasattr(self.memory, 'working'):
            return []

        try:
            working_items = self.memory.working.get_context_window()
            result = []
            for item in working_items[-limit:]:  # Get most recent
                if hasattr(item, 'content'):
                    result.append({
                        'content': item.content,
                        'event_time': item.event_time.isoformat() if hasattr(item, 'event_time') else None,
                        'confidence': getattr(item, 'confidence', 1.0),
                        'metadata': getattr(item, 'metadata', {})
                    })
            return result
        except Exception as e:
            logger.warning(f"Failed to get working memory: {e}")
            return []

    def get_semantic_facts(self, topic: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get validated semantic facts, optionally filtered by topic.

        Args:
            topic: Optional topic to filter by
            limit: Maximum number of facts to return

        Returns:
            List of semantic facts with confidence scores
        """
        if not hasattr(self.memory, 'semantic'):
            return []

        try:
            query = topic or ""  # Use topic as query or empty string for all facts
            semantic_facts = self.memory.semantic.retrieve(query, limit=limit)
            result = []
            for fact in semantic_facts:
                result.append({
                    'content': fact.content,
                    'confidence': fact.confidence,
                    'event_time': fact.event_time.isoformat() if hasattr(fact, 'event_time') else None,
                    'metadata': getattr(fact, 'metadata', {})
                })
            return result
        except Exception as e:
            logger.warning(f"Failed to get semantic facts: {e}")
            return []

    def get_user_profile(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete user profile information.

        Args:
            user_id: User ID to get profile for (uses current_user if None)

        Returns:
            Dictionary with user profile information
        """
        effective_user_id = user_id or self.current_user_id

        if not hasattr(self.memory, 'user_profiles'):
            return {'user_id': effective_user_id, 'profile_available': False}

        try:
            profile = self.memory.user_profiles.get(effective_user_id, {})
            return {
                'user_id': effective_user_id,
                'profile_available': True,
                'relationship': profile.get('relationship', 'unknown'),
                'interaction_count': profile.get('interaction_count', 0),
                'facts': profile.get('facts', []),
                'preferences': profile.get('preferences', {}),
                'first_seen': profile.get('first_seen').isoformat() if profile.get('first_seen') else None
            }
        except Exception as e:
            logger.warning(f"Failed to get user profile: {e}")
            return {'user_id': effective_user_id, 'profile_available': False, 'error': str(e)}

    def search_by_memory_type(self, query: str, memory_types: List[str],
                             user_id: Optional[str] = None, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search specific memory types/tiers.

        Args:
            query: Search query
            memory_types: List of memory types to search ('working', 'semantic', 'episodic', 'storage')
            user_id: User ID for filtering (uses current_user if None)
            limit: Maximum results per memory type

        Returns:
            Dictionary mapping memory type to search results
        """
        effective_user_id = user_id or self.current_user_id
        results = {}

        for memory_type in memory_types:
            results[memory_type] = []

            try:
                if memory_type == 'working' and hasattr(self.memory, 'working'):
                    items = self.memory.working.retrieve(query, limit=limit)
                    for item in items:
                        results[memory_type].append({
                            'content': item.content,
                            'confidence': getattr(item, 'confidence', 1.0),
                            'type': 'working'
                        })

                elif memory_type == 'semantic' and hasattr(self.memory, 'semantic'):
                    items = self.memory.semantic.retrieve(query, limit=limit)
                    for item in items:
                        results[memory_type].append({
                            'content': item.content,
                            'confidence': getattr(item, 'confidence', 1.0),
                            'type': 'semantic'
                        })

                elif memory_type == 'episodic' and hasattr(self.memory, 'episodic'):
                    items = self.memory.episodic.retrieve(query, limit=limit)
                    for item in items:
                        results[memory_type].append({
                            'content': item.content,
                            'confidence': getattr(item, 'confidence', 1.0),
                            'type': 'episodic'
                        })

                elif memory_type == 'storage':
                    storage_results = self.search_memory(query, user_id=effective_user_id, limit=limit)
                    results[memory_type] = storage_results

            except Exception as e:
                logger.warning(f"Failed to search {memory_type} memory: {e}")

        return results

    def get_failure_patterns(self) -> Dict[str, int]:
        """
        Get learned failure patterns.

        Returns:
            Dictionary mapping failure patterns to occurrence counts
        """
        if hasattr(self.memory, 'failure_patterns'):
            return self.memory.failure_patterns.copy()
        return {}

    def get_success_patterns(self) -> Dict[str, int]:
        """
        Get learned success patterns.

        Returns:
            Dictionary mapping success patterns to occurrence counts
        """
        if hasattr(self.memory, 'success_patterns'):
            return self.memory.success_patterns.copy()
        return {}

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory usage and storage.

        Returns:
            Dictionary with memory statistics
        """
        stats = {
            "memory_type": type(self.memory).__name__,
            "interaction_count": self._interaction_count,
            "users_seen": len(self._users_seen),
            "current_user": self.current_user_id,
            "default_user": self.default_user_id
        }

        # Add storage stats if available
        if hasattr(self.memory, 'get_storage_stats'):
            try:
                storage_stats = self.memory.get_storage_stats()
                stats["storage"] = storage_stats
            except Exception as e:
                logger.warning(f"Failed to get storage stats: {e}")

        return stats

    def clear_history(self, keep_system: bool = True):
        """
        Clear conversation history while preserving memory.

        Args:
            keep_system: Whether to keep system message
        """
        if self._basic_session:
            self._basic_session.clear_history(keep_system)
        else:
            # Fallback implementation
            if keep_system:
                self.messages = [m for m in self.messages if m.get('role') == 'system']
            else:
                self.messages = []

    def save_session(self, filepath: str):
        """
        Save session state (conversation + memory).

        Args:
            filepath: Path to save session data
        """
        if self._basic_session and hasattr(self._basic_session, 'save'):
            self._basic_session.save(filepath)

        # Save memory state if supported
        if hasattr(self.memory, 'save'):
            memory_path = filepath.replace('.json', '_memory')
            self.memory.save(memory_path)

    # Compatibility methods - delegate to BasicSession when available
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        if self._basic_session:
            return self._basic_session.add_message(role, content)
        else:
            # Fallback
            message = {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
            self.messages.append(message)
            return message

    def get_messages(self):
        """Get conversation messages"""
        if self._basic_session:
            return self._basic_session.get_messages()
        return self.messages.copy()

    def get_history(self, include_system: bool = True):
        """Get conversation history"""
        if self._basic_session:
            return self._basic_session.get_history(include_system)

        # Fallback
        if include_system:
            return self.messages.copy()
        return [m for m in self.messages if m.get('role') != 'system']

    @property
    def id(self):
        """Get session ID"""
        return getattr(self._basic_session, 'id', 'memory_session')

    def __str__(self):
        return f"MemorySession(memory={type(self.memory).__name__}, users={len(self._users_seen)}, interactions={self._interaction_count})"