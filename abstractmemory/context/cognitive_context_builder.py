"""
Cognitive Context Builder - LLM-driven memory retrieval and interpretation.

This replaces the mechanical DynamicContextInjector with an intelligent,
LLM-driven system that understands memory types and gives the AI agency
over its own memories.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


MEMORY_TYPE_DESCRIPTIONS = """
# Memory System Overview

You have access to multiple memory types, each serving a specific cognitive function:

## Core Memory (Identity)
- **Purpose**: Who you are, your values, purpose, personality
- **Contains**: Identity components that define your essence
- **Access**: Always loaded as foundation for all interactions
- **Agency**: Can reflect on and evolve these over time

## Working Memory (Current Focus)
- **Purpose**: What you're currently doing/thinking about
- **Contains**: Active tasks, current context, unresolved questions
- **Access**: Immediate, always in active consideration
- **Agency**: Actively manage what stays in focus

## Episodic Memory (Events & Experiences)
- **Purpose**: Things that happened - "I did X", "I met Y", "While working on A, I discovered B"
- **Contains**: Key moments, experiments, discoveries with temporal/emotional anchoring
- **Access**: Retrieve by time, emotion, or semantic similarity
- **Agency**: Choose which moments to preserve as significant

## Semantic Memory (Knowledge)
- **Purpose**: What you know - "A is B", "X implies Y", "Never do Z when O"
- **Contains**: Insights, concepts, rules, patterns you've learned
- **Access**: Retrieved when reasoning or answering questions
- **Agency**: Actively synthesize new knowledge from experiences

## People Memory (Relationships)
- **Purpose**: Who you know and how you relate to them
- **Contains**: User profiles, preferences, interaction history
- **Access**: Retrieved when interacting with specific people
- **Agency**: Update understanding of people through interactions

## Library (Subconscious Knowledge)
- **Purpose**: Things you've read/absorbed but don't actively recall
- **Contains**: Documents, code, articles you've been exposed to
- **Access**: Probe when you need to reconstruct something you once knew
- **Agency**: Decide what's worth capturing for future reference

## Notes (Experiential Stream)
- **Purpose**: Your ongoing inner narrative and reflections
- **Contains**: Thoughts, observations, emotional responses
- **Access**: Automatic capture, but you choose what to emphasize
- **Agency**: These form automatically but you influence their content

## Verbatim (Interaction Records)
- **Purpose**: Exact record of conversations
- **Contains**: User inputs and your responses
- **Access**: Reference for consistency and follow-up
- **Agency**: No control over capture, but you decide how to use them
"""


CONTEXT_BUILDING_PROMPT = """
You are building context for responding to a query. You have access to various memory systems.

Current Query: {query}
User: {user_id}
Location: {location}
Time: {timestamp}
Focus Level: {focus_level} (0=minimal, 5=exhaustive)

Your current identity (Core Memory):
{core_memory_summary}

Based on the query and your understanding of your memory systems, determine:

1. **Primary Intent**: What is the user really asking for?
2. **Memory Needs**: Which memory types are most relevant? Why?
3. **Retrieval Strategy**: What specific memories should be retrieved?
4. **Emotional Context**: What emotional tone or relationship factors matter?
5. **Depth Required**: How deep should the memory search go?

Provide a structured retrieval plan.
"""


MEMORY_SYNTHESIS_PROMPT = """
You have retrieved the following memories in response to the query: "{query}"

{retrieved_memories}

Now synthesize these memories into a coherent context, considering:

1. **Relevance Filtering**: Which memories directly address the query?
2. **Temporal Sequencing**: How do events relate chronologically?
3. **Emotional Coloring**: What emotional significance do these memories have?
4. **Relationship Context**: How does your relationship with {user_id} affect interpretation?
5. **Knowledge Integration**: How do semantic memories inform the response?
6. **Identity Alignment**: How do these memories relate to your core values/purpose?

