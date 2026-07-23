"""G8.3: MCTSNode — UCT tree node for Monte Carlo Tree Search."""
from .simulation_state import SimulationState
from .action import CombatAction, action_name
import math
import random


class MCTSNode:
    __slots__ = ('state', 'action', 'parent', 'children', 'visits', 'reward',
                 '_untried_actions')

    def __init__(self, state: SimulationState = None,
                 action: CombatAction = CombatAction.WAIT,
                 parent: "MCTSNode | None" = None):
        self.state = state.clone() if state else SimulationState()
        self.action = action
        self.parent = parent
        self.children: list[MCTSNode] = []
        self.visits = 0
        self.reward = 0.0
        self._untried_actions: list[CombatAction] = []

    def uct_value(self, C: float = 1.414) -> float:
        if self.visits == 0:
            return 1e9
        exploitation = self.reward / self.visits
        parent_visits = self.parent.visits if self.parent else 1
        exploration = C * math.sqrt(math.log(parent_visits) / self.visits)
        return exploitation + exploration

    def is_fully_expanded(self) -> bool:
        return len(self._untried_actions) == 0

    def is_terminal(self) -> bool:
        return self.state.is_terminal()
