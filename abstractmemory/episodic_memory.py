"""
Episodic Memory Manager for AbstractMemory.

Manages experiential history: key moments, experiments, discoveries, and timeline.
This is the "what happened" layer of memory.

Philosophy: Episodic memory captures the AI's experiential journey -
significant moments, experiments tried, and breakthroughs achieved.

Components:
- key_moments.md: Significant turning points (high emotional resonance)
- key_experiments.md: Experiments conducted (hypothesis → test → result)
- key_discoveries.md: Breakthrough "aha!" moments
- history.json: Temporal graph showing chain of causality
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EpisodicMemoryManager:
    """
    Manages episodic memory - the experiential history.

    Episodic memory tracks:
    - Key moments (temporal anchors with high emotional significance)
    - Experiments (hypothesis-test-result cycles)
    - Discoveries (breakthrough realizations)
    - History (causal chain of events)
    """

    def __init__(self, base_path: Path):
        """
        Initialize EpisodicMemoryManager.

        Args:
            base_path: Root memory directory
        """
        self.base_path = Path(base_path)
        self.episodic_path = self.base_path / "episodic"
        self.episodic_path.mkdir(parents=True, exist_ok=True)

        # Ensure all files exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Ensure all episodic memory files exist."""
        from .memory_structure import _initialize_episodic_memory
        _initialize_episodic_memory(self.base_path)

    def add_key_moment(self,
                       event: str,
                       intensity: float,
                       context: Optional[str] = None,
                       user_id: Optional[str] = None) -> bool:
        """
        Add a key moment (temporal anchor).

        Args:
            event: Description of the significant event
            intensity: Emotional intensity (0.0-1.0)
            context: Optional context about why this is significant
            user_id: Optional user ID if relevant

        Returns:
            bool: True if successful
        """
        try:
            moments_file = self.episodic_path / "key_moments.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if moments_file.exists():
                existing = moments_file.read_text()
            else:
                existing = f"""# Key Moments

**Last Updated**: {timestamp}

**Significant moments that mark turning points.**

*High emotional resonance events.*

---

## Temporal Anchors

"""

            # Add new moment
            moment_entry = f"\n### {timestamp}\n"
            moment_entry += f"\n**Event**: {event}\n"
            moment_entry += f"\n**Intensity**: {intensity:.2f}\n"
            if user_id:
                moment_entry += f"\n**User**: {user_id}\n"
            if context:
                moment_entry += f"\n**Context**: {context}\n"
            moment_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append moment
            updated = existing + moment_entry
            moments_file.write_text(updated)

            logger.info(f"Added key moment: {event[:50]}... (intensity={intensity:.2f})")
            return True

        except Exception as e:
            logger.error(f"Error adding key moment: {e}")
            return False

    def add_experiment(self,
                       hypothesis: str,
                       test: str,
                       result: str,
                       success: bool,
                       learnings: Optional[str] = None) -> bool:
        """
        Add an experiment with hypothesis, test, and result.

        Args:
            hypothesis: What was hypothesized
            test: How it was tested
            result: What the result was
            success: Whether the hypothesis was confirmed
            learnings: Optional key learnings

        Returns:
            bool: True if successful
        """
        try:
            experiments_file = self.episodic_path / "key_experiments.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if experiments_file.exists():
                existing = experiments_file.read_text()
            else:
                existing = f"""# Key Experiments

**Last Updated**: {timestamp}

**Experiments conducted and their results.**

*Hypothesis → Test → Result*

---

## Experiments

"""

            # Add new experiment
            status = "✅ CONFIRMED" if success else "❌ REFUTED"
            experiment_entry = f"\n### {timestamp}\n"
            experiment_entry += f"\n**Status**: {status}\n"
            experiment_entry += f"\n**Hypothesis**: {hypothesis}\n"
            experiment_entry += f"\n**Test**: {test}\n"
            experiment_entry += f"\n**Result**: {result}\n"
            if learnings:
                experiment_entry += f"\n**Learnings**: {learnings}\n"
            experiment_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append experiment
            updated = existing + experiment_entry
            experiments_file.write_text(updated)

            logger.info(f"Added experiment: {hypothesis[:50]}... ({status})")
            return True

        except Exception as e:
            logger.error(f"Error adding experiment: {e}")
            return False

    def add_discovery(self,
                      discovery: str,
                      impact: str,
                      context: Optional[str] = None) -> bool:
        """
        Add a breakthrough discovery.

        Args:
            discovery: Description of the discovery
            impact: How this changed understanding
            context: Optional context about the discovery

        Returns:
            bool: True if successful
        """
        try:
            discoveries_file = self.episodic_path / "key_discoveries.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing content
            if discoveries_file.exists():
                existing = discoveries_file.read_text()
            else:
                existing = f"""# Key Discoveries

**Last Updated**: {timestamp}

**Breakthrough moments and "aha!" realizations.**

---

## Discoveries

"""

            # Add new discovery
            discovery_entry = f"\n### {timestamp}\n"
            discovery_entry += f"\n**Discovery**: {discovery}\n"
            discovery_entry += f"\n**Impact**: {impact}\n"
            if context:
                discovery_entry += f"\n**Context**: {context}\n"
            discovery_entry += "\n---\n"

            # Update last updated timestamp
            existing = existing.split("\n")
            existing[2] = f"**Last Updated**: {timestamp}"
            existing = "\n".join(existing)

            # Append discovery
            updated = existing + discovery_entry
            discoveries_file.write_text(updated)

            logger.info(f"Added discovery: {discovery[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error adding discovery: {e}")
            return False

    def add_history_event(self,
                         event_id: str,
                         event: str,
                         caused_by: Optional[List[str]] = None,
                         leads_to: Optional[List[str]] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an event to the temporal history graph.

        Args:
            event_id: Unique identifier for the event
            event: Description of the event
            caused_by: Optional list of event IDs that caused this
            leads_to: Optional list of event IDs this leads to
            metadata: Optional additional metadata

        Returns:
            bool: True if successful
        """
        try:
            history_file = self.episodic_path / "history.json"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Read existing history
            if history_file.exists():
                history = json.loads(history_file.read_text())
            else:
                history = {
                    "timeline": [],
                    "last_updated": timestamp,
                    "description": "Temporal graph of events and chain of causality"
                }

            # Create event entry
            event_entry = {
                "event_id": event_id,
                "timestamp": timestamp,
                "event": event,
                "caused_by": caused_by or [],
                "leads_to": leads_to or [],
                "metadata": metadata or {}
            }

            # Add to timeline
            history["timeline"].append(event_entry)
            history["last_updated"] = timestamp

            # Write back
            history_file.write_text(json.dumps(history, indent=2))

            logger.info(f"Added history event: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding history event: {e}")
            return False

    def get_key_moments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent key moments.

        Args:
            limit: Maximum number of moments to return

        Returns:
            List[Dict]: List of key moments
        """
        try:
            moments_file = self.episodic_path / "key_moments.md"
            if not moments_file.exists():
                return []

            content = moments_file.read_text()
            moments = []

            # Parse markdown format
            current_moment = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_moment:
                        moments.append(current_moment)
                    current_moment = {"timestamp": line[4:].strip()}
                elif line.startswith("**Event**:"):
                    if current_moment:
                        current_moment["event"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Intensity**:"):
                    if current_moment:
                        try:
                            current_moment["intensity"] = float(line.split(":", 1)[1].strip())
                        except ValueError:
                            current_moment["intensity"] = 0.0
                elif line.startswith("**User**:"):
                    if current_moment:
                        current_moment["user_id"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Context**:"):
                    if current_moment:
                        current_moment["context"] = line.split(":", 1)[1].strip()

            if current_moment:
                moments.append(current_moment)

            # Return most recent first
            return moments[-limit:][::-1]

        except Exception as e:
            logger.error(f"Error reading key moments: {e}")
            return []

    def get_experiments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent experiments.

        Args:
            limit: Maximum number of experiments to return

        Returns:
            List[Dict]: List of experiments
        """
        try:
            experiments_file = self.episodic_path / "key_experiments.md"
            if not experiments_file.exists():
                return []

            content = experiments_file.read_text()
            experiments = []

            # Parse markdown format
            current_exp = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_exp:
                        experiments.append(current_exp)
                    current_exp = {"timestamp": line[4:].strip()}
                elif line.startswith("**Status**:"):
                    if current_exp:
                        current_exp["success"] = "CONFIRMED" in line
                elif line.startswith("**Hypothesis**:"):
                    if current_exp:
                        current_exp["hypothesis"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Test**:"):
                    if current_exp:
                        current_exp["test"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Result**:"):
                    if current_exp:
                        current_exp["result"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Learnings**:"):
                    if current_exp:
                        current_exp["learnings"] = line.split(":", 1)[1].strip()

            if current_exp:
                experiments.append(current_exp)

            # Return most recent first
            return experiments[-limit:][::-1]

        except Exception as e:
            logger.error(f"Error reading experiments: {e}")
            return []

    def get_discoveries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent discoveries.

        Args:
            limit: Maximum number of discoveries to return

        Returns:
            List[Dict]: List of discoveries
        """
        try:
            discoveries_file = self.episodic_path / "key_discoveries.md"
            if not discoveries_file.exists():
                return []

            content = discoveries_file.read_text()
            discoveries = []

            # Parse markdown format
            current_disc = None
            for line in content.split("\n"):
                if line.startswith("### "):
                    if current_disc:
                        discoveries.append(current_disc)
                    current_disc = {"timestamp": line[4:].strip()}
                elif line.startswith("**Discovery**:"):
                    if current_disc:
                        current_disc["discovery"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Impact**:"):
                    if current_disc:
                        current_disc["impact"] = line.split(":", 1)[1].strip()
                elif line.startswith("**Context**:"):
                    if current_disc:
                        current_disc["context"] = line.split(":", 1)[1].strip()

            if current_disc:
                discoveries.append(current_disc)

            # Return most recent first
            return discoveries[-limit:][::-1]

        except Exception as e:
            logger.error(f"Error reading discoveries: {e}")
            return []

    def get_history_timeline(self) -> Dict[str, Any]:
        """
        Get the complete history timeline.

        Returns:
            Dict: History with timeline and metadata
        """
        try:
            history_file = self.episodic_path / "history.json"
            if not history_file.exists():
                return {
                    "timeline": [],
                    "last_updated": None,
                    "description": "Temporal graph of events and chain of causality"
                }

            return json.loads(history_file.read_text())

        except Exception as e:
            logger.error(f"Error reading history timeline: {e}")
            return {"timeline": [], "last_updated": None, "description": "Error loading history"}

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of episodic memory state.

        Returns:
            Dict: Summary with counts and recent events
        """
        moments = self.get_key_moments(limit=3)
        experiments = self.get_experiments(limit=3)
        discoveries = self.get_discoveries(limit=3)
        history = self.get_history_timeline()

        return {
            "key_moments_count": len(self.get_key_moments(limit=1000)),
            "experiments_count": len(self.get_experiments(limit=1000)),
            "discoveries_count": len(self.get_discoveries(limit=1000)),
            "timeline_events_count": len(history.get("timeline", [])),
            "most_recent_moment": moments[0] if moments else None,
            "most_recent_experiment": experiments[0] if experiments else None,
            "most_recent_discovery": discoveries[0] if discoveries else None
        }