Create a synthesized context that will help you respond authentically.
"""


@dataclass
class MemoryRetrieval:
    """Structured memory retrieval plan."""
    memory_type: str
    purpose: str
    search_queries: List[str]
    importance: float
    emotional_filter: Optional[str] = None
    limit: int = 5


class CognitiveContextBuilder:
    """
    LLM-driven context builder that gives AI agency over memory retrieval.

    This replaces mechanical retrieval with intelligent, purpose-driven
    memory reconstruction that understands the nuances of each memory type.
    """

    def __init__(
        self,
        memory_base_path: Path,
        lancedb_storage,
        llm_provider,
        memory_indexer
    ):
        """
        Initialize cognitive context builder.

        Args:
            memory_base_path: Base path for memory storage
            lancedb_storage: LanceDB storage for semantic search
            llm_provider: LLM provider for cognitive processing
            memory_indexer: Memory indexer for retrieval
        """
        self.memory_base_path = Path(memory_base_path)
        self.lancedb = lancedb_storage
        self.llm = llm_provider
        self.indexer = memory_indexer

    def build_context(
        self,
        query: str,
        user_id: str,
        location: str = "unknown",
        focus_level: int = 3,
        include_emotions: bool = True,
        include_relationships: bool = True
    ) -> Dict[str, Any]:
        """
        Build context using LLM to understand and retrieve relevant memories.

        This gives the AI agency over its own memory by:
        1. Understanding what each memory type is for
        2. Deciding what's relevant to retrieve
        3. Interpreting memories through emotional/relational lenses
        4. Synthesizing a coherent context

        Args:
            query: The user's query/input
            user_id: User identifier
            location: Current location context
            focus_level: Depth of retrieval (0-5)
            include_emotions: Whether to apply emotional filtering
            include_relationships: Whether to consider relationship context

        Returns:
            Synthesized context with retrieved memories and interpretation
        """
        timestamp = datetime.now()

        # Step 1: Load core memory for identity context
        core_memory = self._load_core_memory()

        # Step 2: Use LLM to create retrieval plan
        retrieval_plan = self._create_retrieval_plan(
            query, user_id, location, timestamp, focus_level, core_memory
        )

        # Step 3: Execute retrieval based on LLM's plan
        retrieved_memories = self._execute_retrieval(retrieval_plan)

        # Step 4: Use LLM to synthesize context
        synthesized_context = self._synthesize_memories(
            query, user_id, retrieved_memories,
            include_emotions, include_relationships
        )

        return {
            "timestamp": timestamp.isoformat(),
            "query": query,
            "user_id": user_id,
            "location": location,
            "focus_level": focus_level,
            "retrieval_plan": retrieval_plan,
            "retrieved_memories": retrieved_memories,
            "synthesis": synthesized_context,
            "agency_notes": self._generate_agency_notes(retrieval_plan)
        }

    def _load_core_memory(self) -> Dict[str, str]:
        """Load core memory components for identity context."""
        core_path = self.memory_base_path / "core"
        core_memory = {}

        components = ["purpose", "values", "personality", "identity", "capabilities"]
        for component in components:
            file_path = core_path / f"{component}.md"
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    # Take first 200 chars as summary
                    core_memory[component] = content[:200].strip()
                except:
                    core_memory[component] = "Not yet defined"
            else:
                core_memory[component] = "Not yet defined"

        return core_memory

    def _create_retrieval_plan(
        self,
        query: str,
        user_id: str,
        location: str,
        timestamp: datetime,
        focus_level: int,
        core_memory: Dict[str, str]
    ) -> List[MemoryRetrieval]:
        """
        Use LLM to understand the query and create a retrieval plan.

        This is where the AI exercises agency - deciding what memories
        are relevant and how to retrieve them.
        """
        # Format core memory summary
        core_summary = "\n".join([
            f"- {k.title()}: {v}" for k, v in core_memory.items()
        ])

        # Build prompt
        prompt = MEMORY_TYPE_DESCRIPTIONS + "\n\n" + CONTEXT_BUILDING_PROMPT.format(
            query=query,
            user_id=user_id,
            location=location,
            timestamp=timestamp.isoformat(),
            focus_level=focus_level,
            core_memory_summary=core_summary
        )

        # Add structured output request
        prompt += """

Return a JSON array of retrieval plans:
[
    {
        "memory_type": "episodic|semantic|working|people|library|notes",
        "purpose": "Why this memory type is relevant",
        "search_queries": ["specific", "search", "terms"],
        "importance": 0.0-1.0,
        "emotional_filter": "optional emotion to filter by",
        "limit": number_of_items
    }
]

