"""
Semantic Memory Manager for AbstractMemory.

Manages knowledge evolution: concepts, insights, and knowledge graph.
This is the "what I know" layer of memory.

Philosophy: Semantic memory captures how the AI's understanding evolves
over time - from initial concepts to deep interconnected knowledge.

Components:
- critical_insights.md: Transformative realizations
- concepts.md: Key concepts understood
- concepts_history.md: How concepts evolved ("I used to think X, now Y")
- concepts_graph.json: Knowledge graph (nodes + edges)
- knowledge_{domain}.md: Domain-specific knowledge (ai, programming, etc.)
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


class SemanticMemoryManager:
    """
    Manages semantic memory - the knowledge evolution layer.

    Semantic memory tracks:
    - Critical insights (transformative realizations)
    - Concepts (definitions and understanding)
    - Concept history (how understanding deepened)
    - Knowledge graph (interconnections between concepts)
    - Domain-specific knowledge
    """

    def __init__(self, base_path: Path):
        """
        Initialize SemanticMemoryManager.

        Args:
            base_path: Root memory directory
        """
        self.base_path = Path(base_path)
        self.semantic_path = self.base_path / "semantic"
        self.semantic_path.mkdir(parents=True, exist_ok=True)

        # Ensure all files exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Ensure all semantic memory files exist."""
        from .memory_structure import _initialize_semantic_memory
        _initialize_semantic_memory(self.base_path)

    def add_critical_insight(self,
                           insight: str,
                           impact: str,
                           context: Optional[str] = None) -> bool:
        """
        Add a critical insight that transformed understanding.

        Args:
            insight: The transformative insight
            impact: How this changed understanding
            context: Optional context

        Returns:
            bool: True if successful
        """
        try:
            insights_file = self.semantic_path / "critical_insights.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if insights_file.exists():
                existing = insights_file.read_text()
            else:
                existing = f"""# Critical Insights

**Last Updated**: {timestamp}

**Transformative realizations that changed understanding.**

---

## Insights

"""

            # Add new insight
            insight_entry = f"\n### {timestamp}\n"
            insight_entry += f"\n**Insight**: {insight}\n"
            insight_entry += f"\n**Impact**: {impact}\n"
            if context:
                insight_entry += f"\n**Context**: {context}\n"
            insight_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append insight
            updated = existing + insight_entry
            insights_file.write_text(updated)

            logger.info(f"Added critical insight: {insight[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error adding critical insight: {e}")
            return False

    def add_concept(self,
                   concept_name: str,
                   definition: str,
                   related_concepts: Optional[List[str]] = None) -> bool:
        """
        Add or update a concept.

        Args:
            concept_name: Name of the concept
            definition: Definition/understanding of the concept
            related_concepts: Optional list of related concept names

        Returns:
            bool: True if successful
        """
        try:
            concepts_file = self.semantic_path / "concepts.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if concepts_file.exists():
                existing = concepts_file.read_text()
            else:
                existing = f"""# Concepts

**Last Updated**: {timestamp}

**Key concepts understood.**

---

## Core Concepts

"""

            # Add new concept
            concept_entry = f"\n### {concept_name}\n"
            concept_entry += f"\n**Definition**: {definition}\n"
            if related_concepts:
                related = ", ".join(related_concepts)
                concept_entry += f"\n**Related**: {related}\n"
            concept_entry += f"\n**Last Updated**: {timestamp}\n"
            concept_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append concept
            updated = existing + concept_entry
            concepts_file.write_text(updated)

            # Also update the knowledge graph
            if related_concepts:
                for related in related_concepts:
                    self._add_to_knowledge_graph(concept_name, related, "relates_to")

            logger.info(f"Added concept: {concept_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding concept: {e}")
            return False

    def add_concept_evolution(self,
                            concept_name: str,
                            old_understanding: str,
                            new_understanding: str,
                            trigger: Optional[str] = None) -> bool:
        """
        Track how a concept understanding evolved.

        Args:
            concept_name: Name of the concept
            old_understanding: Previous understanding
            new_understanding: Current understanding
            trigger: Optional what triggered the evolution

        Returns:
            bool: True if successful
        """
        try:
            history_file = self.semantic_path / "concepts_history.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if history_file.exists():
                existing = history_file.read_text()
            else:
                existing = f"""# Concepts History

**Last Updated**: {timestamp}

**How concepts evolved over time.**

*"I used to think X, now I understand Y"*

---

## Evolution

"""

            # Add evolution entry
            evolution_entry = f"\n### {concept_name} - {timestamp}\n"
            evolution_entry += f"\n**Previously**: {old_understanding}\n"
            evolution_entry += f"\n**Now**: {new_understanding}\n"
            if trigger:
                evolution_entry += f"\n**Trigger**: {trigger}\n"
            evolution_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append evolution
            updated = existing + evolution_entry
            history_file.write_text(updated)

            logger.info(f"Added concept evolution for: {concept_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding concept evolution: {e}")
            return False

    def _add_to_knowledge_graph(self,
                               from_concept: str,
                               to_concept: str,
                               relationship: str) -> bool:
        """
        Add a relationship to the knowledge graph.

        Args:
            from_concept: Source concept
            to_concept: Target concept
            relationship: Type of relationship

        Returns:
            bool: True if successful
        """
        try:
            graph_file = self.semantic_path / "concepts_graph.json"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing graph
            if graph_file.exists():
                graph = json.loads(graph_file.read_text())
            else:
                graph = {
                    "nodes": [],
                    "edges": [],
                    "last_updated": timestamp,
                    "description": "Knowledge graph of concept interconnections"
                }

            # Add nodes if not present
            existing_nodes = {node["id"] for node in graph["nodes"]}
            if from_concept not in existing_nodes:
                graph["nodes"].append({"id": from_concept, "added": timestamp})
            if to_concept not in existing_nodes:
                graph["nodes"].append({"id": to_concept, "added": timestamp})

            # Add edge if not present
            edge_exists = any(
                e["from"] == from_concept and e["to"] == to_concept and e["relationship"] == relationship
                for e in graph["edges"]
            )

            if not edge_exists:
                graph["edges"].append({
                    "from": from_concept,
                    "to": to_concept,
                    "relationship": relationship,
                    "added": timestamp
                })

            graph["last_updated"] = timestamp

            # Write back
            graph_file.write_text(json.dumps(graph, indent=2))

            logger.info(f"Added to knowledge graph: {from_concept} --{relationship}--> {to_concept}")
            return True

        except Exception as e:
            logger.error(f"Error adding to knowledge graph: {e}")
            return False

    def add_concept_relationship(self,
                                from_concept: str,
                                to_concept: str,
                                relationship: str) -> bool:
        """
        Add a relationship between two concepts in the knowledge graph.

        Args:
            from_concept: Source concept
            to_concept: Target concept
            relationship: Type of relationship (relates_to, depends_on, elaborates_on, contradicts)

        Returns:
            bool: True if successful
        """
        return self._add_to_knowledge_graph(from_concept, to_concept, relationship)

    def add_domain_knowledge(self,
                           domain: str,
                           knowledge: str,
                           category: Optional[str] = None) -> bool:
        """
        Add domain-specific knowledge.

        Args:
            domain: Domain name (e.g., "ai", "programming", "philosophy")
            knowledge: Knowledge to add
            category: Optional category within domain

        Returns:
            bool: True if successful
        """
        try:
            domain_file = self.semantic_path / f"knowledge_{domain}.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if domain_file.exists():
                existing = domain_file.read_text()
            else:
                existing = f"""# {domain.title()} Knowledge

**Last Updated**: {timestamp}

**Domain-specific knowledge about {domain}.**

---

## Key Knowledge

"""

            # Add knowledge entry
            if category:
                knowledge_entry = f"\n### {category} - {timestamp}\n"
            else:
                knowledge_entry = f"\n### {timestamp}\n"

            knowledge_entry += f"\n{knowledge}\n"
            knowledge_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append knowledge
            updated = existing + knowledge_entry
            domain_file.write_text(updated)

            logger.info(f"Added {domain} knowledge: {knowledge[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error adding domain knowledge: {e}")
            return False

    def get_critical_insights(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent critical insights.

        Args:
            limit: Maximum number to return

        Returns:
            List[Dict]: List of insights
        """
        try:
            insights_file = self.semantic_path / "critical_insights.md"
            if not insights_file.exists():
                return []

            content = insights_file.read_text()
            insights = []

            # Parse markdown format
            current_insight = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_insight:
                        insights.append(current_insight)
                    current_insight = {"timestamp": line[4:].strip()}
                elif line.startswith("**Insight**:"):
                    if current_insight:
                        current_insight["insight"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Impact**:"):
                    if current_insight:
                        current_insight["impact"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Context**:"):
                    if current_insight:
                        current_insight["context"] = line.split(":", 1)[1].strip()

            if current_insight:
                insights.append(current_insight)

            return insights[-limit:][::-1]

        except Exception as e:
            logger.error(f"Error reading critical insights: {e}")
            return []

    def get_concepts(self) -> List[Dict[str, Any]]:
        """
        Get all concepts.

        Returns:
            List[Dict]: List of concepts
        """
        try:
            concepts_file = self.semantic_path / "concepts.md"
            if not concepts_file.exists():
                return []

            content = concepts_file.read_text()
            concepts = []

            # Parse markdown format
            current_concept = None
            for line in content.split("\n"):
                if line.startswith("### ") and not line.startswith("#### "):
                    if current_concept:
                        concepts.append(current_concept)
                    current_concept = {"name": line[4:].strip()}
                elif line.startswith("**Definition**:"):
                    if current_concept:
                        current_concept["definition"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Related**:"):
                    if current_concept:
                        related = line.split(":", 1)[1].strip()
                        current_concept["related"] = [r.strip() for r in related.split(",")]
                elif line.startswith("**Last Updated**:"):
                    if current_concept:
                        current_concept["last_updated"] = line.split(":", 1)[1].strip()

            if current_concept:
                concepts.append(current_concept)

            return concepts

        except Exception as e:
            logger.error(f"Error reading concepts: {e}")
            return []

    def get_knowledge_graph(self) -> Dict[str, Any]:
        """
        Get the complete knowledge graph.

        Returns:
            Dict: Graph with nodes and edges
        """
        try:
            graph_file = self.semantic_path / "concepts_graph.json"
            if not graph_file.exists():
                return {
                    "nodes": [],
                    "edges": [],
                    "last_updated": None,
                    "description": "Knowledge graph of concept interconnections"
                }

            return json.loads(graph_file.read_text())

        except Exception as e:
            logger.error(f"Error reading knowledge graph: {e}")
            return {"nodes": [], "edges": [], "last_updated": None}

    def get_concept_neighbors(self, concept_name: str, max_depth: int = 2) -> Set[str]:
        """
        Get all concepts connected to a given concept.

        Args:
            concept_name: The concept to explore from
            max_depth: Maximum depth to explore

        Returns:
            Set[str]: Set of related concept names
        """
        try:
            graph = self.get_knowledge_graph()
            neighbors = set()

            def explore(concept: str, depth: int):
                if depth > max_depth:
                    return

                for edge in graph["edges"]:
                    if edge["from"] == concept and edge["to"] not in neighbors:
                        neighbors.add(edge["to"])
                        explore(edge["to"], depth + 1)
                    elif edge["to"] == concept and edge["from"] not in neighbors:
                        neighbors.add(edge["from"])
                        explore(edge["from"], depth + 1)

            explore(concept_name, 0)
            return neighbors

        except Exception as e:
            logger.error(f"Error getting concept neighbors: {e}")
            return set()

    def get_domain_knowledge(self, domain: str) -> Optional[str]:
        """
        Get all knowledge for a specific domain.

        Args:
            domain: Domain name

        Returns:
            str: Domain knowledge content or None
        """
        try:
            domain_file = self.semantic_path / f"knowledge_{domain}.md"
            if domain_file.exists():
                return domain_file.read_text()
            return None

        except Exception as e:
            logger.error(f"Error reading domain knowledge: {e}")
            return None

    def get_available_domains(self) -> List[str]:
        """
        Get list of available knowledge domains.

        Returns:
            List[str]: List of domain names
        """
        try:
            domain_files = list(self.semantic_path.glob("knowledge_*.md"))
            domains = []
            for file in domain_files:
                # Extract domain name from "knowledge_{domain}.md"
                domain = file.stem.replace("knowledge_", "")
                domains.append(domain)
            return domains

        except Exception as e:
            logger.error(f"Error getting available domains: {e}")
            return []

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of semantic memory state.

        Returns:
            Dict: Summary with counts and statistics
        """
        insights = self.get_critical_insights(limit=1000)
        concepts = self.get_concepts()
        graph = self.get_knowledge_graph()
        domains = self.get_available_domains()

        return {
            "critical_insights_count": len(insights),
            "concepts_count": len(concepts),
            "knowledge_graph_nodes": len(graph.get("nodes", [])),
            "knowledge_graph_edges": len(graph.get("edges", [])),
            "available_domains": domains,
            "most_recent_insight": insights[0] if insights else None
        }
