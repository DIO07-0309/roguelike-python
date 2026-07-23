"""G8.4: RandomAgent — uniform random action baseline."""
from ..mcts.simulation_state import SimulationState
from ..mcts.action import CombatAction, get_possible_actions
import random


class RandomAgent:
    def select(self, state: SimulationState, seed: int = 0) -> CombatAction:
        actions = get_possible_actions(state)
        if not actions:
            return CombatAction.WAIT
        return random.choice(actions)
