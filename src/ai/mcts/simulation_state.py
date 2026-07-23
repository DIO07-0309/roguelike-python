"""G8.3: SimulationState — minimal combat snapshot for MCTS rollouts."""
from __future__ import annotations
from dataclasses import dataclass, field
import math, random


@dataclass
class BuffSnapshot:
    id: str = ""
    stacks: int = 0
    remaining: float = 0


@dataclass
class PlayerSnapshot:
    hp: float = 100; max_hp: float = 100
    x: float = 0; y: float = 0
    attack: int = 10; pdef: int = 3; mdef: int = 1
    buffs: list = field(default_factory=list)
    attack_cooldown: float = 0
    skill_cooldowns: list = field(default_factory=lambda: [0, 0, 0, 0])
    alive: bool = True


@dataclass
class MonsterSnapshot:
    type: str = ""
    hp: float = 20; max_hp: float = 20
    x: float = 0; y: float = 0
    attack: int = 4; pdef: int = 1; mdef: int = 0
    buffs: list = field(default_factory=list)
    alive: bool = True; is_boss: bool = False


@dataclass
class RNGState:
    seed: int = 0; calls: int = 0

    def next(self) -> int:
        s = self.seed + self.calls * 1103515245 + 12345
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s


class SimulationState:
    __slots__ = ('player', 'monsters', 'rng', 'depth', 'terminal', 'victory')

    def __init__(self):
        self.player = PlayerSnapshot()
        self.monsters: list[MonsterSnapshot] = []
        self.rng = RNGState()
        self.depth = 0
        self.terminal = False
        self.victory = False

    def clone(self) -> "SimulationState":
        s = SimulationState()
        s.player = PlayerSnapshot(**self.player.__dict__)
        s.player.buffs = [BuffSnapshot(**b.__dict__) for b in self.player.buffs]
        s.monsters = [MonsterSnapshot(**m.__dict__) for m in self.monsters]
        for ms in s.monsters:
            ms.buffs = [BuffSnapshot(**b.__dict__) for b in ms.buffs]
        s.rng = RNGState(self.rng.seed, self.rng.calls)
        s.depth = self.depth
        s.terminal = self.terminal
        s.victory = self.victory
        return s

    def is_terminal(self) -> bool:
        return self.terminal or not self.player.alive

    def alive_monsters(self) -> int:
        return sum(1 for m in self.monsters if m.alive)
