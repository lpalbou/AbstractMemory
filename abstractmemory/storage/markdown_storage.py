"""
Markdown Storage Backend for human-readable, observable AI memory.
Provides complete transparency into AI memory evolution.
"""

import os
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
import re

from ..core.interfaces import IStorage


class MarkdownStorage(IStorage):
    """
    Human-readable markdown storage with full observability.

    Directory structure:
    memory/
    ├── verbatim/{user}/{yyyy}/{mm}/{dd}/{HH}-{MM}-{SS}_{topic}.md
    ├── experiential/{yyyy}/{mm}/{dd}/{HH}-{MM}-{SS}_reflection.md
    ├── links/{yyyy}/{mm}/{dd}/{interaction_id}_to_{note_id}.json
    ├── core/{yyyy}-{mm}-{dd}_snapshot.md
    ├── semantic/facts_{yyyy}-{mm}.md
    └── index.json
    """

    def __init__(self, base_path: str):
        """Initialize markdown storage at specified path"""
        self.base_path = Path(base_path)
        self.index_file = self.base_path / "index.json"

        # Create directory structure
        self._create_directories()

        # Load or create index
        index_existed = self.index_file.exists()
        self.index = self._load_index()

        # Save initial index if it was created new
        if not index_existed:
            self._save_index()

    def _create_directories(self):
        """Create the directory structure"""
        directories = [
            "verbatim", "experiential", "links",
            "core", "semantic"
        ]

        for directory in directories:
            (self.base_path / directory).mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict:
        """Load the master index"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Create new index
        return {
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "interactions": {},
            "experiential_notes": {},
            "links": {},
            "topics": set(),
            "users": set()
        }

    def _save_index(self):
        """Save the master index"""
        self.index["last_updated"] = datetime.now().isoformat()

        # Convert sets to lists for JSON serialization
        index_copy = self.index.copy()
        index_copy["topics"] = list(self.index["topics"]) if isinstance(self.index["topics"], set) else self.index["topics"]
        index_copy["users"] = list(self.index["users"]) if isinstance(self.index["users"], set) else self.index["users"]

        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index_copy, f, indent=2, ensure_ascii=False)

    def _extract_topic(self, user_input: str, agent_response: str) -> str:
        """Extract main topic from interaction"""
        # Simple topic extraction - could be enhanced with NLP
        text = f"{user_input} {agent_response}".lower()

        # Look for key terms
        topics = []
        if "python" in text:
            topics.append("python")
        if "code" in text or "programming" in text:
            topics.append("coding")
        if "learn" in text or "teach" in text:
            topics.append("learning")
        if "help" in text or "assist" in text:
            topics.append("assistance")
        if "memory" in text or "remember" in text:
            topics.append("memory")

        # Default topic from first few words of user input
        if not topics:
            words = user_input.split()[:3]
            topic = "_".join(word.lower().strip(".,!?") for word in words if word.isalpha())
            topics.append(topic or "general")

        return topics[0]

    def _get_date_path(self, timestamp: datetime) -> str:
        """Get date-based path component"""
        return f"{timestamp.year:04d}/{timestamp.month:02d}/{timestamp.day:02d}"

    def _get_time_prefix(self, timestamp: datetime) -> str:
        """Get time-based filename prefix"""
        return f"{timestamp.hour:02d}-{timestamp.minute:02d}-{timestamp.second:02d}"

    def save_interaction(self, user_id: str, timestamp: datetime,
                        user_input: str, agent_response: str,
                        topic: str, metadata: Optional[Dict] = None) -> str:
        """Save verbatim interaction to markdown"""

        # Generate interaction ID
        interaction_id = f"int_{uuid.uuid4().hex[:8]}"

        # Extract or use provided topic
        if not topic:
            topic = self._extract_topic(user_input, agent_response)

        # Create file path
        date_path = self._get_date_path(timestamp)
        time_prefix = self._get_time_prefix(timestamp)
        filename = f"{time_prefix}_{topic}_{interaction_id}.md"

        file_path = self.base_path / "verbatim" / user_id / date_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create markdown content
        content = self._create_interaction_markdown(
            interaction_id, user_id, timestamp, user_input,
            agent_response, topic, metadata
        )

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Update index
        self.index["interactions"][interaction_id] = {
            "file_path": str(file_path.relative_to(self.base_path)),
            "user_id": user_id,
            "timestamp": timestamp.isoformat(),
            "topic": topic,
            "linked_notes": []
        }

        # Ensure topics and users are sets
        if not isinstance(self.index["topics"], set):
            self.index["topics"] = set(self.index["topics"])
        if not isinstance(self.index["users"], set):
            self.index["users"] = set(self.index["users"])

        self.index["topics"].add(topic)
        self.index["users"].add(user_id)
        self._save_index()

        return interaction_id

    def _create_interaction_markdown(self, interaction_id: str, user_id: str,
                                   timestamp: datetime, user_input: str,
                                   agent_response: str, topic: str,
                                   metadata: Optional[Dict]) -> str:
        """Create markdown content for interaction"""

        content = f"""# Interaction: {topic}

