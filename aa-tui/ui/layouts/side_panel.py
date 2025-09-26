"""Side panel with memory status, tools, and metrics."""

from typing import Optional, Dict, Any, List
from datetime import datetime

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import HSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from ui.widgets.foldable import FoldableSection


class SidePanel:
    """Side panel showing memory status, tools, and metrics."""

    def __init__(self, visible: bool = True, width: int = 30):
        """
        Initialize the side panel.

        Args:
            visible: Whether the panel starts visible
            width: Width of the panel in characters
        """
        self._visible = visible
        self.width = width

        # Data
        self.memory_info: Dict[str, Any] = {}
        self.tools_info: List[str] = []
        self.context_metrics: Dict[str, Any] = {}
        self.agent_status: Dict[str, str] = {}

        # Create foldable sections
        self.memory_section = FoldableSection(
            title="🧠 Memory Status",
            content_factory=self._create_memory_content,
            expanded=True,
            style_prefix="sidepanel"
        )

        self.tools_section = FoldableSection(
            title="🔧 Available Tools",
            content_factory=self._create_tools_content,
            expanded=False,
            style_prefix="sidepanel"
        )

        self.metrics_section = FoldableSection(
            title="📊 Context Metrics",
            content_factory=self._create_metrics_content,
            expanded=False,
            style_prefix="sidepanel"
        )

        self.status_section = FoldableSection(
            title="🤖 Agent Status",
            content_factory=self._create_status_content,
            expanded=True,
            style_prefix="sidepanel"
        )

    @property
    def visible(self) -> bool:
        """Check if panel is visible."""
        return self._visible

    def toggle_visibility(self):
        """Toggle panel visibility."""
        self._visible = not self._visible
        get_app().invalidate()

    def show(self):
        """Show the panel."""
        self._visible = True
        get_app().invalidate()

    def hide(self):
        """Hide the panel."""
        self._visible = False
        get_app().invalidate()

    def is_visible(self) -> bool:
        """Check if panel is visible."""
        return self._visible

    @property
    def visibility_filter(self):
        """Get visibility filter for ConditionalContainer."""
        return Condition(lambda: self._visible)

    def update_memory_info(self, memory_info: Dict[str, Any]):
        """Update memory information."""
        self.memory_info = memory_info
        get_app().invalidate()

    def update_tools_info(self, tools: List[str]):
        """Update tools information."""
        self.tools_info = tools
        get_app().invalidate()

    def update_context_metrics(self, metrics: Dict[str, Any]):
        """Update context metrics."""
        self.context_metrics = metrics
        get_app().invalidate()

    def update_agent_status(self, status: Dict[str, str]):
        """Update agent status."""
        self.agent_status = status
        get_app().invalidate()

    def _create_memory_content(self):
        """Create memory status content."""
        if not self.memory_info:
            content = FormattedText([
                ('class:sidepanel.content', 'No memory info available')
            ])
        else:
            parts = []

            # Working memory
            working_count = self.memory_info.get('working_count', 0)
            parts.extend([
                ('class:memory.working', f'Working: {working_count} items\n')
            ])

            # Semantic memory
            semantic_count = self.memory_info.get('semantic_count', 0)
            pending_count = self.memory_info.get('pending_count', 0)
            parts.extend([
                ('class:memory.semantic', f'Semantic: {semantic_count} facts\n'),
                ('class:memory.semantic', f'Pending: {pending_count} facts\n')
            ])

            # Document memory
            doc_count = self.memory_info.get('document_count', 0)
            parts.extend([
                ('class:memory.document', f'Documents: {doc_count} stored\n')
            ])

            # Episodic memory
            episode_count = self.memory_info.get('episode_count', 0)
            parts.extend([
                ('class:memory.episodic', f'Episodes: {episode_count} events\n')
            ])

            # Memory path
            memory_path = self.memory_info.get('memory_path', 'Unknown')
            parts.extend([
                ('class:sidepanel.content', f'\nPath: {memory_path}')
            ])

            content = FormattedText(parts)

        return Window(
            content=FormattedTextControl(text=content),
            wrap_lines=True,
            style='class:sidepanel.content'
        )

    def _create_tools_content(self):
        """Create tools list content."""
        if not self.tools_info:
            content = FormattedText([
                ('class:sidepanel.content', 'No tools available')
            ])
        else:
            parts = []
            for i, tool in enumerate(self.tools_info, 1):
                parts.extend([
                    ('class:sidepanel.content', f'{i}. '),
                    ('class:tool.success', tool),
                    ('class:sidepanel.content', '\n')
                ])
            content = FormattedText(parts)

        return Window(
            content=FormattedTextControl(text=content),
            wrap_lines=True,
            style='class:sidepanel.content'
        )

    def _create_metrics_content(self):
        """Create context metrics content."""
        if not self.context_metrics:
            content = FormattedText([
                ('class:sidepanel.content', 'No metrics available')
            ])
        else:
            parts = []

            # Token information
            base_tokens = self.context_metrics.get('base_tokens', 0)
            enhanced_tokens = self.context_metrics.get('enhanced_tokens', 0)
            max_tokens = self.context_metrics.get('max_tokens', 0)

            if max_tokens > 0:
                usage_percent = (enhanced_tokens / max_tokens) * 100
                parts.extend([
                    ('class:sidepanel.content', f'Base: {base_tokens:,} tokens\n'),
                    ('class:sidepanel.content', f'Enhanced: {enhanced_tokens:,} tokens\n'),
                    ('class:sidepanel.content', f'Max: {max_tokens:,} tokens\n'),
                    ('class:sidepanel.content', f'Usage: {usage_percent:.1f}%\n\n')
                ])

            # Timing information
            react_time = self.context_metrics.get('react_time', 0)
            if react_time > 0:
                parts.extend([
                    ('class:sidepanel.content', f'Last ReAct: {react_time:.1f}s\n')
                ])

            # Memory injection info
            memory_items = self.context_metrics.get('memory_items_count', 0)
            if memory_items > 0:
                parts.extend([
                    ('class:sidepanel.content', f'Memory items: {memory_items}\n')
                ])

            # Interaction count
            interaction_count = self.context_metrics.get('interaction_count', 0)
            parts.extend([
                ('class:sidepanel.content', f'Interactions: {interaction_count}')
            ])

            content = FormattedText(parts)

        return Window(
            content=FormattedTextControl(text=content),
            wrap_lines=True,
            style='class:sidepanel.content'
        )

    def _create_status_content(self):
        """Create agent status content."""
        if not self.agent_status:
            content = FormattedText([
                ('class:sidepanel.content', 'No status available')
            ])
        else:
            parts = []

            # Model info
            model = self.agent_status.get('model', 'Unknown')
            provider = self.agent_status.get('provider', 'Unknown')
            parts.extend([
                ('class:sidepanel.content', f'Model: {model}\n'),
                ('class:sidepanel.content', f'Provider: {provider}\n\n')
            ])

            # Connection status
            connected = self.agent_status.get('connected', False)
            status_style = 'tool.success' if connected else 'tool.error'
            status_text = 'Connected' if connected else 'Disconnected'
            parts.extend([
                ('class:sidepanel.content', 'Status: '),
                (status_style, status_text),
                ('class:sidepanel.content', '\n')
            ])

            # Memory status
            memory_enabled = self.agent_status.get('memory_enabled', False)
            memory_style = 'tool.success' if memory_enabled else 'tool.error'
            memory_text = 'Enabled' if memory_enabled else 'Disabled'
            parts.extend([
                ('class:sidepanel.content', 'Memory: '),
                (memory_style, memory_text),
                ('class:sidepanel.content', '\n')
            ])

            # Tools status
            tools_count = self.agent_status.get('tools_count', 0)
            parts.extend([
                ('class:sidepanel.content', f'Tools: {tools_count} available\n')
            ])

            # Last update
            last_update = self.agent_status.get('last_update')
            if last_update:
                parts.extend([
                    ('class:sidepanel.content', f'Updated: {last_update}')
                ])

            content = FormattedText(parts)

        return Window(
            content=FormattedTextControl(text=content),
            wrap_lines=True,
            style='class:sidepanel.content'
        )

    def create_container(self):
        """Create the container for the side panel."""
        # Panel title
        title_window = Window(
            content=FormattedTextControl(
                text=FormattedText([
                    ('class:sidepanel.title', ' 📋 Control Panel ')
                ])
            ),
            height=1
        )

        # Create sections
        sections = HSplit([
            title_window,
            self.status_section.create_container(),
            self.memory_section.create_container(),
            self.metrics_section.create_container(),
            self.tools_section.create_container(),
        ])

        # Wrap in conditional container
        return ConditionalContainer(
            content=sections,
            filter=self.visibility_filter
        )


