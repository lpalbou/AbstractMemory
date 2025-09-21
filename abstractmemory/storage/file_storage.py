"""
File-based storage backend.
"""

import pickle
import json
from pathlib import Path
from typing import Any

from abstractmemory.core.interfaces import IStorage


class FileStorage(IStorage):
    """Simple file-based storage"""

    def __init__(self, base_path: str = "./memory_storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def save(self, key: str, value: Any) -> None:
        """Save value to file"""
        file_path = self.base_path / f"{key}.pkl"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'wb') as f:
            pickle.dump(value, f)

    def load(self, key: str) -> Any:
        """Load value from file"""
        file_path = self.base_path / f"{key}.pkl"

        with open(file_path, 'rb') as f:
            return pickle.load(f)

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        file_path = self.base_path / f"{key}.pkl"
        return file_path.exists()