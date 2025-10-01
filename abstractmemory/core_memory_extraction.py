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
        response = llm_provider.generate(prompt)

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
        "capabilities": "Identify CAN DO patterns: What tasks succeeded? What skills are confirmed? What is the AI capable of?",
        "limitations": "Identify CANNOT YET patterns: What challenges occurred? What couldn't be done? What needs improvement?"
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


def consolidate_core_memory(
    session,
    mode: str = "daily"
) -> Dict[str, bool]:
    """
    Consolidate experiential notes into core memory.

    This is the KEY process for emergence:
    1. Read recent experiential notes
    2. For key components: extract patterns
    3. Compare with existing
    4. Update if significant change

    Args:
        session: MemorySession with LLM and memory_base_path
        mode: "daily" (last 24h) or "weekly" (last 7 days)

    Returns:
        {"purpose_updated": bool, "values_updated": bool, "personality_updated": bool}
    """
    logger.info(f"Starting {mode} consolidation")

    notes_dir = session.memory_base_path / "notes"
    core_dir = session.memory_base_path / "core"
    core_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Extract purpose
    try:
        logger.info("Extracting purpose...")
        new_purpose = extract_purpose(notes_dir, session.provider)

        purpose_file = core_dir / "purpose.md"
        old_content = purpose_file.read_text() if purpose_file.exists() else ""

        # Update if changed significantly
        if new_purpose != old_content and "not yet clear" not in new_purpose:
            purpose_file.write_text(new_purpose)
            results["purpose_updated"] = True
            logger.info("Purpose updated")
        else:
            results["purpose_updated"] = False
    except Exception as e:
        logger.error(f"Purpose extraction failed: {e}")
        results["purpose_updated"] = False

    # Extract values
    try:
        logger.info("Extracting values...")
        new_values = extract_values(notes_dir, session.provider)

        values_file = core_dir / "values.md"
        old_content = values_file.read_text() if values_file.exists() else ""

        if new_values != old_content and "not yet clear" not in new_values:
            values_file.write_text(new_values)
            results["values_updated"] = True
            logger.info("Values updated")
        else:
            results["values_updated"] = False
    except Exception as e:
        logger.error(f"Values extraction failed: {e}")
        results["values_updated"] = False

    # Extract personality
    try:
        logger.info("Extracting personality...")
        new_personality = extract_personality(notes_dir, session.provider)

        personality_file = core_dir / "personality.md"
        old_content = personality_file.read_text() if personality_file.exists() else ""

        if new_personality != old_content and "not yet clear" not in new_personality:
            personality_file.write_text(new_personality)
            results["personality_updated"] = True
            logger.info("Personality updated")
        else:
            results["personality_updated"] = False
    except Exception as e:
        logger.error(f"Personality extraction failed: {e}")
        results["personality_updated"] = False

    logger.info(f"Consolidation complete: {results}")
    return results
