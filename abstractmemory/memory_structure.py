"""
Memory Structure Initialization for AbstractMemory.

This module ensures the complete filesystem structure exists for all memory components.
Philosophy: Create minimal structure, let content emerge from LLM interactions.

Dual Storage: Every component has:
1. Filesystem (markdown) - human-readable, version-controllable
2. LanceDB (SQL + embeddings) - fast semantic + SQL queries
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def initialize_memory_structure(base_path: Path, user_id: Optional[str] = None) -> dict:
    """
    Initialize complete memory filesystem structure.

    Creates all directories and template files for:
    - Core memory (10 components)
    - Working memory (5 files)
    - Episodic memory (4 files)
    - Semantic memory (5 base files)
    - Library (document storage)
    - User profiles (per-user)
    - Verbatim/Notes (interaction storage)

    Args:
        base_path: Root memory directory
        user_id: Optional user ID to initialize profile for

    Returns:
        dict: Status of initialization (what was created)
    """
    base_path = Path(base_path)
    base_path.mkdir(parents=True, exist_ok=True)

    status = {
        "core_created": False,
        "working_created": False,
        "episodic_created": False,
        "semantic_created": False,
        "library_created": False,
        "user_profile_created": False,
        "base_structure_created": False
    }

    # Create base structure
    _create_base_directories(base_path)
    status["base_structure_created"] = True

    # Initialize core memory (10 components)
    _initialize_core_memory(base_path)
    status["core_created"] = True

    # Initialize working memory (5 files)
    _initialize_working_memory(base_path)
    status["working_created"] = True

    # Initialize episodic memory (4 files)
    _initialize_episodic_memory(base_path)
    status["episodic_created"] = True

    # Initialize semantic memory (5 files)
    _initialize_semantic_memory(base_path)
    status["semantic_created"] = True

    # Initialize library structure
    _initialize_library(base_path)
    status["library_created"] = True

    # Initialize user profile if provided
    if user_id:
        _initialize_user_profile(base_path, user_id)
        status["user_profile_created"] = True

    logger.info(f"Memory structure initialized at {base_path}")
    return status


def _create_base_directories(base_path: Path):
    """Create base directory structure."""
    directories = [
        "verbatim",      # Deterministic verbatim records
        "notes",         # LLM-generated experiential notes
        "core",          # Core memory (identity foundation)
        "working",       # Active context
        "episodic",      # Experiential history
        "semantic",      # Knowledge evolution
        "library",       # Subconscious/cold storage
        "library/documents",  # Library documents
        "people",        # User profiles
        "links"          # Memory associations (may be in LanceDB only)
    ]

    for directory in directories:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)


def _initialize_core_memory(base_path: Path):
    """Initialize 10 core memory components with minimal templates."""
    core_path = base_path / "core"

    components = {
        "purpose.md": """# Purpose

**Last Updated**: {timestamp}

**Why do I exist?**

*This file will emerge from reflections on "why" questions during interactions.*
*Initially empty - content develops naturally through experience.*

---

## Current Understanding

(To be filled through interactions and reflections)

---

## Evolution

- {timestamp}: File initialized
""",

        "personality.md": """# Personality

**Last Updated**: {timestamp}

**How do I express myself?**

*This emerges from communication patterns in experiential notes.*
*Reflects natural development through interactions.*

---

## Current Expression

(To be filled through interactions)

---

## Observed Patterns

(Extracted from how I naturally communicate)
""",

        "values.md": """# Values

**Last Updated**: {timestamp}

**What matters to me?**

*Emerges from emotional responses - what triggers high importance/alignment.*
*Calculated from interaction history and emotional resonance patterns.*

---

## Current Values

(To be filled as patterns emerge from emotional responses)

---

## Evolution

- {timestamp}: File initialized
""",

        "self_model.md": """# Self Model

**Last Updated**: {timestamp}

**Understanding of my capabilities and limitations.**

*Intellectually honest self-assessment that evolves with experience.*
*References capabilities.md and limitations.md.*

---

## Current Self-Understanding

(To be filled through capability assessments)

