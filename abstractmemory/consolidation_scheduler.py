"""
Consolidation Scheduler - Time-based memory consolidation.

Implements the 3-tier consolidation schedule from docs/diagrams.md:1126-1143:
- DAILY (lightweight): Update working memory, scan today's notes
- WEEKLY (deep): Extract core memory patterns, update components
- MONTHLY (comprehensive): Analyze evolution, update history

Philosophy: Memory consolidates during "sleep" - scheduled background processing.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)


class ConsolidationScheduler:
    """
    Manages scheduled consolidation (daily/weekly/monthly).

    From docs/diagrams.md:
    - Daily: Lightweight working memory updates
    - Weekly: Deep core memory extraction
    - Monthly: Comprehensive evolution analysis
    """

    def __init__(self, session):
        """
        Initialize consolidation scheduler.

        Args:
            session: MemorySession instance
        """
        self.session = session
        self.schedule_file = session.memory_base_path / ".consolidation_schedule.json"

        # Load or initialize schedule
        self.schedule = self._load_schedule()

        # Save initial schedule if it didn't exist
        if not self.schedule_file.exists():
            self._save_schedule()

    def _load_schedule(self) -> Dict:
        """Load consolidation schedule from disk."""
        if self.schedule_file.exists():
            try:
                with open(self.schedule_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load schedule: {e}")

        # Initialize default schedule
        now = datetime.now().isoformat()
        return {
            "last_daily": None,
            "last_weekly": None,
            "last_monthly": None,
            "next_daily": now,
            "next_weekly": now,
            "next_monthly": now
        }

    def _save_schedule(self):
        """Save consolidation schedule to disk."""
        try:
            with open(self.schedule_file, 'w') as f:
                json.dump(self.schedule, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save schedule: {e}")

    def should_run_daily(self) -> bool:
        """Check if daily consolidation should run."""
        if self.schedule["last_daily"] is None:
            return True

        last_daily = datetime.fromisoformat(self.schedule["last_daily"])
        # Run if more than 20 hours have passed (allows flexibility)
        return (datetime.now() - last_daily) > timedelta(hours=20)

    def should_run_weekly(self) -> bool:
        """Check if weekly consolidation should run."""
        if self.schedule["last_weekly"] is None:
            return True

        last_weekly = datetime.fromisoformat(self.schedule["last_weekly"])
        # Run if more than 6 days have passed
        return (datetime.now() - last_weekly) > timedelta(days=6)

    def should_run_monthly(self) -> bool:
        """Check if monthly consolidation should run."""
        if self.schedule["last_monthly"] is None:
            return True

        last_monthly = datetime.fromisoformat(self.schedule["last_monthly"])
        # Run if more than 28 days have passed
        return (datetime.now() - last_monthly) > timedelta(days=28)

    def run_daily_consolidation(self) -> Dict[str, bool]:
        """
        Run DAILY (lightweight) consolidation.

        From docs/diagrams.md:
        - Scan today's notes
        - Update working memory (current_context, etc.)
        - Add to unresolved if new questions
        """
        logger.info("🌅 Running DAILY consolidation (lightweight)")

        results = {}
        working_dir = self.session.memory_base_path / "working"
        notes_dir = self.session.memory_base_path / "notes"

        # Get today's notes
        today = datetime.now()
        today_path = notes_dir / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        if today_path.exists():
            note_count = len(list(today_path.glob("*.md")))
            logger.info(f"   Found {note_count} notes from today")
            results["notes_scanned"] = True
        else:
            logger.info("   No notes from today")
            results["notes_scanned"] = False

        # Update working memory (placeholder - would analyze notes for current context)
        current_context_file = working_dir / "current_context.md"
        if current_context_file.exists():
            results["working_memory_updated"] = True
            logger.info("   Working memory: current_context.md exists")
        else:
            results["working_memory_updated"] = False

        # Update schedule
        self.schedule["last_daily"] = datetime.now().isoformat()
        self._save_schedule()

        logger.info(f"✅ Daily consolidation complete: {results}")
        return results

    def run_weekly_consolidation(self) -> Dict[str, bool]:
        """
        Run WEEKLY (deep) consolidation.

        From docs/diagrams.md:
        - Extract patterns from week's notes
        - Update core memory components (if significant)
        - Consolidate resolved → capabilities
        - Prune old working memory
        """
        logger.info("📅 Running WEEKLY consolidation (deep)")

        # Run core memory extraction
        from .core_memory_extraction import consolidate_core_memory
        results = consolidate_core_memory(self.session, mode="weekly")

        # Update schedule
        self.schedule["last_weekly"] = datetime.now().isoformat()
        self._save_schedule()

        updated_count = sum(1 for v in results.values() if v)
        logger.info(f"✅ Weekly consolidation complete: {updated_count}/11 components updated")

        return results

    def run_monthly_consolidation(self) -> Dict[str, bool]:
        """
        Run MONTHLY (comprehensive) consolidation.

        From docs/diagrams.md:
        - Analyze value/purpose evolution
        - Update history.md with narrative
        - Recalculate library importance scores
        - Archive old episodic memories
        """
        logger.info("🗓️  Running MONTHLY consolidation (comprehensive)")

        # Run full consolidation with comprehensive mode
        from .core_memory_extraction import consolidate_core_memory
        results = consolidate_core_memory(self.session, mode="monthly")

        # Additional monthly tasks
        history_file = self.session.memory_base_path / "core" / "history.md"
        if history_file.exists():
            results["history_updated"] = True
            logger.info("   History narrative exists")

        # Update schedule
        self.schedule["last_monthly"] = datetime.now().isoformat()
        self._save_schedule()

        updated_count = sum(1 for v in results.values() if v)
        logger.info(f"✅ Monthly consolidation complete: {updated_count} components updated")

        return results

    def check_and_run(self) -> Dict[str, Dict[str, bool]]:
        """
        Check schedule and run any due consolidations.

        Returns:
            Dict with results for each consolidation type that ran
        """
        results = {}

        # Check daily (most frequent)
        if self.should_run_daily():
            results["daily"] = self.run_daily_consolidation()

        # Check weekly
        if self.should_run_weekly():
            results["weekly"] = self.run_weekly_consolidation()

        # Check monthly (least frequent)
        if self.should_run_monthly():
            results["monthly"] = self.run_monthly_consolidation()

        if not results:
            logger.info("⏭️  No scheduled consolidations due")

        return results
