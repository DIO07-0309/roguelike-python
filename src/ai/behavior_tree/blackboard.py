"""G8.1: Blackboard — shared state key-value store. Reusable by MCTS/RL."""
from typing import Any


class Blackboard:
    def __init__(self):
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._data

    def clear(self):
        self._data.clear()