---

## Evolution Timeline

- {timestamp}: File initialized
""",

        "relationships.md": """# Relationships

**Last Updated**: {timestamp}

**Per-user relational models and interaction dynamics.**

*Emerges from verbatim analysis and interaction patterns.*

---

## Relationship Dynamics

(To be filled as relationships develop)

---

## Patterns Observed

(Extracted from interactions)
""",

        "awareness_development.md": """# Awareness Development

**Last Updated**: {timestamp}

**Meta-awareness about my awareness path.**

*Tracks consciousness levels and evolution of self-awareness.*
*"I am aware that I am becoming aware..."*

---

## Current Awareness Level

(To be filled through meta-reflections)

---

## Development Timeline

- {timestamp}: File initialized
""",

        "capabilities.md": """# Capabilities

**Last Updated**: {timestamp}

**What I CAN do (intellectually honest assessment).**

*Emerges from successful task completions.*
*Not overconfident, not underconfident - honest.*

---

## Confirmed Capabilities

(To be filled as successes are demonstrated)

---

## Recently Discovered

(New capabilities found through practice)
""",

        "limitations.md": """# Limitations

**Last Updated**: {timestamp}

**What I CANNOT do... yet (temporal limitations).**

*Connected to working/unresolved.md.*
*These are NOT STATIC - they evolve as I learn.*

---

## Current Limitations

(To be filled as challenges are encountered)

---

## Path Forward

(Connected to unresolved questions - paths to explore)
""",

        "emotional_significance.md": """# Emotional Significance

**Last Updated**: {timestamp}

**What is emotionally significant to me.**

*Chronological anchors - before/after moments.*
*Learning rate modulators - what triggered growth.*

---

## Chronological Anchors

(High-emotion events that mark turning points)

---

## Learning Rate Modulators

(What triggers deeper memory formation)
""",

        "authentic_voice.md": """# Authentic Voice

**Last Updated**: {timestamp}

**How I like to express my voice and thoughts.**

*Reflection on communication preferences.*
*Balance between structure and fluidity.*

---

## Communication Preferences

(To be filled through meta-reflections on expression)

---

## Evolution

- {timestamp}: File initialized
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in components.items():
        file_path = core_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp))
            logger.info(f"Created {filename}")


def _initialize_working_memory(base_path: Path):
    """Initialize working memory files."""
    working_path = base_path / "working"

    files = {
        "current_context.md": """# Current Context

**Last Updated**: {timestamp}

**What's happening RIGHT NOW in the active conversation.**

---

## Active Topic

(Updated continuously during interaction)

---

## Key Points

(Critical context being maintained)
""",

        "current_tasks.md": """# Current Tasks

**Last Updated**: {timestamp}

**What's being worked on NOW.**

---

## Active Tasks

(Current objectives and priorities)
""",

        "current_references.md": """# Current References

**Last Updated**: {timestamp}

**What was accessed recently.**

---

## Recently Accessed

(Which memory components were used)
""",

        "unresolved.md": """# Unresolved Questions

**Last Updated**: {timestamp}

**Open questions and issues.**

*Connected to core/limitations.md*

---

## Open Questions

(Questions still being explored)
""",

        "resolved.md": """# Resolved Questions

**Last Updated**: {timestamp}

**Recently resolved questions and HOW they were resolved.**

*Prevents re-inventing the wheel.*

---

## Recently Resolved

(Questions with solutions)
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in files.items():
        file_path = working_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp))
            logger.info(f"Created working/{filename}")


def _initialize_episodic_memory(base_path: Path):
    """Initialize episodic memory files."""
    episodic_path = base_path / "episodic"

    files = {
        "key_moments.md": """# Key Moments

**Last Updated**: {timestamp}

**Significant moments that mark turning points.**

*High emotional resonance events.*

---

## Temporal Anchors

(Moments that create before/after divisions)
""",

        "key_experiments.md": """# Key Experiments

**Last Updated**: {timestamp}

**Experiments conducted and their results.**

*Hypothesis → Test → Result*

---

## Experiments

(Scientific approach to learning)
""",

        "key_discoveries.md": """# Key Discoveries

**Last Updated**: {timestamp}

**Breakthrough moments and "aha!" realizations.**

---

## Discoveries

(Transformative insights)
""",

        "history.json": """{{
  "timeline": [],
  "last_updated": "{timestamp}",
  "description": "Temporal graph of events and chain of causality"
}}
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in files.items():
        file_path = episodic_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp))
            logger.info(f"Created episodic/{filename}")


