"""G8.1: Behavior Tree — base node + status enum. Pure Python, zero game deps."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class Status(Enum):
    SUCCESS = 0
    FAILURE = 1
    RUNNING = 2


class Node(ABC):
    """Abstract BT node."""

    @abstractmethod
    def tick(self, board: "Blackboard") -> Status:
        """Evaluate this node. Returns SUCCESS/FAILURE/RUNNING."""

    def name(self) -> str:
        return type(self).__name__

    def is_condition(self) -> bool:
        return False

    def is_action(self) -> bool:
        return False
