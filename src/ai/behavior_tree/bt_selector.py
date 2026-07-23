"""G8.1: Selector — OR logic. First non-FAILURE wins."""
from .bt_node import Node, Status


class Selector(Node):
    def __init__(self, children: list[Node]):
        self._children = children

    def tick(self, board):
        for c in self._children:
            s = c.tick(board)
            if s != Status.FAILURE:
                return s
        return Status.FAILURE

    def name(self) -> str:
        return "Selector"