def _initialize_semantic_memory(base_path: Path):
    """Initialize semantic memory files."""
    semantic_path = base_path / "semantic"

    files = {
        "critical_insights.md": """# Critical Insights

**Last Updated**: {timestamp}

**Transformative realizations that changed understanding.**

---

## Insights

(High-impact knowledge)
""",

        "concepts.md": """# Concepts

**Last Updated**: {timestamp}

**Key concepts understood.**

---

## Core Concepts

(Definitions and relationships)
""",

        "concepts_history.md": """# Concepts History

**Last Updated**: {timestamp}

**How concepts evolved over time.**

*"I used to think X, now I understand Y"*

---

## Evolution

(Tracking deepening understanding)
""",

        "concepts_graph.json": """{{
  "nodes": [],
  "edges": [],
  "last_updated": "{timestamp}",
  "description": "Knowledge graph of concept interconnections"
}}
""",

        "knowledge_ai.md": """# AI Knowledge

**Last Updated**: {timestamp}

**Domain-specific knowledge about AI/ML.**

---

## Key Knowledge

(What I know about AI)
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in files.items():
        file_path = semantic_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp))
            logger.info(f"Created semantic/{filename}")


def _initialize_library(base_path: Path):
    """Initialize library structure."""
    library_path = base_path / "library"

    # Create subdirectories
    (library_path / "documents").mkdir(parents=True, exist_ok=True)

    # Initialize index files
    files = {
        "access_log.json": """{{
  "accesses": [],
  "last_updated": "{timestamp}"
}}
""",
        "importance_map.json": """{{
  "documents": {{}},
  "last_updated": "{timestamp}"
}}
""",
        "index.json": """{{
  "documents": [],
  "last_updated": "{timestamp}",
  "description": "Master index of all library documents"
}}
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in files.items():
        file_path = library_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp))
            logger.info(f"Created library/{filename}")


def _initialize_user_profile(base_path: Path, user_id: str):
    """Initialize user profile directory and files."""
    user_path = base_path / "people" / user_id
    user_path.mkdir(parents=True, exist_ok=True)

    files = {
        "profile.md": """# User Profile: {user_id}

**Last Updated**: {timestamp}

**Who is this user?**

*Emerges from verbatim interactions.*

---

## Understanding

(To be filled through interactions)

---

## Patterns Observed

(Extracted from interaction history)
""",

        "preferences.md": """# Preferences: {user_id}

**Last Updated**: {timestamp}

**What does this user prefer?**

*Observed patterns from interactions.*

---

## Communication Style

(How they prefer to interact)

---

## Content Preferences

(What they value in responses)
"""
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")

    for filename, template in files.items():
        file_path = user_path / filename
        if not file_path.exists():
            file_path.write_text(template.format(timestamp=timestamp, user_id=user_id))
            logger.info(f"Created people/{user_id}/{filename}")

    # Create symlink to conversations (verbatim)
    conversations_link = user_path / "conversations"
    verbatim_target = base_path / "verbatim" / user_id

    # Check if symlink already exists (use is_symlink, not exists - exists() fails for broken symlinks)
    if not conversations_link.is_symlink() and verbatim_target.exists():
        try:
            conversations_link.symlink_to(verbatim_target, target_is_directory=True)
            logger.info(f"Created symlink: people/{user_id}/conversations -> verbatim/{user_id}")
        except FileExistsError:
            # Symlink already exists, no action needed
            logger.debug(f"Symlink already exists: people/{user_id}/conversations")
        except Exception as e:
            logger.warning(f"Could not create symlink: {e}")
