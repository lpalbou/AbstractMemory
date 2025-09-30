"""
Emotional Resonance System for AbstractMemory

CRITICAL DESIGN PRINCIPLE:
All cognitive assessments MUST come from the LLM itself.
NO keyword matching, NO NLP heuristics, NO pattern matching.

The LLM assesses:
- importance: How significant is this? (0.0-1.0)
- alignment_with_values: How aligned with my emerging values? (-1.0 to 1.0)
- reason: Why does this matter to me?

Formula: intensity = importance × abs(alignment_with_values)

This module only performs the mathematical calculation.
The LLM does the cognitive evaluation.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def calculate_emotional_resonance(
    importance: float,
    alignment_with_values: float,
    reason: Optional[str] = None
) -> Dict[str, any]:
    """
    Calculate emotional resonance from LLM-assessed values.

    IMPORTANT: This function ONLY performs the mathematical calculation.
    The importance and alignment_with_values MUST come from the LLM itself.

    The LLM evaluates:
    - importance: "How significant is this to me?" (0.0-1.0)
    - alignment_with_values: "Does this align with what I value?" (-1.0 to 1.0)
    - reason: "Why does this matter to me emotionally?"

    Formula:
        intensity = importance × abs(alignment_with_values)
        valence = positive (aligned) / negative (misaligned) / mixed (neutral)

    Args:
        importance: 0.0-1.0 - LLM-assessed significance
        alignment_with_values: -1.0 to 1.0 - LLM-assessed alignment
                              1.0 = perfectly aligned
                              0.0 = neutral
                             -1.0 = contradicts values
        reason: LLM-provided explanation

    Returns:
        Dict with:
        - intensity: float (0.0-1.0) - Strength of emotion
        - valence: str (positive/negative/mixed) - Emotional direction
        - reason: str - Why this emotion exists (from LLM)
        - alignment: float - The alignment value used
        - importance: float - The importance value used

    Examples:
        >>> # LLM assessed: importance=0.9, alignment=0.8
        >>> calculate_emotional_resonance(0.9, 0.8, "Breakthrough understanding")
        {
            "intensity": 0.72,
            "valence": "positive",
            "reason": "Breakthrough understanding",
            "alignment": 0.8,
            "importance": 0.9
        }

        >>> # LLM assessed: importance=0.8, alignment=-0.5 (contradicts values)
        >>> calculate_emotional_resonance(0.8, -0.5, "Contradicts intellectual honesty")
        {
            "intensity": 0.40,
            "valence": "negative",
            "reason": "Contradicts intellectual honesty",
            "alignment": -0.5,
            "importance": 0.8
        }
    """
    # Validate inputs
    importance = max(0.0, min(1.0, importance))
    alignment_with_values = max(-1.0, min(1.0, alignment_with_values))

    # Calculate intensity (absolute alignment matters for intensity)
    intensity = importance * abs(alignment_with_values)

    # Determine valence based on alignment direction
    if alignment_with_values > 0.3:
        valence = "positive"  # Aligned with values
    elif alignment_with_values < -0.3:
        valence = "negative"  # Contradicts values
    else:
        valence = "mixed"  # Neutral or ambiguous

    # Generate default reason if not provided by LLM
    if reason is None:
        if valence == "positive":
            reason = f"Aligns with core values (importance={importance:.2f}, alignment={alignment_with_values:.2f})"
        elif valence == "negative":
            reason = f"Contradicts core values (importance={importance:.2f}, alignment={alignment_with_values:.2f})"
        else:
            reason = f"Neutral alignment (importance={importance:.2f}, alignment={alignment_with_values:.2f})"

    logger.debug(f"Emotion calculated: intensity={intensity:.2f}, valence={valence}, alignment={alignment_with_values:.2f}")

    return {
        "intensity": round(intensity, 3),
        "valence": valence,
        "reason": reason,
        "alignment": round(alignment_with_values, 3),
        "importance": round(importance, 3)
    }


def format_emotion_for_display(emotion_resonance: Dict) -> str:
    """
    Format emotional resonance for human-readable display.

    Args:
        emotion_resonance: Dict from calculate_emotional_resonance()

    Returns:
        str: Formatted emotion string

    Example:
        "Positive (0.72) - Breakthrough in understanding"
    """
    valence = emotion_resonance.get("valence", "mixed").capitalize()
    intensity = emotion_resonance.get("intensity", 0.0)
    reason = emotion_resonance.get("reason", "No reason provided")

    return f"{valence} ({intensity:.2f}) - {reason}"


# Module-level statistics for observability
_emotion_calculations = 0


def get_emotion_statistics() -> Dict:
    """
    Get statistics about emotion calculations for observability.

    Returns:
        Dict with calculation counts
    """
    return {
        "emotion_calculations": _emotion_calculations
    }


def _increment_emotion_stat():
    """Internal: increment emotion calculation counter."""
    global _emotion_calculations
    _emotion_calculations += 1
