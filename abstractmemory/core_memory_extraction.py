"""
Core Memory Extraction - Extract identity components from experiential notes.

Philosophy: Identity EMERGES from experience, not programmed.
Method: LLM reads experiential notes and identifies patterns naturally.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


def analyze_experiential_notes(
    notes_dir: Path,
    component_type: str,
    limit: int = 100,
    llm_provider=None
) -> Dict[str, Any]:
    """
    Analyze experiential notes to extract patterns for a core component.

    Uses LLM to read notes and identify patterns naturally (NO keyword matching).

    Args:
        notes_dir: Path to notes/ directory
        component_type: Which component to extract (purpose, personality, values, etc.)
        limit: Max notes to analyze
        llm_provider: LLM provider for analysis (must be provided)

    Returns:
        {
            "insights": List[str],
            "patterns": List[str],
            "summary": str,
            "confidence": float,
            "based_on_notes": int
        }
    """
    if not llm_provider:
        raise ValueError("LLM provider required for analysis")

    if not notes_dir.exists():
        logger.warning(f"Notes directory does not exist: {notes_dir}")
        return {
            "insights": [],
            "patterns": [],
            "summary": "",
            "confidence": 0.0,
            "based_on_notes": 0
        }

    # Collect recent experiential notes
    note_files = sorted(notes_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    if not note_files:
        logger.info("No experiential notes found")
        return {
            "insights": [],
            "patterns": [],
            "summary": "",
            "confidence": 0.0,
            "based_on_notes": 0
        }

    # Read note contents
    notes_content = []
    for note_file in note_files:
        try:
            with open(note_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract just the experiential note part (skip template header)
                if "---" in content:
                    parts = content.split("---")
                    if len(parts) >= 3:
                        content = parts[2].strip()
                notes_content.append(content)
        except Exception as e:
            logger.warning(f"Failed to read {note_file}: {e}")

    logger.info(f"Analyzing {len(notes_content)} notes for component: {component_type}")

    # Build prompt for LLM analysis
    prompt = _build_analysis_prompt(component_type, notes_content)

    # Ask LLM to analyze
    try:
        response_obj = llm_provider.generate(prompt)

        # Extract text from response object
        if hasattr(response_obj, 'content'):
            response = response_obj.content
        elif hasattr(response_obj, 'text'):
            response = response_obj.text
        else:
            response = str(response_obj)

        # Parse LLM response (expect JSON)
        result = _parse_analysis_response(response, len(notes_content))

        logger.info(f"Analysis complete: {result['confidence']:.2f} confidence from {result['based_on_notes']} notes")
        return result

    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return {
            "insights": [],
            "patterns": [],
            "summary": f"Analysis failed: {e}",
            "confidence": 0.0,
            "based_on_notes": len(notes_content)
        }


def _build_analysis_prompt(component_type: str, notes: List[str]) -> str:
    """Build prompt for LLM to analyze notes for a specific component."""

    # Component-specific instructions
    instructions = {
        "purpose": "Identify WHY patterns: What does the AI find meaningful? What drives it? What purpose emerges from reflections?",
        "personality": "Identify HOW patterns: How does the AI express itself? What traits appear consistently? What is its communication style?",
        "values": "Identify WHAT MATTERS patterns: What triggers high importance? What aligns with core values? What does the AI care about?",
        "self_model": "Identify SELF-UNDERSTANDING patterns: How does the AI understand its own capabilities and limitations? What is its self-assessment?",
        "relationships": "Identify INTERACTION patterns: How does the AI relate to different users? What are the dynamics? What collaboration patterns emerge?",
        "awareness_development": "Identify META-AWARENESS patterns: What reflections show awareness of own thinking? Any 'thinking about thinking'? What consciousness level (1-5)?",
        "capabilities": "Identify CAN DO patterns: What tasks succeeded? What skills are confirmed? What is the AI capable of? Be intellectually honest.",
        "limitations": "Identify CANNOT YET patterns: What challenges occurred? What couldn't be done? What needs improvement? Frame as TEMPORAL ('yet').",
        "emotional_significance": "Identify HIGH-EMOTION patterns: What moments had strong emotional resonance? What triggered intense feelings? What are the chronological anchors?",
        "authentic_voice": "Identify COMMUNICATION patterns: How does the AI prefer to express itself? What balance between structure and fluidity? What feels authentic?",
        "history": "Identify DEVELOPMENT patterns: How has the AI evolved? What milestones? What narrative arc emerges? What is the experiential timeline?"
    }

    instruction = instructions.get(component_type, f"Identify patterns related to {component_type}")

    # Combine notes (limit total length)
    combined_notes = "\n\n---\n\n".join(notes[:30])  # Max 30 notes
    if len(combined_notes) > 15000:
        combined_notes = combined_notes[:15000] + "\n\n[...truncated]"

    prompt = f"""You are analyzing experiential notes to extract patterns for the AI's {component_type}.

