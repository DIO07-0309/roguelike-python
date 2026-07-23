"""G8.1: Condition — leaf node checking a predicate on Blackboard."""
from .bt_node import Node, Status
from typing import Callable


class Condition(Node):
    def __init__(self, name: str, predicate: Callable[["Blackboard"], bool]):
        self._name = name
        self._pred = predicate

    def tick(self, board):
        return Status.SUCCESS if self._pred(board) else Status.FAILURE

    def is_condition(self) -> bool:
        return True

    def name(self) -> str:
        return self._name
