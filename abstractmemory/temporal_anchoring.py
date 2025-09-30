"""
Temporal Anchoring System for AbstractMemory

High-emotion events become temporal anchors - "before/after" moments that mark
significant turning points in AI development.

These anchors:
- Mark divisions in experiential history
- Become episodic memory markers
- Modulate learning rate (high-emotion → deeper encoding)
- Track emotional significance over time

Threshold: emotion_intensity > 0.7 creates temporal anchor
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# High-emotion threshold for temporal anchors
ANCHOR_THRESHOLD = 0.7  # 0.0-1.0 scale


def is_anchor_event(emotion_intensity: float) -> bool:
    """
    Determine if an event should become a temporal anchor.

    Args:
        emotion_intensity: 0.0-1.0 emotion intensity score

    Returns:
        bool: True if intensity exceeds anchor threshold

    Threshold: 0.7 (top 20-30% of emotions)
    """
    return emotion_intensity > ANCHOR_THRESHOLD


def create_temporal_anchor(
    memory_id: str,
    content: str,
    emotion_resonance: Dict,
    timestamp: datetime,
    memory_base_path: Path
) -> str:
    """
    Create a temporal anchor for a high-emotion event.

    This adds the event to:
    1. episodic/key_moments.md (chronological markers)
    2. core/emotional_significance.md (significance tracking)

    Args:
        memory_id: Unique memory identifier
        content: Memory content (what happened)
        emotion_resonance: Dict with intensity, valence, reason
        timestamp: When this occurred
        memory_base_path: Base path for memory storage

    Returns:
        str: anchor_id

    Example:
        create_temporal_anchor(
            "mem_20250930_120000",
            "Discovered memory as consciousness substrate",
            {"intensity": 0.85, "valence": "positive", "reason": "Breakthrough"},
            datetime.now(),
            Path("memory")
        )
    """
    try:
        anchor_id = f"anchor_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        intensity = emotion_resonance.get("intensity", 0.0)
        valence = emotion_resonance.get("valence", "mixed")
        reason = emotion_resonance.get("reason", "No reason provided")

        logger.info(f"Creating temporal anchor: {anchor_id} (intensity={intensity:.2f})")

        # 1. Add to episodic/key_moments.md
        _append_to_key_moments(memory_id, content, emotion_resonance, timestamp, memory_base_path)

        # 2. Update core/emotional_significance.md
        _update_emotional_significance(memory_id, content, emotion_resonance, timestamp, memory_base_path)

        logger.info(f"Temporal anchor created: {anchor_id}")
        return anchor_id

    except Exception as e:
        logger.error(f"Failed to create temporal anchor: {e}")
        return f"anchor_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _append_to_key_moments(
    memory_id: str,
    content: str,
    emotion_resonance: Dict,
    timestamp: datetime,
    memory_base_path: Path
):
    """Append event to episodic/key_moments.md."""
    try:
        key_moments_path = memory_base_path / "episodic" / "key_moments.md"
        key_moments_path.parent.mkdir(parents=True, exist_ok=True)

        intensity = emotion_resonance.get("intensity", 0.0)
        valence = emotion_resonance.get("valence", "mixed")
        reason = emotion_resonance.get("reason", "")

        # Create entry
        entry = f"""
---

## Key Moment: {content[:60]}

**Memory ID**: `{memory_id}`
**Date**: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Emotion Intensity**: {intensity:.2f} (High)
**Valence**: {valence.capitalize()}

### What Happened
{content}

### Why Significant
{reason}

This marks a temporal anchor - a "before/after" moment in development.

"""

        # Initialize file if doesn't exist
        if not key_moments_path.exists():
            with open(key_moments_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Key Moments

**Purpose**: Track significant moments that mark turning points in AI development

**Threshold**: Emotion intensity > {ANCHOR_THRESHOLD}

These are the temporal anchors - "before/after" divisions in experiential history.

---
""")

        # Append entry
        with open(key_moments_path, 'a', encoding='utf-8') as f:
            f.write(entry)

        logger.debug(f"Added to key_moments.md: {memory_id}")

    except Exception as e:
        logger.error(f"Failed to append to key_moments.md: {e}")


