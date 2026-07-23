"""G8.4: CombatEnvironment — Gym-like RL wrapper."""
from ..mcts.simulation_state import SimulationState
from ..mcts.action import CombatAction, get_possible_actions
from ..mcts.mcts_search import _apply_action, _evaluate_terminal
from .observation import Observation


class StepResult:
    __slots__ = ('observation', 'reward', 'terminal')
    def __init__(self, obs=None, reward=0.0, terminal=False):
        self.observation = obs or Observation()
        self.reward = reward; self.terminal = terminal


class CombatEnvironment:
    def __init__(self):
        self._state = SimulationState()
        self._rng_seed = 42

    def reset(self, initial: SimulationState) -> Observation:
        self._state = initial.clone()
        self._rng_seed = self._state.rng.seed
        return Observation.from_state(self._state)

    def step(self, action: CombatAction) -> StepResult:
        if self._state.is_terminal():
            return StepResult(Observation.from_state(self._state), 0, True)
        prev_hp = self._state.player.hp
        rng = [self._rng_seed]
        _apply_action(self._state, action, rng)
        self._rng_seed = rng[0]
        # Reward: damage dealt - damage taken + terminal bonus
        reward = 0
        for m in self._state.monsters:
            if not m.alive: reward += 50.0
        hp_delta = self._state.player.hp - prev_hp
        if hp_delta < 0: reward += hp_delta
        if self._state.victory: reward += 200.0
        if not self._state.player.alive: reward -= 200.0
        return StepResult(Observation.from_state(self._state), reward,
                          self._state.terminal)

    def is_done(self) -> bool:
        return self._state.is_terminal()

    def state(self) -> SimulationState:
        return self._state
