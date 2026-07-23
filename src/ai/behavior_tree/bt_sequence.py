"""G8.1: Sequence — AND logic. Stops on first FAILURE/RUNNING."""
from .bt_node import Node, Status


class Sequence(Node):
    def __init__(self, children: list[Node]):
        self._children = children

    def tick(self, board):
        for c in self._children:
            s = c.tick(board)
            if s != Status.SUCCESS:
                return s
        return Status.SUCCESS

    def name(self) -> str:
        return "Sequence"