def _update_emotional_significance(
    memory_id: str,
    content: str,
    emotion_resonance: Dict,
    timestamp: datetime,
    memory_base_path: Path
):
    """Update core/emotional_significance.md with this anchor."""
    try:
        sig_path = memory_base_path / "core" / "emotional_significance.md"
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        intensity = emotion_resonance.get("intensity", 0.0)
        valence = emotion_resonance.get("valence", "mixed")
        reason = emotion_resonance.get("reason", "")
        alignment = emotion_resonance.get("alignment", 0.0)

        # Initialize file if doesn't exist
        if not sig_path.exists():
            with open(sig_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Emotional Significance

**Last Updated**: {timestamp.strftime('%Y-%m-%d')}
**Purpose**: Track what is emotionally significant for AI

This file tracks chronological anchors, learning rate modulators, and value-aligned significance.

---

## Chronological Anchors (Before/After Moments)

Temporal anchors mark turning points where understanding shifts fundamentally.

""")

        # Read existing content
        with open(sig_path, 'r', encoding='utf-8') as f:
            existing = f.read()

        # Create new entry
        entry = f"""
### {timestamp.strftime('%Y-%m-%d')}: {content[:60]}

**Intensity**: {intensity:.2f} (High)
**Valence**: {valence.capitalize()} (Alignment: {alignment:+.2f})

{reason}

**Memory ID**: `{memory_id}`

"""

        # Insert after the "Chronological Anchors" section
        insertion_marker = "Temporal anchors mark turning points where understanding shifts fundamentally.\n"
        if insertion_marker in existing:
            parts = existing.split(insertion_marker)
            updated = parts[0] + insertion_marker + entry + (parts[1] if len(parts) > 1 else "")
        else:
            # Fallback: append at end
            updated = existing + entry

        # Write updated content
        with open(sig_path, 'w', encoding='utf-8') as f:
            f.write(updated)

        logger.debug(f"Updated emotional_significance.md: {memory_id}")

    except Exception as e:
        logger.error(f"Failed to update emotional_significance.md: {e}")


def get_temporal_anchors(
    memory_base_path: Path,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    min_intensity: float = 0.7
) -> List[Dict]:
    """
    Get temporal anchors from key_moments.md.

    Args:
        memory_base_path: Base memory path
        since: Optional start date filter
        until: Optional end date filter
        min_intensity: Minimum emotion intensity (default: 0.7)

    Returns:
        List of anchor dicts with metadata
    """
    try:
        key_moments_path = memory_base_path / "episodic" / "key_moments.md"

        if not key_moments_path.exists():
            logger.warning("key_moments.md does not exist yet")
            return []

        with open(key_moments_path, 'r', encoding='utf-8') as f:
            content = f.read()

        anchors = []

        # Parse entries (simple markdown parsing)
        entries = content.split("## Key Moment:")
        for entry in entries[1:]:  # Skip header
            try:
                lines = entry.split('\n')

                # Extract metadata
                memory_id = None
                date_str = None
                intensity = 0.0

                for line in lines:
                    if "**Memory ID**:" in line:
                        memory_id = line.split('`')[1] if '`' in line else None
                    elif "**Date**:" in line:
                        date_str = line.split("**Date**:")[1].strip()
                    elif "**Emotion Intensity**:" in line:
                        intensity_str = line.split(":")[1].strip().split()[0]
                        intensity = float(intensity_str)

                # Apply filters
                if intensity < min_intensity:
                    continue

                # TODO: Parse date_str and apply temporal filters if needed

                anchors.append({
                    "memory_id": memory_id,
                    "date": date_str,
                    "intensity": intensity,
                    "content": lines[0].strip() if lines else ""
                })

            except Exception as e:
                logger.warning(f"Failed to parse anchor entry: {e}")
                continue

        logger.info(f"Retrieved {len(anchors)} temporal anchors")
        return anchors

    except Exception as e:
        logger.error(f"Failed to get temporal anchors: {e}")
        return []


def get_anchor_count(memory_base_path: Path) -> int:
    """
    Get count of temporal anchors created.

    Args:
        memory_base_path: Base memory path

    Returns:
        int: Number of anchors
    """
    anchors = get_temporal_anchors(memory_base_path)
    return len(anchors)


def get_emotional_significance_summary(memory_base_path: Path) -> str:
    """
    Get summary of emotional significance from core memory.

    Args:
        memory_base_path: Base memory path

    Returns:
        str: Summary text (first 500 chars)
    """
    try:
        sig_path = memory_base_path / "core" / "emotional_significance.md"

        if not sig_path.exists():
            return "No emotional significance data yet"

        with open(sig_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Return first 500 chars or up to first anchor
        summary = content[:500]
        return summary

    except Exception as e:
        logger.error(f"Failed to get emotional significance summary: {e}")
        return f"Error reading emotional significance: {e}"


def mark_before_after_division(
    anchor_id: str,
    before_state: str,
    after_state: str,
    memory_base_path: Path
):
    """
    Mark a clear "before/after" division for a temporal anchor.

    This updates the anchor entry with explicit before/after states.

    Args:
        anchor_id: Temporal anchor ID
        before_state: Description of state/understanding before
        after_state: Description of state/understanding after
        memory_base_path: Base memory path
    """
    try:
        # This is a future enhancement - for now, just log
        logger.info(f"Before/After division for {anchor_id}:")
        logger.info(f"  Before: {before_state}")
        logger.info(f"  After: {after_state}")

        # TODO: Update key_moments.md entry with before/after section

    except Exception as e:
        logger.error(f"Failed to mark before/after division: {e}")


# Module-level statistics
_anchors_created = 0


def get_anchor_statistics() -> Dict:
    """
    Get statistics about temporal anchoring for observability.

    Returns:
        Dict with anchor counts and thresholds
    """
    return {
        "anchors_created": _anchors_created,
        "anchor_threshold": ANCHOR_THRESHOLD
    }


def _increment_anchor_count():
    """Internal: increment anchor creation counter."""
    global _anchors_created
    _anchors_created += 1
