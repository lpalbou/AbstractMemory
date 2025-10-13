"""
Pydantic models for AbstractMemory structured responses.

These models define the structure that the LLM should return for memory-enhanced conversations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MemoryAction(BaseModel):
    """A memory action that the LLM wants to perform."""
    action: str = Field(..., description="Type of memory action: remember, link, search, reflect")
    content: Optional[str] = Field(None, description="Content to remember (for remember action)")
    importance: Optional[float] = Field(None, description="Importance score 0.0-1.0 (for remember action)")
    alignment_with_values: Optional[float] = Field(None, description="Value alignment -1.0 to 1.0 (for remember action)")
    reason: Optional[str] = Field(None, description="Why this action matters")
    emotion: Optional[str] = Field(None, description="Associated emotion")
    links_to: Optional[List[str]] = Field(None, description="IDs to link to (for remember/link actions)")

    # Additional fields for other actions
    query: Optional[str] = Field(None, description="Search query (for search action)")
    topic: Optional[str] = Field(None, description="Reflection topic (for reflect action)")
    from_id: Optional[str] = Field(None, description="Source memory ID (for link action)")
    to_id: Optional[str] = Field(None, description="Target memory ID (for link action)")
    relationship: Optional[str] = Field(None, description="Relationship type (for link action)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters (for search action)")
    limit: Optional[int] = Field(None, description="Result limit (for search action)")


class EmotionalResonance(BaseModel):
    """Emotional resonance assessment by the LLM."""
    importance: float = Field(..., description="How significant is this interaction (0.0-1.0)")
    alignment_with_values: float = Field(..., description="How well this aligns with LLM values (-1.0 to 1.0)")
    reason: str = Field(..., description="Why this matters emotionally and how it aligns with values")


class MemoryResponse(BaseModel):
    """Complete structured response from LLM with memory capabilities."""
    answer: str = Field(..., description="The actual response that the user will see")
    experiential_note: Optional[str] = Field(
        None,
        description="Personal first-person note about the interaction - AI's internal processing"
    )
    memory_actions: Optional[List[MemoryAction]] = Field(
        default_factory=list,
        description="Memory actions the AI wants to perform"
    )
    unresolved_questions: Optional[List[str]] = Field(
        default_factory=list,
        description="Open questions or uncertainties remaining"
    )
    emotional_resonance: Optional[EmotionalResonance] = Field(
        None,
        description="Assessment of emotional significance and value alignment"
    )


class SimpleMemoryResponse(BaseModel):
    """Simplified response for tool-based interactions."""
    answer: str = Field(..., description="The response to the user")
    experiential_note: Optional[str] = Field(None, description="Optional internal note")


class ReflectionResponse(BaseModel):
    """Response structure for reflection operations."""
    insights: List[str] = Field(..., description="Key insights discovered")
    patterns: List[str] = Field(..., description="Patterns identified across memories")
    contradictions: Optional[List[str]] = Field(default_factory=list, description="Contradictions found")
    evolution: Optional[str] = Field(None, description="How understanding has evolved")
    unresolved: Optional[List[str]] = Field(default_factory=list, description="Remaining unresolved questions")
    confidence: float = Field(..., description="Confidence in the reflection quality (0.0-1.0)")


class MemorySearchResult(BaseModel):
    """Result from memory search operation."""
    memories: List[Dict[str, Any]] = Field(..., description="Retrieved memories")
    total_found: int = Field(..., description="Total number of memories found")
    query_used: str = Field(..., description="The query that was used")
    reasoning: Optional[str] = Field(None, description="Why these memories were selected")