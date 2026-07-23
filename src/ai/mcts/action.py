"""G8.3: CombatAction + action filtering."""
from enum import Enum, auto
from .simulation_state import SimulationState


class CombatAction(Enum):
    ATTACK = auto()
    SKILL_1 = auto(); SKILL_2 = auto(); SKILL_3 = auto(); SKILL_4 = auto()
    MOVE_UP = auto(); MOVE_DOWN = auto(); MOVE_LEFT = auto(); MOVE_RIGHT = auto()
    WAIT = auto()


_ACTION_NAMES = {
    CombatAction.ATTACK: "attack",
    CombatAction.SKILL_1: "skill_1", CombatAction.SKILL_2: "skill_2",
    CombatAction.SKILL_3: "skill_3", CombatAction.SKILL_4: "skill_4",
    CombatAction.MOVE_UP: "move_up", CombatAction.MOVE_DOWN: "move_down",
    CombatAction.MOVE_LEFT: "move_left", CombatAction.MOVE_RIGHT: "move_right",
    CombatAction.WAIT: "wait",
}


def action_name(a: CombatAction) -> str:
    return _ACTION_NAMES.get(a, "wait")


def all_actions() -> list[CombatAction]:
    return [CombatAction.ATTACK, CombatAction.SKILL_1, CombatAction.SKILL_2,
            CombatAction.SKILL_3, CombatAction.SKILL_4,
            CombatAction.MOVE_UP, CombatAction.MOVE_DOWN,
            CombatAction.MOVE_LEFT, CombatAction.MOVE_RIGHT]


def get_possible_actions(state: SimulationState) -> list[CombatAction]:
    p = state.player
    if not p.alive:
        return []
    result = []
    enemy_in_range = any(
        m.alive and abs(m.x - p.x) + abs(m.y - p.y) < 2.0
        for m in state.monsters)
    if enemy_in_range and p.attack_cooldown <= 0:
        result.append(CombatAction.ATTACK)
    for i in range(4):
        if p.skill_cooldowns[i] <= 0:
            result.append(CombatAction(list(CombatAction)[1 + i]))
    for d, (dx, dy) in enumerate([(0, -1), (0, 1), (-1, 0), (1, 0)]):
        nx, ny = p.x + dx, p.y + dy
        if 0 <= nx < 40 and 0 <= ny < 30:
            result.append(CombatAction(list(CombatAction)[5 + d]))
    result.append(CombatAction.WAIT)
    return result
