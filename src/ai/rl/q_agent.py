"""G8.4: QAgent — tabular Q-learning agent."""
from ..mcts.simulation_state import SimulationState
from ..mcts.action import CombatAction, get_possible_actions
from .observation import Observation
import random, math


class QAgent:
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.1):
        self._q: dict[str, float] = {}
        self._alpha = alpha; self._gamma = gamma; self._epsilon = epsilon

    def select(self, state: SimulationState, seed: int = 0) -> CombatAction:
        actions = get_possible_actions(state)
        if not actions:
            return CombatAction.WAIT
        obs_key = Observation.from_state(state).to_key()
        if random.random() < self._epsilon:
            return random.choice(actions)
        best, best_q = actions[0], -float('inf')
        for a in actions:
            qv = self._q.get(f"{obs_key}|{a.value}", 0.0)
            if qv > best_q:
                best_q, best = qv, a
        return best

    def update(self, obs: Observation, action: CombatAction,
               reward: float, next_obs: Observation):
        s_key = obs.to_key()
        sn_key = next_obs.to_key()
        old_q = self._q.get(f"{s_key}|{action.value}", 0.0)
        max_next = max(
            (self._q.get(f"{sn_key}|{a.value}", 0.0)
             for a in list(CombatAction)),
            default=0)
        self._q[f"{s_key}|{action.value}"] = (
            old_q + self._alpha * (reward + self._gamma * max_next - old_q))

    def table_size(self) -> int:
        return len(self._q)

    def action_distribution(self) -> list[tuple[str, int, float]]:
        from ..mcts.action import action_name
        from collections import defaultdict
        counts = defaultdict(int)
        sums = defaultdict(float)
        for key, qv in self._q.items():
            aid = int(key.split("|")[-1])
            name = action_name(CombatAction(aid))
            counts[name] += 1; sums[name] += qv
        return [(n, counts[n], sums[n]/counts[n]) for n in sorted(counts)]