**ID**: `{interaction_id}`
**Date**: {timestamp.isoformat()}
**User**: {user_id}
**Topic**: {topic}

"""

        if metadata:
            content += "## Metadata\n\n"
            for key, value in metadata.items():
                content += f"- **{key}**: {value}\n"
            content += "\n"

        content += f"""## User Input

{user_input}

## Agent Response

{agent_response}

## Links

*Linked experiential notes will appear here*

---
*Generated by AbstractMemory - {timestamp.isoformat()}*
"""

        return content

    def save_experiential_note(self, timestamp: datetime, reflection: str,
                              interaction_id: str, note_type: str = "reflection",
                              metadata: Optional[Dict] = None) -> str:
        """Save AI experiential note to markdown"""

        # Generate note ID
        note_id = f"note_{uuid.uuid4().hex[:8]}"

        # Create file path
        date_path = self._get_date_path(timestamp)
        time_prefix = self._get_time_prefix(timestamp)
        filename = f"{time_prefix}_{note_type}_{note_id}.md"

        file_path = self.base_path / "experiential" / date_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create markdown content
        content = self._create_experiential_markdown(
            note_id, timestamp, reflection, interaction_id, note_type, metadata
        )

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Update index
        self.index["experiential_notes"][note_id] = {
            "file_path": str(file_path.relative_to(self.base_path)),
            "timestamp": timestamp.isoformat(),
            "note_type": note_type,
            "linked_interaction": interaction_id
        }
        self._save_index()

        return note_id

    def _create_experiential_markdown(self, note_id: str, timestamp: datetime,
                                    reflection: str, interaction_id: str,
                                    note_type: str, metadata: Optional[Dict]) -> str:
        """Create markdown content for experiential note"""

        content = f"""# AI {note_type.title()}: {note_id}

**Note ID**: `{note_id}`
**Date**: {timestamp.isoformat()}
**Type**: {note_type}
**Triggered by**: [Interaction {interaction_id}](../../verbatim/.../.../{interaction_id}.md)

"""

        if metadata:
            content += "## Context\n\n"
            for key, value in metadata.items():
                content += f"- **{key}**: {value}\n"
            content += "\n"

        content += f"""## Reflection

{reflection}

## Insights

*This section could contain extracted insights, patterns, or learnings*

