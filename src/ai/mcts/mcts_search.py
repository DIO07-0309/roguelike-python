"""G8.3: MCTS search engine — Combat Action Search, Python port."""
from .simulation_state import SimulationState
from .action import CombatAction, get_possible_actions
from .mcts_node import MCTSNode
import random


def _apply_action(state: SimulationState, a: CombatAction, rng_seed: list):
    """Mutate state in-place (simplified combat simulation)."""
    p = state.player
    if not p.alive:
        return

    def lcg():
        rng_seed[0] = (rng_seed[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return (rng_seed[0] & 0x7FFFFFFF) / 2147483648.0

    def dist(px, py, mx, my):
        return abs(px - mx) + abs(py - my)

    if a == CombatAction.ATTACK:
        best, bd = None, 999
        for m in state.monsters:
            if not m.alive:
                continue
            d = dist(p.x, p.y, m.x, m.y)
            if d < 1.5 and d < bd:
                bd, best = d, m
        if best:
            base = p.attack - int(best.pdef * 0.5)
            dmg = max(1, int(base * (0.8 + 0.4 * lcg())))
            best.hp -= dmg
            if best.hp <= 0:
                best.alive = False
        p.attack_cooldown = 0.5

    elif a in (CombatAction.SKILL_1, CombatAction.SKILL_2,
               CombatAction.SKILL_3, CombatAction.SKILL_4):
        si = list(CombatAction).index(a) - 1
        for m in state.monsters:
            if not m.alive:
                continue
            d = dist(p.x, p.y, m.x, m.y)
            if d < 3.0:
                base = int(p.attack * 1.5) - int(m.pdef * 0.5)
                dmg = max(1, int(base * (0.8 + 0.4 * lcg())))
                m.hp -= dmg
                if m.hp <= 0:
                    m.alive = False
        p.skill_cooldowns[si] = 3.0

    elif a == CombatAction.MOVE_UP: p.y -= 1
    elif a == CombatAction.MOVE_DOWN: p.y += 1
    elif a == CombatAction.MOVE_LEFT: p.x -= 1
    elif a == CombatAction.MOVE_RIGHT: p.x += 1

    # Cooldown decay
    if p.attack_cooldown > 0:
        p.attack_cooldown -= 0.25
    for i in range(4):
        if p.skill_cooldowns[i] > 0:
            p.skill_cooldowns[i] -= 0.25

    # Monster retaliation
    for m in state.monsters:
        if not m.alive:
            continue
        if dist(p.x, p.y, m.x, m.y) < 1.5 and lcg() < 0.4:
            dmg = max(1, m.attack - int(p.pdef * 0.5))
            p.hp -= dmg
            if p.hp <= 0:
                p.alive = False

    state.depth += 1
    if all(not m.alive for m in state.monsters):
        state.victory = True
        state.terminal = True
    if not p.alive:
        state.terminal = True


def _evaluate_terminal(state: SimulationState) -> float:
    if state.victory:
        return 1000.0
    if not state.player.alive:
        return -1000.0
    score = state.player.hp * 2.0
    for m in state.monsters:
        if not m.alive:
            score += 200.0
        else:
            score -= m.hp * 1.5
    return score - state.depth * 5.0


class MCTS:
    def __init__(self, iterations: int = 100):
        self._iterations = iterations

    def search(self, state: SimulationState) -> CombatAction:
        root = MCTSNode(state=state, action=CombatAction.WAIT)

        for i in range(self._iterations):
            node = self._select(root)
            if not node.is_terminal() and not node.is_fully_expanded():
                self._expand(node)
                if node.children:
                    node = node.children[-1]
            rng = [state.rng.next() + i * 7919]
            reward = self._simulate(node.state, rng)
            self._backpropagate(node, reward)

        best, best_visits = None, -1
        for c in root.children:
            if c.visits > best_visits:
                best_visits, best = c.visits, c
        if best:
            return best.action
        actions = get_possible_actions(state)
        return actions[0] if actions else CombatAction.WAIT

    def _select(self, node: MCTSNode) -> MCTSNode:
        while not node.is_terminal():
            if not node.is_fully_expanded():
                return node
            best, best_uct = None, -1e9
            for c in node.children:
                u = c.uct_value()
                if u > best_uct:
                    best_uct, best = u, c
            if not best:
                return node
            node = best
        return node

    def _expand(self, node: MCTSNode):
        actions = get_possible_actions(node.state)
        for a in actions:
            child = MCTSNode(state=node.state, action=a, parent=node)
            rng = [node.state.rng.next() + len(node.children) * 7331]
            _apply_action(child.state, a, rng)
            node.children.append(child)

    def _simulate(self, state: SimulationState, rng: list) -> float:
        sim = state.clone()
        for _ in range(10):
            if sim.is_terminal():
                break
            actions = get_possible_actions(sim)
            if not actions:
                break
            a = actions[(rng[0] + sim.depth) % len(actions)]
            _apply_action(sim, a, rng)
        return _evaluate_terminal(sim)

    def _backpropagate(self, leaf: MCTSNode, reward: float):
        node = leaf
        while node:
            node.visits += 1
            node.reward += reward
            reward *= 0.95
            node = node.parent
