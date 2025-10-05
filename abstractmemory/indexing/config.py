"""
Memory indexing configuration management.

Manages which memory modules are indexed to LanceDB and provides
toggle functionality for dynamic index management.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class IndexConfig:
    """Configuration for a single memory module index."""
    enabled: bool = False
    last_indexed: Optional[str] = None
    index_count: int = 0
    table_name: Optional[str] = None
    auto_update: bool = True


@dataclass
class MemoryIndexConfig:
    """Main configuration for memory module indexing."""

    # Memory modules with their index configurations
    notes: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="notes"))
    verbatim: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=False, table_name="verbatim"))
    library: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="library"))
    links: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="links"))
    core: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="core_memory"))
    working: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=False, table_name="working_memory"))
    episodic: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="episodic_memory"))
    semantic: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=True, table_name="semantic_memory"))
    people: IndexConfig = field(default_factory=lambda: IndexConfig(enabled=False, table_name="people"))

    # Global settings
    auto_index_on_create: bool = True
    auto_index_on_update: bool = True
    max_tokens_per_module: int = 500
    dynamic_injection_enabled: bool = True

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"

    @classmethod
    def load(cls, config_path: Path) -> "MemoryIndexConfig":
        """Load configuration from JSON file."""
        if not config_path.exists():
            # Return default config if file doesn't exist
            config = cls()
            config.save(config_path)
            return config

        with open(config_path, 'r') as f:
            data = json.load(f)

        # Convert nested dicts to IndexConfig objects
        for module in ['notes', 'verbatim', 'library', 'links', 'core',
                      'working', 'episodic', 'semantic', 'people']:
            if module in data and isinstance(data[module], dict):
                data[module] = IndexConfig(**data[module])

        return cls(**data)

    def save(self, config_path: Path) -> None:
        """Save configuration to JSON file."""
        self.last_modified = datetime.now().isoformat()

        # Convert to dict with nested IndexConfig objects serialized
        data = {}
        for key, value in asdict(self).items():
            if isinstance(value, dict):  # IndexConfig gets converted to dict
                data[key] = value
            else:
                data[key] = value

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def enable_module(self, module_name: str) -> bool:
        """Enable indexing for a specific module."""
        if hasattr(self, module_name):
            module_config = getattr(self, module_name)
            if isinstance(module_config, IndexConfig):
                module_config.enabled = True
                return True
        return False

    def disable_module(self, module_name: str) -> bool:
        """Disable indexing for a specific module."""
        if hasattr(self, module_name):
            module_config = getattr(self, module_name)
            if isinstance(module_config, IndexConfig):
                module_config.enabled = False
                return True
        return False

    def get_enabled_modules(self) -> List[str]:
        """Get list of enabled memory modules."""
        enabled = []
        for module_name in ['notes', 'verbatim', 'library', 'links', 'core',
                           'working', 'episodic', 'semantic', 'people']:
            module_config = getattr(self, module_name)
            if module_config.enabled:
                enabled.append(module_name)
        return enabled

    def get_module_config(self, module_name: str) -> Optional[IndexConfig]:
        """Get configuration for a specific module."""
        if hasattr(self, module_name):
            config = getattr(self, module_name)
            if isinstance(config, IndexConfig):
                return config
        return None

    def update_index_stats(self, module_name: str, count: int) -> None:
        """Update indexing statistics for a module."""
        module_config = self.get_module_config(module_name)
        if module_config:
            module_config.last_indexed = datetime.now().isoformat()
            module_config.index_count = count

    def get_status(self) -> Dict:
        """Get detailed status of all modules."""
        # Calculate summary stats
        enabled_modules = self.get_enabled_modules()
        total_indexed = sum(
            getattr(self, m).index_count
            for m in enabled_modules
        )

        status = {
            "summary": {
                "enabled_modules": len(enabled_modules),
                "total_modules": 9,
                "total_indexed_items": total_indexed,
                "config_version": self.version
            },
            "global": {
                "auto_index_on_create": self.auto_index_on_create,
                "auto_index_on_update": self.auto_index_on_update,
                "dynamic_injection_enabled": self.dynamic_injection_enabled,
                "max_tokens_per_module": self.max_tokens_per_module,
                "version": self.version,
                "last_modified": self.last_modified
            },
            "modules": {}
        }

        for module_name in ['notes', 'verbatim', 'library', 'links', 'core',
                           'working', 'episodic', 'semantic', 'people']:
            module_config = getattr(self, module_name)
            status["modules"][module_name] = {
                "enabled": module_config.enabled,
                "table_name": module_config.table_name,
                "last_indexed": module_config.last_indexed,
                "index_count": module_config.index_count,
                "auto_update": module_config.auto_update
            }

        return status

    def validate_table_names(self) -> List[str]:
        """Validate and return unique table names for enabled modules."""
        tables = set()
        for module_name in self.get_enabled_modules():
            module_config = self.get_module_config(module_name)
            if module_config and module_config.table_name:
                tables.add(module_config.table_name)
        return sorted(list(tables))

    def should_index_module(self, module_name: str, operation: str = "create") -> bool:
        """
        Determine if a module should be indexed based on config and operation.

        Args:
            module_name: Name of the memory module
            operation: Type of operation ("create", "update", "manual")
        """
        module_config = self.get_module_config(module_name)
        if not module_config or not module_config.enabled:
            return False

        if operation == "create" and self.auto_index_on_create:
            return True
        elif operation == "update" and self.auto_index_on_update:
            return module_config.auto_update
        elif operation == "manual":
            return True

        return False


class IndexManager:
    """Manager for memory index configuration and operations."""

    def __init__(self, memory_base_path: Path):
        self.memory_base_path = Path(memory_base_path)
        self.config_path = self.memory_base_path / ".memory_index_config.json"
        self.config = MemoryIndexConfig.load(self.config_path)

    def save_config(self) -> None:
        """Save current configuration to disk."""
        self.config.save(self.config_path)

    def enable_module(self, module_name: str, auto_index: bool = True) -> bool:
        """
        Enable indexing for a module and optionally trigger indexing.

        Args:
            module_name: Name of the module to enable
            auto_index: Whether to immediately index the module

        Returns:
            True if successful, False otherwise
        """
        if self.config.enable_module(module_name):
            self.save_config()
            if auto_index:
                # Trigger indexing (will be implemented with MemoryIndexer)
                pass
            return True
        return False

    def disable_module(self, module_name: str, drop_table: bool = False) -> bool:
        """
        Disable indexing for a module and optionally drop its table.

        Args:
            module_name: Name of the module to disable
            drop_table: Whether to drop the LanceDB table

        Returns:
            True if successful, False otherwise
        """
        if self.config.disable_module(module_name):
            self.save_config()
            if drop_table:
                # Drop table (will be implemented with LanceDB storage)
                pass
            return True
        return False

    def get_indexing_stats(self) -> Dict:
        """Get comprehensive indexing statistics."""
        stats = self.config.get_status()

        # Add computed statistics
        enabled_count = len(self.config.get_enabled_modules())
        total_indexed = sum(
            getattr(self.config, m).index_count
            for m in self.config.get_enabled_modules()
        )

        stats["summary"] = {
            "enabled_modules": enabled_count,
            "total_modules": 9,
            "total_indexed_items": total_indexed,
            "config_version": self.config.version
        }

        return stats

    def reset_module(self, module_name: str) -> bool:
        """Reset a module's index configuration and stats."""
        module_config = self.config.get_module_config(module_name)
        if module_config:
            module_config.last_indexed = None
            module_config.index_count = 0
            self.save_config()
            return True
        return False

    def set_token_limit(self, module_name: str, limit: int) -> bool:
        """Set token limit for a specific module in context injection."""
        # This would be module-specific token limits
        # For now, using global limit
        if 0 < limit <= 2000:
            self.config.max_tokens_per_module = limit
            self.save_config()
            return True
        return False