---
*AI experiential note generated by AbstractMemory - {timestamp.isoformat()}*
"""

        return content

    def link_interaction_to_note(self, interaction_id: str, note_id: str) -> None:
        """Create bidirectional link between interaction and note"""

        # Create link metadata
        link_data = {
            "interaction_id": interaction_id,
            "note_id": note_id,
            "created": datetime.now().isoformat(),
            "type": "bidirectional"
        }

        # Save link file
        if interaction_id in self.index["interactions"]:
            interaction_data = self.index["interactions"][interaction_id]
            timestamp = datetime.fromisoformat(interaction_data["timestamp"])
            date_path = self._get_date_path(timestamp)

            link_file = self.base_path / "links" / date_path / f"{interaction_id}_to_{note_id}.json"
            link_file.parent.mkdir(parents=True, exist_ok=True)

            with open(link_file, 'w', encoding='utf-8') as f:
                json.dump(link_data, f, indent=2)

        # Update index
        if interaction_id in self.index["interactions"]:
            self.index["interactions"][interaction_id]["linked_notes"].append(note_id)

        self.index["links"][f"{interaction_id}_{note_id}"] = link_data
        self._save_index()

    def search_interactions(self, query: str, user_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Dict]:
        """Search interactions using file system and text matching"""

        results = []
        query_lower = query.lower()

        for interaction_id, interaction_data in self.index["interactions"].items():
            # Filter by user
            if user_id and interaction_data["user_id"] != user_id:
                continue

            # Filter by date range
            interaction_time = datetime.fromisoformat(interaction_data["timestamp"])
            if start_date and interaction_time < start_date:
                continue
            if end_date and interaction_time > end_date:
                continue

            # Check topic match
            if query_lower in interaction_data["topic"].lower():
                results.append({
                    "id": interaction_id,
                    "timestamp": interaction_data["timestamp"],
                    "user_id": interaction_data["user_id"],
                    "topic": interaction_data["topic"],
                    "file_path": interaction_data["file_path"],
                    "match_type": "topic"
                })
                continue

            # Search file content
            file_path = self.base_path / interaction_data["file_path"]
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if query_lower in content:
                            results.append({
                                "id": interaction_id,
                                "timestamp": interaction_data["timestamp"],
                                "user_id": interaction_data["user_id"],
                                "topic": interaction_data["topic"],
                                "file_path": interaction_data["file_path"],
                                "match_type": "content"
                            })
                except IOError:
                    pass

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results

    # IStorage interface implementation
    def save(self, key: str, value: Any) -> None:
        """Generic save for compatibility"""
        # For memory component snapshots
        if "/" in key:
            component_name = key.split("/")[-1]
            self.save_memory_component(component_name, value)

    def load(self, key: str) -> Any:
        """Generic load for compatibility"""
        if "/" in key:
            component_name = key.split("/")[-1]
            return self.load_memory_component(component_name)
        return None

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if "/" in key:
            component_name = key.split("/")[-1]
            component_file = self.base_path / "core" / f"{component_name}_latest.json"
            return component_file.exists()
        return False

    def save_memory_component(self, component_name: str, component_data: Any) -> None:
        """Save memory component as human-readable snapshot"""
        timestamp = datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")

        # Save as JSON for structured data
        json_file = self.base_path / "core" / f"{component_name}_{date_str}.json"
        json_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert component to serializable format
        if hasattr(component_data, '__dict__'):
            data = component_data.__dict__
        else:
            data = component_data

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        # Create symlink to latest
        latest_file = self.base_path / "core" / f"{component_name}_latest.json"
        if latest_file.exists():
            latest_file.unlink()
        latest_file.symlink_to(json_file.name)

    def load_memory_component(self, component_name: str) -> Optional[Any]:
        """Load latest memory component"""
        latest_file = self.base_path / "core" / f"{component_name}_latest.json"

        if latest_file.exists():
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        return {
            "total_interactions": len(self.index["interactions"]),
            "total_notes": len(self.index["experiential_notes"]),
            "total_links": len(self.index["links"]),
            "unique_users": len(self.index["users"]),
            "unique_topics": len(self.index["topics"]),
            "base_path": str(self.base_path),
            "storage_size_mb": self._get_directory_size() / (1024 * 1024)
        }

    def _get_directory_size(self) -> int:
        """Get total size of storage directory in bytes"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.base_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size