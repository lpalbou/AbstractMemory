"""
User Profile Extraction - Emergence Through Observation

Philosophy:
- Profiles EMERGE from interactions (not asked, observed)
- Patterns extracted via LLM analysis
- Updated incrementally (threshold-based)
- Integration with reconstruct_context() step 7

Design from docs/IMPLEMENTATION_ROADMAP.md:189-218
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class UserProfileManager:
    """
    Manages user profile emergence from verbatim interactions.

    Key principles:
    1. Profiles emerge naturally (NOT manually created)
    2. Observed patterns (NOT asked questions)
    3. Incremental updates (threshold-based: every N interactions)
    4. LLM-driven analysis (NO keyword matching)

    Structure:
        people/{user}/
        ├── profile.md         # Who they are
        ├── preferences.md     # What they prefer
        └── conversations/     # Symlink to verbatim/{user}/
    """

    def __init__(self, memory_base_path: Path, llm_provider=None):
        """
        Initialize UserProfileManager.

        Args:
            memory_base_path: Base path for memory storage
            llm_provider: LLM provider for profile extraction (AbstractCore)
        """
        self.memory_base_path = Path(memory_base_path)
        self.people_path = self.memory_base_path / "people"
        self.verbatim_path = self.memory_base_path / "verbatim"
        self.llm = llm_provider

        # Ensure people directory exists
        self.people_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"UserProfileManager initialized at {self.people_path}")

    def _ensure_user_structure(self, user_id: str) -> Path:
        """
        Ensure user directory structure exists.

        Args:
            user_id: User identifier

        Returns:
            Path to user directory
        """
        user_path = self.people_path / user_id
        user_path.mkdir(parents=True, exist_ok=True)

        # Create symlink to conversations if not exists
        conversations_link = user_path / "conversations"
        if not conversations_link.exists():
            target = self.verbatim_path / user_id
            if target.exists():
                try:
                    conversations_link.symlink_to(target, target_is_directory=True)
                    logger.debug(f"Created symlink: {conversations_link} -> {target}")
                except Exception as e:
                    logger.warning(f"Could not create symlink: {e}")

        return user_path

    def get_user_interactions(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Load verbatim interactions for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of interactions to load (None = all)

        Returns:
            List of interaction dictionaries with metadata
        """
        user_verbatim = self.verbatim_path / user_id
        if not user_verbatim.exists():
            logger.warning(f"No verbatim interactions found for {user_id}")
            return []

        interactions = []

        # Find all .md files recursively
        for md_file in sorted(user_verbatim.rglob("*.md"), reverse=True):
            if limit and len(interactions) >= limit:
                break

            try:
                content = md_file.read_text()

                # Parse metadata from frontmatter
                interaction = {
                    "file_path": str(md_file),
                    "content": content,
                    "timestamp": self._extract_timestamp(md_file, content),
                    "user_id": user_id
                }

                # Extract query and response from content
                query, response = self._parse_interaction_content(content)
                interaction["user_query"] = query
                interaction["agent_response"] = response

                interactions.append(interaction)

            except Exception as e:
                logger.warning(f"Error parsing {md_file}: {e}")
                continue

        logger.info(f"Loaded {len(interactions)} interactions for {user_id}")
        return interactions

    def _extract_timestamp(self, file_path: Path, content: str) -> datetime:
        """Extract timestamp from file path or content."""
        # Try to parse from file path (YYYY/MM/DD/HH_MM_SS_*.md)
        parts = file_path.parts
        try:
            # Expect: .../YYYY/MM/DD/HH_MM_SS_*.md
            if len(parts) >= 4:
                yyyy, mm, dd = parts[-4], parts[-3], parts[-2]
                filename = parts[-1]
                hh_mm_ss = filename.split("_")[:3]
                if len(hh_mm_ss) == 3:
                    dt_str = f"{yyyy}-{mm}-{dd} {hh_mm_ss[0]}:{hh_mm_ss[1]}:{hh_mm_ss[2]}"
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.debug(f"Could not parse timestamp from path: {e}")

        # Fallback: use file modification time
        return datetime.fromtimestamp(file_path.stat().st_mtime)

    def _parse_interaction_content(self, content: str) -> tuple[str, str]:
        """
        Parse user query and agent response from verbatim content.

        Expected format:
        ## User Query

        <query text>

        ## Agent Response

        <response text>
        """
        query = ""
        response = ""

        lines = content.split("\n")
        current_section = None

        for line in lines:
            if line.strip() == "## User Query":
                current_section = "query"
                continue
            elif line.strip() == "## Agent Response":
                current_section = "response"
                continue
            elif line.strip().startswith("##"):
                current_section = None
                continue

            if current_section == "query":
                query += line + "\n"
            elif current_section == "response":
                response += line + "\n"

        return query.strip(), response.strip()

    def extract_user_profile(self, user_id: str, interactions: List[Dict[str, Any]]) -> str:
        """
        Extract user profile from interactions using LLM analysis.

        Analyzes:
        - Background/expertise (from query complexity, domain knowledge)
        - Thinking style (analytical, exploratory, practical, creative)
        - Communication preferences (technical, casual, formal)
        - Interests (topics asked about, recurring themes)

        Args:
            user_id: User identifier
            interactions: List of interaction dictionaries

        Returns:
            Profile content (markdown)
        """
        if not self.llm:
            logger.warning("No LLM provider - cannot extract profile")
            return self._create_template_profile(user_id)

        if not interactions:
            logger.warning(f"No interactions for {user_id} - creating template")
            return self._create_template_profile(user_id)

        # Prepare interaction summary for LLM
        interaction_summary = self._summarize_interactions(interactions)

        # LLM extraction prompt
        prompt = f"""You are analyzing user interactions to extract an emergent user profile.

**CRITICAL**: Base your analysis ONLY on observed patterns in the interactions below.
Do NOT make assumptions. If you cannot determine something, say "Not yet observed."

Analyze these {len(interactions)} interactions for user '{user_id}':

{interaction_summary}

Extract a user profile covering:

1. **Background & Expertise**:
   - What domains/topics do they ask about? (e.g., technical, creative, business)
   - What level of expertise do their questions suggest? (beginner, intermediate, expert)
   - What skills or knowledge areas are evident?

2. **Thinking Style**:
   - How do they approach problems? (analytical, exploratory, practical, creative)
   - Do they prefer depth or breadth?
   - Are they systematic or intuitive?

3. **Communication Style**:
   - How do they phrase questions? (technical, casual, formal)
   - Do they prefer concise or detailed responses?
   - What's their typical interaction pattern?

4. **Interests & Focus**:
   - What topics do they return to repeatedly?
   - What themes emerge across interactions?
   - What are they trying to accomplish?

Format your response as a markdown profile with these sections.
Be specific, cite examples from interactions, and avoid generic statements.
If evidence is insufficient for a section, state "Not yet observed - need more interactions."

Generate the profile now:"""

        try:
            # Generate profile using LLM
            logger.info(f"Extracting profile for {user_id} from {len(interactions)} interactions")
            response_obj = self.llm.generate(prompt)

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(response_obj, 'content'):
                profile_content = response_obj.content
            elif hasattr(response_obj, 'text'):
                profile_content = response_obj.text
            else:
                profile_content = str(response_obj)

            # Validate extraction quality
            if len(profile_content.strip()) < 100:
                logger.warning(f"Profile extraction too short ({len(profile_content)} chars) - using template")
                return self._create_template_profile(user_id)

            # Add metadata header
            header = f"""# User Profile: {user_id}

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Interactions Analyzed**: {len(interactions)}
**Confidence**: Emergent (based on observed patterns)

---

"""
            return header + profile_content

        except Exception as e:
            logger.error(f"Error extracting profile: {e}")
            return self._create_template_profile(user_id)

    def extract_user_preferences(self, user_id: str, interactions: List[Dict[str, Any]]) -> str:
        """
        Extract user preferences from interactions using LLM analysis.

        Analyzes:
        - Organization preferences (structured vs. freeform)
        - Language style (concise vs. detailed, technical vs. accessible)
        - Depth vs. breadth preferences
        - Decision-making patterns
        - Response format preferences

        Args:
            user_id: User identifier
            interactions: List of interaction dictionaries

        Returns:
            Preferences content (markdown)
        """
        if not self.llm:
            logger.warning("No LLM provider - cannot extract preferences")
            return self._create_template_preferences(user_id)

        if not interactions:
            logger.warning(f"No interactions for {user_id} - creating template")
            return self._create_template_preferences(user_id)

        # Prepare interaction summary
        interaction_summary = self._summarize_interactions(interactions)

        # LLM extraction prompt
        prompt = f"""You are analyzing user interactions to extract emergent preferences.

**CRITICAL**: Base your analysis ONLY on observed patterns.
Look for what they ACTUALLY prefer based on how they interact, NOT assumptions.

Analyze these {len(interactions)} interactions for user '{user_id}':

{interaction_summary}

Extract user preferences covering:

1. **Communication Preferences**:
   - Do they prefer concise or detailed responses?
   - Technical language or accessible explanations?
   - Formal or casual tone?

2. **Organization Preferences**:
   - Structured (numbered lists, clear sections) or freeform?
   - Linear progression or exploratory discussion?
   - Examples first or concepts first?

3. **Content Preferences**:
   - Depth (deep dive on fewer topics) or breadth (overview of many)?
   - Practical (actionable steps) or theoretical (concepts, principles)?
   - Code examples vs. explanations?

4. **Interaction Patterns**:
   - Short queries or detailed questions?
   - Follow-up questions or one-off queries?
   - Exploratory (open-ended) or goal-oriented?

5. **Decision-Making Style**:
   - Quick decisions (choose first good option) or careful analysis (compare multiple)?
   - Risk-tolerant or risk-averse?
   - Prefer guidance or autonomy?

Format as markdown with sections above.
Cite specific examples from interactions.
If evidence is insufficient, state "Not yet observed."

Generate preferences now:"""

        try:
            logger.info(f"Extracting preferences for {user_id} from {len(interactions)} interactions")
            response_obj = self.llm.generate(prompt)

            # Extract text from response object (AbstractCore compatibility)
            if hasattr(response_obj, 'content'):
                preferences_content = response_obj.content
            elif hasattr(response_obj, 'text'):
                preferences_content = response_obj.text
            else:
                preferences_content = str(response_obj)

            # Validate extraction quality
            if len(preferences_content.strip()) < 100:
                logger.warning(f"Preferences extraction too short - using template")
                return self._create_template_preferences(user_id)

            # Add metadata header
            header = f"""# Preferences: {user_id}

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Interactions Analyzed**: {len(interactions)}
**Confidence**: Emergent (observed patterns)

---

"""
            return header + preferences_content

        except Exception as e:
            logger.error(f"Error extracting preferences: {e}")
            return self._create_template_preferences(user_id)

    def _summarize_interactions(self, interactions: List[Dict[str, Any]], max_length: int = 3000) -> str:
        """
        Create a concise summary of interactions for LLM analysis.

        Args:
            interactions: List of interactions
            max_length: Maximum character length for summary

        Returns:
            Formatted interaction summary
        """
        summary_lines = []
        char_count = 0

        for i, interaction in enumerate(interactions[:50], 1):  # Limit to 50 most recent
            timestamp = interaction.get("timestamp", "Unknown")
            query = interaction.get("user_query", "")[:200]  # Truncate long queries
            response = interaction.get("agent_response", "")[:300]  # Truncate long responses

            interaction_text = f"""
Interaction {i} ({timestamp}):
USER: {query}
AGENT: {response}
---
"""
            if char_count + len(interaction_text) > max_length:
                summary_lines.append(f"\n[... {len(interactions) - i + 1} more interactions not shown ...]")
                break

            summary_lines.append(interaction_text)
            char_count += len(interaction_text)

        return "\n".join(summary_lines)

    def _create_template_profile(self, user_id: str) -> str:
        """Create template profile when extraction not possible."""
        return f"""# User Profile: {user_id}

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Status**: Template (insufficient interactions for extraction)

---

## Background & Expertise

*Not yet observed - need more interactions*

---

## Thinking Style

*Not yet observed - need more interactions*

---

## Communication Style

*Not yet observed - need more interactions*

---

## Interests & Focus

*Not yet observed - need more interactions*

---

**Note**: This is a template. Profile will emerge after more interactions.
"""

    def _create_template_preferences(self, user_id: str) -> str:
        """Create template preferences when extraction not possible."""
        return f"""# Preferences: {user_id}

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Status**: Template (insufficient interactions for extraction)

---

## Communication Preferences

*Not yet observed*

---

## Organization Preferences

*Not yet observed*

---

## Content Preferences

*Not yet observed*

---

## Interaction Patterns

*Not yet observed*

---

**Note**: This is a template. Preferences will emerge after more interactions.
"""

    def update_user_profile(self, user_id: str, min_interactions: int = 5) -> Dict[str, Any]:
        """
        Update user profile and preferences from interactions.

        This is the main entry point for profile generation/update.

        Args:
            user_id: User identifier
            min_interactions: Minimum interactions required for extraction

        Returns:
            Dictionary with update results
        """
        logger.info(f"Updating profile for {user_id} (min_interactions={min_interactions})")

        # Ensure user structure exists
        user_path = self._ensure_user_structure(user_id)

        # Load interactions
        interactions = self.get_user_interactions(user_id)

        if len(interactions) < min_interactions:
            logger.warning(
                f"Insufficient interactions for {user_id}: "
                f"{len(interactions)} < {min_interactions} (minimum)"
            )
            # Create templates if files don't exist
            profile_path = user_path / "profile.md"
            preferences_path = user_path / "preferences.md"

            if not profile_path.exists():
                profile_path.write_text(self._create_template_profile(user_id))
            if not preferences_path.exists():
                preferences_path.write_text(self._create_template_preferences(user_id))

            return {
                "status": "insufficient_data",
                "user_id": user_id,
                "interactions_found": len(interactions),
                "min_required": min_interactions
            }

        # Extract profile
        logger.info(f"Extracting profile from {len(interactions)} interactions")
        profile_content = self.extract_user_profile(user_id, interactions)

        # Extract preferences
        logger.info(f"Extracting preferences from {len(interactions)} interactions")
        preferences_content = self.extract_user_preferences(user_id, interactions)

        # Write to files
        profile_path = user_path / "profile.md"
        preferences_path = user_path / "preferences.md"

        profile_path.write_text(profile_content)
        preferences_path.write_text(preferences_content)

        logger.info(f"✅ Updated profile for {user_id}: {profile_path}, {preferences_path}")

        return {
            "status": "success",
            "user_id": user_id,
            "interactions_analyzed": len(interactions),
            "profile_path": str(profile_path),
            "preferences_path": str(preferences_path),
            "updated_at": datetime.now().isoformat()
        }

    def get_user_profile(self, user_id: str) -> Optional[str]:
        """
        Load existing user profile.

        Args:
            user_id: User identifier

        Returns:
            Profile content or None if not found
        """
        profile_path = self.people_path / user_id / "profile.md"
        if profile_path.exists():
            return profile_path.read_text()
        return None

    def get_user_preferences(self, user_id: str) -> Optional[str]:
        """
        Load existing user preferences.

        Args:
            user_id: User identifier

        Returns:
            Preferences content or None if not found
        """
        preferences_path = self.people_path / user_id / "preferences.md"
        if preferences_path.exists():
            return preferences_path.read_text()
        return None
