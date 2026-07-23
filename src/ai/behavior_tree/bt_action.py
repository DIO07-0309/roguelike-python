"""G8.1: Action — leaf node executing a function on Blackboard."""
from .bt_node import Node, Status
from typing import Callable


class Action(Node):
    def __init__(self, name: str, executor: Callable[["Blackboard"], None]):
        self._name = name
        self._exec = executor

    def tick(self, board):
        self._exec(board)
        return Status.SUCCESS

    def is_action(self) -> bool:
        return True

    def name(self) -> str:
        return self._name
