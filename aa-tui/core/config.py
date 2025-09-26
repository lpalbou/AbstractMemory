"""Configuration management for the TUI application."""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

@dataclass
class TUIConfig:
    """Configuration for the TUI application."""

    # Agent configuration
    model: str = "qwen3-coder:30b"
    provider: str = "ollama"
    memory_path: str = "./agent_memory"
    identity_name: str = "autonomous_assistant"
    enable_tools: bool = True
    enable_memory_tools: bool = True
    timeout: float = 7200.0

    # TUI-specific configuration
    show_side_panel: bool = True
    side_panel_width: int = 30
    auto_scroll: bool = True
    mouse_support: bool = True

    # Theme configuration
    theme: str = "dark"
    enable_syntax_highlighting: bool = True
    show_line_numbers: bool = True

    # Behavior configuration
    auto_save_session: bool = True
    max_conversation_history: int = 1000
    foldable_sections_default_state: str = "collapsed"  # "expanded" or "collapsed"

    # ReAct configuration
    context_tokens: int = 2000
    max_iterations: int = 25
    include_memory_in_react: bool = True
    observation_display_limit: int = 500
    save_scratchpad: bool = True
    scratchpad_confidence: float = 0.8

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'TUIConfig':
        """Create configuration from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

    def save_to_file(self, file_path: Path):
        """Save configuration to file."""
        import json
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: Path) -> 'TUIConfig':
        """Load configuration from file."""
        import json
        if file_path.exists():
            with open(file_path, 'r') as f:
                config_dict = json.load(f)
            return cls.from_dict(config_dict)
        return cls()