#!/usr/bin/env python3
"""
Migration script to populate history.json from existing key_moments.md.

This fixes the episodic memory issue by backfilling the timeline with existing anchors.
"""

import json
import re
from pathlib import Path
from datetime import datetime


def parse_key_moments(moments_file: Path):
    """Parse key_moments.md and extract all anchors."""

    content = moments_file.read_text()

    # Split by "## Key Moment:" to get individual entries
    entries = content.split("## Key Moment:")

    events = []

    for entry in entries[1:]:  # Skip header
        lines = entry.strip().split('\n')

        # Extract metadata
        memory_id = None
        date = None
        intensity = 0.0
        valence = "mixed"
        event_text = lines[0].strip() if lines else ""

        for line in lines:
            if "**Memory ID**:" in line:
                match = re.search(r'`([^`]+)`', line)
                if match:
                    memory_id = match.group(1)
            elif "**Date**:" in line:
                date_str = line.split("**Date**:")[1].strip()
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    date = datetime.now()
            elif "**Emotion Intensity**:" in line:
                match = re.search(r'(\d+\.\d+)', line)
                if match:
                    intensity = float(match.group(1))
            elif "**Valence**:" in line:
                valence = line.split("**Valence**:")[1].strip().lower()

        # Extract significance (from "Why Significant" section)
        significance = ""
        in_significance = False
        for line in lines:
            if "### Why Significant" in line:
                in_significance = True
                continue
            if in_significance:
                if line.startswith("###") or line.startswith("This marks"):
                    break
                significance += line.strip() + " "

        if memory_id and date:
            events.append({
                "memory_id": memory_id,
                "timestamp": date.isoformat(),
                "date": date.strftime('%Y-%m-%d %H:%M:%S'),
                "event": event_text[:100] + "..." if len(event_text) > 100 else event_text,
                "emotion_intensity": intensity,
                "valence": valence,
                "significance": significance.strip(),
                "type": "temporal_anchor"
            })

    return events


def migrate_history(memory_base: Path):
    """Migrate existing key_moments to history.json."""

    moments_file = memory_base / "episodic" / "key_moments.md"
    history_file = memory_base / "episodic" / "history.json"

    if not moments_file.exists():
        print("❌ key_moments.md not found")
        return False

    print(f"📖 Reading {moments_file}")

    # Parse existing moments
    events = parse_key_moments(moments_file)

    print(f"✅ Found {len(events)} temporal anchors")

    # Load or create history
    if history_file.exists():
        with open(history_file, 'r') as f:
            history = json.load(f)
        print(f"📝 Existing history.json has {len(history.get('timeline', []))} events")
    else:
        history = {
            "timeline": [],
            "last_updated": datetime.now().strftime('%Y-%m-%d'),
            "description": "Temporal graph of events and chain of causality"
        }

    # Add events to timeline (only if not already present)
    existing_ids = {evt["memory_id"] for evt in history.get("timeline", [])}
    new_events = [evt for evt in events if evt["memory_id"] not in existing_ids]

    if new_events:
        history["timeline"].extend(new_events)
        history["timeline"].sort(key=lambda x: x["timestamp"])  # Sort chronologically
        history["last_updated"] = datetime.now().strftime('%Y-%m-%d')

        # Write updated history
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        print(f"✅ Added {len(new_events)} events to history.json")
        print(f"📊 Total timeline events: {len(history['timeline'])}")
    else:
        print("ℹ️  No new events to add (all already in timeline)")

    return True


if __name__ == "__main__":
    memory_base = Path(__file__).parent.parent / "repl_memory"

    print("=== Episodic Memory History Migration ===\n")

    success = migrate_history(memory_base)

    if success:
        print("\n✅ Migration complete!")
    else:
        print("\n❌ Migration failed!")