class ProgressIndicator:
    """Progress indicator for long-running operations."""

    def __init__(self):
        self._active = False
        self._message = ""
        self._progress = 0.0

    @property
    def active(self) -> bool:
        """Check if progress indicator is active."""
        return self._active

    def start(self, message: str):
        """Start the progress indicator."""
        self._active = True
        self._message = message
        self._progress = 0.0
        get_app().invalidate()

    def update(self, progress: float, message: Optional[str] = None):
        """Update progress."""
        self._progress = max(0.0, min(1.0, progress))
        if message:
            self._message = message
        get_app().invalidate()

    def stop(self):
        """Stop the progress indicator."""
        self._active = False
        self._message = ""
        self._progress = 0.0
        get_app().invalidate()

    def is_active(self) -> bool:
        """Check if progress is active."""
        return self._active

    @property
    def active_filter(self):
        """Get active filter for ConditionalContainer."""
        return Condition(lambda: self._active)

    def create_container(self):
        """Create the progress indicator container."""
        def get_progress_text():
            if not self._active:
                return FormattedText([])

            percentage = int(self._progress * 100)
            bar_width = 20
            filled = int(self._progress * bar_width)
            bar = '█' * filled + '░' * (bar_width - filled)

            return FormattedText([
                ('class:progress.percentage', f'{percentage:3d}% '),
                ('class:progress.bar', f'[{bar}] '),
                ('', self._message)
            ])

        return ConditionalContainer(
            content=Window(
                content=FormattedTextControl(text=get_progress_text),
                height=1,
                style='class:progress.bar'
            ),
            filter=self.active_filter
        )