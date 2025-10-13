"""
Enhanced fact extraction using AbstractCore's BasicExtractor.

This module integrates AbstractCore's semantic extraction capabilities
with AbstractMemory's memory system.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# AbstractCore imports
from abstractllm.processing.basic_extractor import BasicExtractor
from abstractllm.utils.structured_logging import get_logger

# AbstractMemory imports
from .memory_response_models import MemoryAction

logger = get_logger(__name__)


class MemoryFactExtractor:
    """
    Enhanced fact extractor that uses AbstractCore's BasicExtractor
    to extract structured knowledge for AbstractMemory.
    """

    def __init__(self, provider: Optional[Any] = None, memory_session: Optional[Any] = None):
        """
        Initialize the fact extractor.

        Args:
            provider: LLM provider for extraction
            memory_session: MemorySession for storing extracted facts
        """
        self.provider = provider
        self.memory_session = memory_session
        self.logger = get_logger(__name__)

        # Initialize AbstractCore's BasicExtractor
        try:
            self.extractor = BasicExtractor(llm=provider) if provider else BasicExtractor()
            self.logger.info("MemoryFactExtractor initialized with AbstractCore BasicExtractor")
        except Exception as e:
            self.logger.error("Failed to initialize BasicExtractor", error=str(e))
            self.extractor = None

    def extract_facts_from_conversation(
        self,
        conversation_text: str,
        domain_focus: Optional[str] = None,
        importance_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Extract facts from a conversation for memory storage.

        Args:
            conversation_text: The conversation text to analyze
            domain_focus: Optional domain to focus extraction on
            importance_threshold: Minimum importance score for facts

        Returns:
            Dict with extracted facts and suggested memory actions
        """
        if not self.extractor:
            return {"error": "BasicExtractor not available"}

        try:
            self.logger.info("Extracting facts from conversation",
                           text_length=len(conversation_text),
                           domain_focus=domain_focus)

            # Extract knowledge using AbstractCore (TRIPLES format for clean semantic relationships)
            extraction_result = self.extractor.extract(
                text=conversation_text,
                domain_focus=domain_focus,
                length="standard",  # 15 entities max for conversation
                output_format="triples"  # Extract as SUBJECT-PREDICATE-OBJECT triples
            )

            # Convert extraction to memory-friendly format
            memory_facts = self._convert_extraction_to_memory_facts(
                extraction_result,
                importance_threshold
            )

            # Generate memory actions for storing facts
            memory_actions = self._generate_memory_actions(memory_facts)

            result = {
                "extracted_facts": memory_facts,
                "memory_actions": memory_actions,
                "raw_extraction": extraction_result,
                "statistics": {
                    "entities_extracted": len(extraction_result.get("entities", {})),
                    "relationships_extracted": len(extraction_result.get("triples", [])),
                    "memory_actions_generated": len(memory_actions)
                }
            }

            self.logger.info("Fact extraction completed",
                           entities=result["statistics"]["entities_extracted"],
                           relationships=result["statistics"]["relationships_extracted"],
                           memory_actions=result["statistics"]["memory_actions_generated"])

            return result

        except Exception as e:
            self.logger.error("Fact extraction failed", error=str(e))
            return {"error": str(e)}

    def extract_facts_from_document(
        self,
        document_text: str,
        source_path: Optional[str] = None,
        domain_focus: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract facts from a document for library storage.

        Args:
            document_text: The document text to analyze
            source_path: Path to the source document
            domain_focus: Optional domain to focus extraction on

        Returns:
            Dict with extracted facts and document metadata
        """
        if not self.extractor:
            return {"error": "BasicExtractor not available"}

        try:
            self.logger.info("Extracting facts from document",
                           text_length=len(document_text),
                           source_path=source_path,
                           domain_focus=domain_focus)

            # Use more comprehensive extraction for documents (TRIPLES format)
            extraction_result = self.extractor.extract(
                text=document_text,
                domain_focus=domain_focus,
                length="detailed",  # 25 entities max for documents
                output_format="triples"  # Extract as SUBJECT-PREDICATE-OBJECT triples
            )

            # Convert to memory-friendly format
            document_facts = self._convert_extraction_to_document_facts(
                extraction_result,
                source_path
            )

            result = {
                "document_facts": document_facts,
                "extraction_summary": self._create_extraction_summary(extraction_result),
                "raw_extraction": extraction_result,
                "source_metadata": {
                    "source_path": source_path,
                    "extraction_timestamp": datetime.now().isoformat(),
                    "domain_focus": domain_focus
                }
            }

            self.logger.info("Document fact extraction completed",
                           entities=len(document_facts.get("entities", [])),
                           relationships=len(document_facts.get("relationships", [])),
                           source_path=source_path)

            return result

        except Exception as e:
            self.logger.error("Document fact extraction failed", error=str(e), source_path=source_path)
            return {"error": str(e)}

    def refine_existing_facts(
        self,
        original_text: str,
        existing_facts: Dict[str, Any],
        domain_focus: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refine existing fact extraction using AbstractCore's refinement capabilities.

        Args:
            original_text: The original text that was extracted from
            existing_facts: Previously extracted facts in JSON-LD format
            domain_focus: Optional domain focus for refinement

        Returns:
            Dict with refined facts
        """
        if not self.extractor:
            return {"error": "BasicExtractor not available"}

        try:
            self.logger.info("Refining existing facts",
                           text_length=len(original_text),
                           domain_focus=domain_focus)

            # Use AbstractCore's refinement capability
            refined_result = self.extractor.refine_extraction(
                text=original_text,
                previous_extraction=existing_facts,
                domain_focus=domain_focus,
                length="standard"
            )

            result = {
                "refined_facts": refined_result,
                "refinement_summary": self._create_refinement_summary(
                    existing_facts, refined_result
                ),
                "raw_refinement": refined_result
            }

            self.logger.info("Fact refinement completed")
            return result

        except Exception as e:
            self.logger.error("Fact refinement failed", error=str(e))
            return {"error": str(e)}

    def _convert_extraction_to_memory_facts(
        self,
        extraction_result: Dict[str, Any],
        importance_threshold: float
    ) -> List[Dict[str, Any]]:
        """Convert AbstractCore triple extraction to memory-friendly facts."""
        memory_facts = []

        # Process entities from triple format
        entities = extraction_result.get("entities", {})
        for entity_id, entity_data in entities.items():
            confidence = entity_data.get("confidence", 0.5)
            if confidence >= importance_threshold:
                fact = {
                    "type": "entity",
                    "id": entity_id,
                    "name": entity_data.get("name", ""),
                    "entity_type": entity_data.get("type", ""),
                    "description": entity_data.get("description", ""),
                    "confidence": confidence,
                    "importance": min(confidence, 1.0)
                }
                memory_facts.append(fact)

        # Process triples as relationships
        for triple in extraction_result.get("triples", []):
            confidence = triple.get("confidence", 0.5)
            if confidence >= importance_threshold:
                fact = {
                    "type": "triple",
                    "subject": triple["subject_name"],
                    "predicate": triple["predicate"],
                    "object": triple["object_name"],
                    "triple_text": triple["triple_text"],  # "OpenAI creates GPT-4"
                    "subject_id": triple["subject"],
                    "object_id": triple["object"],
                    "confidence": confidence,
                    "importance": min(confidence, 1.0),
                    "strength": triple.get("strength", 0.5),
                    "description": triple.get("description", "")
                }
                memory_facts.append(fact)

        return memory_facts

    def _convert_extraction_to_document_facts(
        self,
        extraction_result: Dict[str, Any],
        source_path: Optional[str]
    ) -> Dict[str, Any]:
        """Convert AbstractCore triple extraction to document-specific format."""
        entities = extraction_result.get("entities", {})
        triples = extraction_result.get("triples", [])

        return {
            "entities": entities,
            "triples": triples,
            "simple_triples": extraction_result.get("simple_triples", []),
            "source_path": source_path,
            "extraction_context": extraction_result.get("context", {}),
            "extraction_metadata": {
                "entities_count": len(entities),
                "triples_count": len(triples),
                "extraction_timestamp": datetime.now().isoformat()
            }
        }

    def _generate_memory_actions(
        self,
        memory_facts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate memory actions for storing extracted facts."""
        memory_actions = []

        for fact in memory_facts:
            if fact["type"] == "entity":
                # Create memory action for entity
                action = {
                    "action": "remember",
                    "content": f"{fact['name']}: {fact['description']}",
                    "importance": fact["importance"],
                    "emotion": "neutral",
                    "reason": f"Extracted entity of type {fact['entity_type']} from conversation",
                    "metadata": {
                        "extraction_type": "entity",
                        "entity_id": fact["id"],
                        "entity_type": fact["entity_type"],
                        "confidence": fact["confidence"]
                    }
                }
                memory_actions.append(action)

            elif fact["type"] == "triple":
                # Create memory action for semantic triple
                action = {
                    "action": "remember",
                    "content": fact["triple_text"],  # "OpenAI creates GPT-4"
                    "importance": fact["importance"],
                    "emotion": "neutral",
                    "reason": f"Extracted semantic triple: {fact['predicate']} relationship",
                    "metadata": {
                        "extraction_type": "triple",
                        "subject": fact["subject"],
                        "predicate": fact["predicate"],
                        "object": fact["object"],
                        "subject_id": fact["subject_id"],
                        "object_id": fact["object_id"],
                        "confidence": fact["confidence"],
                        "strength": fact["strength"]
                    }
                }
                memory_actions.append(action)

        return memory_actions

    def _extract_entity_name(self, entity_ref: Any) -> str:
        """Extract entity name from reference."""
        if isinstance(entity_ref, dict):
            return entity_ref.get("@id", "unknown").replace("e:", "")
        return str(entity_ref).replace("e:", "") if entity_ref else "unknown"

    def _create_extraction_summary(self, extraction_result: Dict[str, Any]) -> str:
        """Create a human-readable summary of the extraction."""
        entities = extraction_result.get("entities", {})
        triples = extraction_result.get("triples", [])

        entity_names = [entity_data.get("name", "Unknown")
                       for entity_data in list(entities.values())[:5]]

        summary = f"Extracted {len(entities)} entities and {len(triples)} triples. "
        if entity_names:
            summary += f"Key entities: {', '.join(entity_names)}"
            if len(entities) > 5:
                summary += f" and {len(entities) - 5} more"

        return summary

    def _create_refinement_summary(
        self,
        original: Dict[str, Any],
        refined: Dict[str, Any]
    ) -> str:
        """Create a summary of refinement changes."""
        orig_entities = len(original.get("entities", {}))
        orig_triples = len(original.get("triples", []))

        ref_entities = len(refined.get("entities", {}))
        ref_triples = len(refined.get("triples", []))

        return (
            f"Refined extraction: {orig_entities} → {ref_entities} entities, "
            f"{orig_triples} → {ref_triples} triples"
        )


def create_fact_extractor(provider=None, memory_session=None) -> MemoryFactExtractor:
    """
    Create a MemoryFactExtractor instance.

    Args:
        provider: LLM provider for extraction
        memory_session: MemorySession for storing facts

    Returns:
        MemoryFactExtractor instance
    """
    return MemoryFactExtractor(provider=provider, memory_session=memory_session)