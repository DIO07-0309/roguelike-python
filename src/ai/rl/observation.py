"""G8.4: Observation — fixed-length feature vector for RL."""
from __future__ import annotations
from ..mcts.simulation_state import SimulationState


class Observation:
    __slots__ = ('player_hp_ratio', 'player_attack', 'enemy_count',
                 'nearest_enemy_dist', 'strongest_hp_ratio', 'boss_present',
                 'buff_count')

    def __init__(self):
        self.player_hp_ratio = 1.0; self.player_attack = 10.0
        self.enemy_count = 0; self.nearest_enemy_dist = 99.0
        self.strongest_hp_ratio = 0; self.boss_present = 0
        self.buff_count = 0

    @staticmethod
    def from_state(state: SimulationState) -> "Observation":
        obs = Observation()
        p = state.player
        obs.player_hp_ratio = p.hp / p.max_hp if p.max_hp > 0 else 0
        obs.player_attack = float(p.attack)
        alive, nearest, strongest, has_boss = 0, 999, 0, False
        for m in state.monsters:
            if not m.alive: continue
            alive += 1
            d = abs(m.x - p.x) + abs(m.y - p.y)
            if d < nearest: nearest = d
            m_ratio = m.hp / m.max_hp if m.max_hp > 0 else 0
            if m_ratio > strongest: strongest = m_ratio
            if m.is_boss: has_boss = True
        obs.enemy_count = float(alive)
        obs.nearest_enemy_dist = nearest
        obs.strongest_hp_ratio = strongest
        obs.boss_present = 1.0 if has_boss else 0
        obs.buff_count = float(len(p.buffs))
        return obs

    def to_vector(self) -> list[float]:
        return [self.player_hp_ratio, self.player_attack, self.enemy_count,
                self.nearest_enemy_dist, self.strongest_hp_ratio,
                self.boss_present, self.buff_count]

    def to_key(self) -> str:
        hp_b = int(self.player_hp_ratio * 10)
        atk_b = int(self.player_attack / 5.0)
        ec_b = int(self.enemy_count)
        nd_b = int(self.nearest_enemy_dist / 2.0)
        boss_b = int(self.boss_present)
        return f"{hp_b}:{atk_b}:{ec_b}:{nd_b}:{boss_b}"