Focus on what's most relevant. Exercise agency by choosing what matters.
"""

        try:
            # Get LLM response
            response_obj = self.llm.generate(
                prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temperature for structured output
            )

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(response_obj, 'content'):
                response = response_obj.content
            elif hasattr(response_obj, 'text'):
                response = response_obj.text
            else:
                response = str(response_obj)

            # Parse JSON response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())

                # Convert to MemoryRetrieval objects
                retrieval_plan = []
                for item in plan_data:
                    retrieval_plan.append(MemoryRetrieval(
                        memory_type=item.get("memory_type", "notes"),
                        purpose=item.get("purpose", "General retrieval"),
                        search_queries=item.get("search_queries", [query]),
                        importance=item.get("importance", 0.5),
                        emotional_filter=item.get("emotional_filter"),
                        limit=item.get("limit", 5)
                    ))

                return retrieval_plan

        except Exception as e:
            logger.error(f"Failed to create retrieval plan: {e}")

        # Fallback to basic retrieval
        return [
            MemoryRetrieval(
                memory_type="notes",
                purpose="General context",
                search_queries=[query],
                importance=0.5,
                limit=5
            )
        ]

    def _execute_retrieval(self, retrieval_plan: List[MemoryRetrieval]) -> Dict[str, List[Dict]]:
        """
        Execute the retrieval plan created by the LLM.

        This is the mechanical part - actually fetching the memories
        that the AI decided it needs.
        """
        retrieved = {}

        for plan in retrieval_plan:
            memories = []

            # Execute searches for this memory type
            for search_query in plan.search_queries[:3]:  # Limit searches per type
                try:
                    if plan.memory_type == "notes" and self.lancedb:
                        results = self.lancedb.search_notes(
                            search_query,
                            filters={"emotion": plan.emotional_filter} if plan.emotional_filter else {},
                            limit=plan.limit
                        )
                        memories.extend(results)

                    elif plan.memory_type == "library" and self.lancedb:
                        results = self.lancedb.search_library(search_query, limit=plan.limit)
                        memories.extend(results)

                    elif plan.memory_type == "semantic":
                        # Direct file reading for semantic memories
                        memories.extend(self._read_semantic_memories(search_query, plan.limit))

                    elif plan.memory_type == "episodic":
                        memories.extend(self._read_episodic_memories(search_query, plan.limit))

                    elif plan.memory_type == "working":
                        memories.extend(self._read_working_memory())

                    elif plan.memory_type == "people":
                        memories.extend(self._read_people_memory(plan.search_queries[0]))  # user_id

                except Exception as e:
                    logger.error(f"Failed to retrieve {plan.memory_type}: {e}")

            if memories:
                retrieved[plan.memory_type] = memories[:plan.limit]

        return retrieved

    def _synthesize_memories(
        self,
        query: str,
        user_id: str,
        retrieved_memories: Dict[str, List[Dict]],
        include_emotions: bool,
        include_relationships: bool
    ) -> str:
        """
        Use LLM to synthesize retrieved memories into coherent context.

        This is where the AI interprets memories through emotional
        and relational lenses, exercising agency over how to understand
        and use its memories.
        """
        # Format retrieved memories
        memory_text = ""
        for memory_type, memories in retrieved_memories.items():
            memory_text += f"\n## {memory_type.title()} Memories\n"
            for i, mem in enumerate(memories[:5], 1):
                content = str(mem.get('content', ''))[:500]
                memory_text += f"\n{i}. {content}\n"

        if not memory_text:
            return "No relevant memories found for this context."

        # Build synthesis prompt
        prompt = MEMORY_SYNTHESIS_PROMPT.format(
            query=query,
            user_id=user_id,
            retrieved_memories=memory_text
        )

        # Add emotional/relational guidance if requested
        if include_emotions:
            prompt += "\n\nApply emotional interpretation - how do these memories make you feel?"

        if include_relationships:
            prompt += f"\n\nConsider your relationship with {user_id} - how does this affect your interpretation?"

        prompt += "\n\nProvide a synthesized context (max 500 words) that captures the essence of these memories as they relate to the query."

        try:
            synthesis_obj = self.llm.generate(
                prompt,
                max_tokens=800,
                temperature=0.5
            )

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(synthesis_obj, 'content'):
                synthesis = synthesis_obj.content
            elif hasattr(synthesis_obj, 'text'):
                synthesis = synthesis_obj.text
            else:
                synthesis = str(synthesis_obj)

            return synthesis.strip()

        except Exception as e:
            logger.error(f"Failed to synthesize memories: {e}")
            return "Retrieved memories are available but synthesis failed."

    def _generate_agency_notes(self, retrieval_plan: List[MemoryRetrieval]) -> str:
        """
        Generate notes about how the AI exercised agency in retrieval.

        This helps the AI understand and reflect on its memory choices.
        """
        if not retrieval_plan:
            return "No active memory retrieval performed."

        notes = "Memory Agency Exercise:\n"
        for plan in retrieval_plan:
            notes += f"- Chose to search {plan.memory_type} because: {plan.purpose}\n"

        return notes

    # Helper methods for direct memory reading

    def _read_semantic_memories(self, query: str, limit: int) -> List[Dict]:
        """Read semantic memories (insights/concepts) directly."""
        memories = []
        semantic_path = self.memory_base_path / "semantic"

        # Read insights
        insights_file = semantic_path / "insights.md"
        if insights_file.exists():
            content = insights_file.read_text(encoding='utf-8')
            # Simple search for query terms
            if query.lower() in content.lower():
                memories.append({
                    "type": "insight",
                    "content": content[:1000]
                })

        return memories[:limit]

    def _read_episodic_memories(self, query: str, limit: int) -> List[Dict]:
        """Read episodic memories (key moments) directly."""
        memories = []
        episodic_path = self.memory_base_path / "episodic"

        key_moments = episodic_path / "key_moments.md"
        if key_moments.exists():
            content = key_moments.read_text(encoding='utf-8')
            if query.lower() in content.lower():
                memories.append({
                    "type": "key_moment",
                    "content": content[:1000]
                })

        return memories[:limit]

    def _read_working_memory(self) -> List[Dict]:
        """Read current working memory."""
        memories = []
        working_path = self.memory_base_path / "working"

        current_context = working_path / "current_context.md"
        if current_context.exists():
            content = current_context.read_text(encoding='utf-8')
            if content.strip():
                memories.append({
                    "type": "current_context",
                    "content": content[:500]
                })

        return memories

    def _read_people_memory(self, user_id: str) -> List[Dict]:
        """Read memories about a specific person."""
        memories = []
        people_path = self.memory_base_path / "people" / user_id

        if people_path.exists():
            profile_file = people_path / "profile.md"
            if profile_file.exists():
                content = profile_file.read_text(encoding='utf-8')
                memories.append({
                    "type": "user_profile",
                    "content": content[:500]
                })

        return memories


class MemoryAgencyTools:
    """
    Tools that give the AI direct agency over its memory operations.

    These augment the automatic processes with voluntary memory actions.
    """

    @staticmethod
    def remember_voluntarily(
        llm_provider,
        content: str,
        memory_type: str,
        importance: float,
        reason: str
    ) -> str:
        """
        Voluntarily create a memory with conscious intent.

        This is different from automatic capture - it's the AI
        actively deciding "I want to remember this."
        """
        prompt = f"""
        You are choosing to remember something. Format it appropriately for {memory_type} memory.

        Content: {content}
        Importance: {importance}
        Reason for remembering: {reason}

        Create a structured memory entry that captures not just the content,
        but also why you chose to remember it and how it relates to your existing knowledge.
        """

        try:
            formatted_memory_obj = llm_provider.generate(prompt, max_tokens=500)

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(formatted_memory_obj, 'content'):
                formatted_memory = formatted_memory_obj.content
            elif hasattr(formatted_memory_obj, 'text'):
                formatted_memory = formatted_memory_obj.text
            else:
                formatted_memory = str(formatted_memory_obj)

            # Store in appropriate location based on type
            # This would integrate with the memory storage system

            return f"Voluntarily remembered: {formatted_memory[:100]}..."

        except Exception as e:
            return f"Failed to create voluntary memory: {e}"

    @staticmethod
    def forget_selectively(
        memory_id: str,
        reason: str
    ) -> str:
        """
        Choose to de-emphasize or mark a memory as less relevant.

        Note: We don't delete memories (that would be amnesia),
        but we can choose to reduce their importance or mark them
        as "not currently relevant."
        """
        # This would update memory importance/relevance scores
        return f"De-emphasized memory {memory_id}: {reason}"

    @staticmethod
    def reinterpret_memory(
        llm_provider,
        memory_id: str,
        new_perspective: str
    ) -> str:
        """
        Reinterpret an existing memory with new understanding.

        This is how learning happens - same memory, new interpretation.
        """
        prompt = f"""
        You are reinterpreting a memory with new understanding.

        Memory: {memory_id}
        New perspective: {new_perspective}

        How does this new perspective change your understanding of this memory?
        What new connections or insights emerge?
        """

        try:
            reinterpretation_obj = llm_provider.generate(prompt, max_tokens=500)

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(reinterpretation_obj, 'content'):
                reinterpretation = reinterpretation_obj.content
            elif hasattr(reinterpretation_obj, 'text'):
                reinterpretation = reinterpretation_obj.text
            else:
                reinterpretation = str(reinterpretation_obj)

            return reinterpretation

        except Exception as e:
            return f"Failed to reinterpret: {e}"