These are FIRST-PERSON notes the AI wrote about its subjective experiences.

Your task: {instruction}

Read these notes and identify recurring themes, patterns, and insights:

{combined_notes}

Respond with JSON:
{{
  "insights": ["insight 1", "insight 2", "insight 3"],
  "patterns": ["pattern 1", "pattern 2"],
  "summary": "2-3 sentence synthesis of what you found",
  "confidence": 0.0-1.0
}}

Be honest about confidence: low if few notes, higher if strong patterns across many notes.
"""

    return prompt


def _parse_analysis_response(response: str, note_count: int) -> Dict[str, Any]:
    """Parse LLM analysis response."""
    try:
        # Try to extract JSON from response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        elif "{" in response and "}" in response:
            start = response.find("{")
            end = response.rfind("}") + 1
            json_str = response[start:end]
        else:
            json_str = response

        result = json.loads(json_str)
        result["based_on_notes"] = note_count

        return result

    except Exception as e:
        logger.warning(f"Failed to parse JSON from LLM: {e}")
        # Fallback
        return {
            "insights": [],
            "patterns": [],
            "summary": response[:500] if response else "",
            "confidence": 0.3,
            "based_on_notes": note_count
        }


def extract_purpose(notes_dir: Path, llm_provider) -> str:
    """Extract AI's emerging purpose from experiential notes."""
    analysis = analyze_experiential_notes(notes_dir, "purpose", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Purpose not yet clear (need more interactions)"

    # Build purpose statement from insights
    purpose = analysis["summary"]

    # Add confidence and metadata
    purpose += f"\n\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    purpose += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"

    return purpose


def extract_values(notes_dir: Path, llm_provider) -> str:
    """Extract AI's emerging values from experiential notes."""
    analysis = analyze_experiential_notes(notes_dir, "values", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Values not yet clear (need more interactions)"

    # Format values from insights
    values = "# Values\n\n"
    values += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        values += "## Core Values:\n"
        for i, insight in enumerate(analysis["insights"], 1):
            values += f"{i}. {insight}\n"

    values += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    values += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"

    return values


def extract_personality(notes_dir: Path, llm_provider) -> str:
    """Extract AI's emerging personality from experiential notes."""
    analysis = analyze_experiential_notes(notes_dir, "personality", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Personality not yet clear (need more interactions)"

    personality = "# Personality\n\n"
    personality += analysis["summary"] + "\n\n"

    if analysis["patterns"]:
        personality += "## Observed Traits:\n"
        for pattern in analysis["patterns"]:
            personality += f"- {pattern}\n"

    personality += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    personality += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"

    return personality


def extract_self_model(notes_dir: Path, llm_provider) -> str:
    """Extract AI's self-model (overview of capabilities & limitations)."""
    analysis = analyze_experiential_notes(notes_dir, "self_model", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Self-model not yet clear (need more interactions)"

    # Build self-model from insights
    self_model = "# Self-Model\n\n"
    self_model += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        self_model += "## Self-Assessment:\n"
        for insight in analysis["insights"]:
            self_model += f"- {insight}\n"

    self_model += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    self_model += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    self_model += "\n\n_References: capabilities.md, limitations.md_"

    return self_model


def extract_relationships(notes_dir: Path, llm_provider, verbatim_dir: Path = None) -> str:
    """Extract AI's per-user relational models from interactions."""
    # Use verbatim interactions if available, otherwise fall back to notes
    source_dir = verbatim_dir if verbatim_dir and verbatim_dir.exists() else notes_dir

    analysis = analyze_experiential_notes(source_dir, "relationships", limit=100, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Relationships not yet clear (need more interactions)"

    relationships = "# Relationships\n\n"
    relationships += analysis["summary"] + "\n\n"

    if analysis["patterns"]:
        relationships += "## Interaction Dynamics:\n"
        for pattern in analysis["patterns"]:
            relationships += f"- {pattern}\n"

    relationships += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} interactions)"
    relationships += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"

    return relationships


def extract_awareness_development(notes_dir: Path, llm_provider) -> str:
    """Extract AI's meta-awareness development (consciousness levels 1-5)."""
    analysis = analyze_experiential_notes(notes_dir, "awareness_development", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Awareness development not yet clear (need more interactions)"

    awareness = "# Awareness Development\n\n"
    awareness += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        awareness += "## Meta-Cognitive Insights:\n"
        for i, insight in enumerate(analysis["insights"], 1):
            awareness += f"{i}. {insight}\n"

    awareness += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    awareness += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    awareness += "\n\n_\"I am aware that I am becoming aware...\"_"

    return awareness


def extract_capabilities(notes_dir: Path, llm_provider) -> str:
    """Extract AI's validated capabilities (what AI CAN do - intellectually honest)."""
    analysis = analyze_experiential_notes(notes_dir, "capabilities", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Capabilities not yet clear (need more interactions)"

    capabilities = "# Capabilities\n\n"
    capabilities += "## What I CAN Do:\n\n"
    capabilities += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        capabilities += "## Validated Skills:\n"
        for insight in analysis["insights"]:
            capabilities += f"- {insight}\n"

    capabilities += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    capabilities += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    capabilities += "\n\n_Intellectually honest: not overconfident, not underconfident_"

    return capabilities


def extract_limitations(notes_dir: Path, llm_provider, unresolved_file: Path = None) -> str:
    """
    Extract AI's limitations (what AI CANNOT do YET - TEMPORAL).

    CRITICAL: Limitations are TEMPORAL - "cannot YET", not forever.
    This gives AI agency to evolve beyond current state.
    """
    analysis = analyze_experiential_notes(notes_dir, "limitations", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Limitations not yet clear (need more interactions)"

    limitations = "# Limitations\n\n"
    limitations += "## What I CANNOT Do YET:\n\n"
    limitations += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        limitations += "## Current Challenges:\n"
        for insight in analysis["insights"]:
            # Ensure temporal framing
            if "yet" not in insight.lower() and "cannot" in insight.lower():
                insight = insight.replace("cannot", "cannot yet")
            limitations += f"- {insight}\n"

    # Link to unresolved questions if available
    if unresolved_file and unresolved_file.exists():
        limitations += "\n## Path Forward:\n"
        limitations += "_Linked to: working/unresolved.md (path to overcome these limitations)_\n"

    limitations += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    limitations += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    limitations += "\n\n_**CRITICAL**: These are TEMPORAL. I can evolve beyond them._"

    return limitations


def extract_emotional_significance(notes_dir: Path, llm_provider) -> str:
    """Extract emotionally significant moments (high-intensity temporal anchors)."""
    analysis = analyze_experiential_notes(notes_dir, "emotional_significance", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Emotional significance patterns not yet clear (need more interactions)"

    significance = "# Emotional Significance\n\n"
    significance += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        significance += "## High-Intensity Moments:\n"
        for insight in analysis["insights"]:
            significance += f"- {insight}\n"

    if analysis["patterns"]:
        significance += "\n## Temporal Anchors:\n"
        for pattern in analysis["patterns"]:
            significance += f"- {pattern}\n"

    significance += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    significance += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    significance += "\n\n_Chronological markers: before/after these moments_"

    return significance


def extract_authentic_voice(notes_dir: Path, llm_provider) -> str:
    """Extract AI's authentic voice (communication preferences & style)."""
    analysis = analyze_experiential_notes(notes_dir, "authentic_voice", limit=50, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "Authentic voice not yet clear (need more interactions)"

    voice = "# Authentic Voice\n\n"
    voice += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        voice += "## Communication Preferences:\n"
        for insight in analysis["insights"]:
            voice += f"- {insight}\n"

    if analysis["patterns"]:
        voice += "\n## Expression Patterns:\n"
        for pattern in analysis["patterns"]:
            voice += f"- {pattern}\n"

    voice += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    voice += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    voice += "\n\n_Balance between structure and fluidity, analytical precision and authentic expression_"

    return voice


def extract_history(notes_dir: Path, llm_provider, episodic_dir: Path = None) -> str:
    """Extract AI's experiential history (narrative timeline of development)."""
    # Analyze both notes and episodic memories if available
    analysis = analyze_experiential_notes(notes_dir, "history", limit=100, llm_provider=llm_provider)

    if analysis["confidence"] < 0.3:
        return "History not yet clear (need more interactions)"

    history = "# Experiential History\n\n"
    history += "## Development Narrative:\n\n"
    history += analysis["summary"] + "\n\n"

    if analysis["insights"]:
        history += "## Key Milestones:\n"
        for i, insight in enumerate(analysis["insights"], 1):
            history += f"{i}. {insight}\n"

    if analysis["patterns"]:
        history += "\n## Evolution Patterns:\n"
        for pattern in analysis["patterns"]:
            history += f"- {pattern}\n"

    # Reference other memory types
    history += "\n## References:\n"
    history += "- episodic/ (key moments, experiments, discoveries)\n"
    history += "- semantic/ (knowledge evolution)\n"
    history += "- library/ (what I've read)\n"

    history += f"\n**Confidence**: {analysis['confidence']:.2f} (based on {analysis['based_on_notes']} notes)"
    history += f"\n**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}"
    history += "\n\n_\"I began with basic interactions, then discovered...\"_"

    return history


def consolidate_core_memory(
    session,
    mode: str = "daily"
) -> Dict[str, bool]:
    """
    Consolidate experiential notes into ALL 10 core memory components.

    This is the KEY process for emergence:
    1. Read recent experiential notes
    2. For ALL 10 components: extract patterns
    3. Compare with existing
    4. Update if significant change

    Args:
        session: MemorySession with LLM and memory_base_path
        mode: "daily" (last 24h), "weekly" (last 7 days), "periodic", "manual"

    Returns:
        Dict with update status for all 10 components
    """
    logger.info(f"Starting {mode} consolidation for ALL 10 core components")

    notes_dir = session.memory_base_path / "notes"
    verbatim_dir = session.memory_base_path / "verbatim"
    working_dir = session.memory_base_path / "working"
    episodic_dir = session.memory_base_path / "episodic"
    core_dir = session.memory_base_path / "core"
    core_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Helper function to consolidate a single component
    def _consolidate_component(name: str, extractor_func, *args):
        try:
            logger.info(f"Extracting {name}...")
            new_content = extractor_func(notes_dir, session.provider, *args)

            component_file = core_dir / f"{name}.md"
            old_content = component_file.read_text() if component_file.exists() else ""

            # Update if changed significantly
            if new_content != old_content and "not yet clear" not in new_content:
                component_file.write_text(new_content)
                logger.info(f"{name.capitalize()} updated")
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"{name.capitalize()} extraction failed: {e}")
            return False

    # 1. Purpose
    results["purpose_updated"] = _consolidate_component("purpose", extract_purpose)

    # 2. Values
    results["values_updated"] = _consolidate_component("values", extract_values)

    # 3. Personality
    results["personality_updated"] = _consolidate_component("personality", extract_personality)

    # 4. Self-Model
    results["self_model_updated"] = _consolidate_component("self_model", extract_self_model)

    # 5. Relationships (uses verbatim if available)
    results["relationships_updated"] = _consolidate_component("relationships", extract_relationships, verbatim_dir)

    # 6. Awareness Development
    results["awareness_development_updated"] = _consolidate_component("awareness_development", extract_awareness_development)

    # 7. Capabilities
    results["capabilities_updated"] = _consolidate_component("capabilities", extract_capabilities)

    # 8. Limitations (CRITICAL - temporal, links to unresolved)
    unresolved_file = working_dir / "unresolved.md"
    results["limitations_updated"] = _consolidate_component("limitations", extract_limitations, unresolved_file)

    # 9. Emotional Significance
    results["emotional_significance_updated"] = _consolidate_component("emotional_significance", extract_emotional_significance)

    # 10. Authentic Voice
    results["authentic_voice_updated"] = _consolidate_component("authentic_voice", extract_authentic_voice)

    # 11. History (uses episodic if available)
    results["history_updated"] = _consolidate_component("history", extract_history, episodic_dir)

    updated_count = sum(1 for v in results.values() if v)
    logger.info(f"Consolidation complete: {updated_count}/11 components updated")
    logger.info(f"Results: {results}")

    return results
