"""G8.1: BTAgent — wraps Behavior Tree with same interface as DecisionAgent."""
from src.ai.behavior_tree import (
    Status, Selector, Sequence, Condition, Action, Blackboard
)
import math, random


class BTAgent:
    def __init__(self):
        self._board = Blackboard()
        self._root = None
        self._frame = 0
        self._build_tree()

    def _build_tree(self):
        # Conditions
        boss_intro = Condition("BossIntro", lambda b: b.get("boss_intro", False))
        stairs_active = Condition("StairsActive", lambda b: b.get("stairs_active", False))
        hp_low = Condition("HPLow", lambda b: b.get("hp_ratio", 1.0) < 0.35)
        heal_ready = Condition("HealReady", lambda b: b.get("heal_ready", False))
        enemy_near = Condition("EnemyNear", lambda b: b.get("enemy_near", False))
        skill_ready = Condition("SkillReady", lambda b: b.get("skill_ready", False))
        enemies_aoe = Condition("EnemiesInAoE", lambda b: b.get("enemies_in_aoe", 0) >= 2)
        near_room = Condition("NearRoom", lambda b: b.get("near_room", False))

        # Actions
        confirm = Action("Confirm", lambda b: b.set("action", "confirm"))
        descend = Action("Descend", lambda b: b.set("action", "descend"))
        do_heal = Action("Heal", lambda b: b.set("action", "skill_3"))
        do_attack = Action("Attack", lambda b: b.set("action", "attack"))
        do_skill = Action("Skill", lambda b: b.set("action", "skill_1"))
        do_aoe = Action("AoESkill", lambda b: b.set("action", "skill_2"))
        do_pickup = Action("Pickup", lambda b: b.set("action", "pickup"))
        do_wander = Action("Wander", lambda b: b.set("action", "move_up"))

        # Heal sequence: HPLow + HealReady → heal
        heal_seq = Sequence([hp_low, heal_ready, do_heal])
        # AoE sequence: multiple enemies + skill ready
        aoe_seq = Sequence([enemies_aoe, skill_ready, do_aoe])
        # Combat sequence: enemy near → attack
        combat_seq = Sequence([enemy_near, do_attack])
        # Pickup sequence
        pickup_seq = Sequence([near_room, do_pickup])

        self._root = Selector([
            boss_intro, stairs_active, heal_seq, aoe_seq,
            combat_seq, pickup_seq, do_wander,
        ])

    def _sync_state(self, player, monsters, game_map, stairs_active, boss_intro):
        if not player:
            return
        self._board.set("boss_intro", boss_intro)
        self._board.set("stairs_active", stairs_active)
        hp = player.combat.current_hp; mhp = max(1, player.combat.max_hp)
        self._board.set("hp_ratio", hp / mhp)
        self._board.set("heal_ready", len(getattr(getattr(player, "skills", None), "active_skills", [])) > 2)

        alive = 0; nearest = 9999
        for m in monsters:
            if not m.combat.is_alive: continue
            alive += 1
            d = math.hypot(m.entity.rect.centerx - player.entity.rect.centerx,
                           m.entity.rect.centery - player.entity.rect.centery)
            if d < nearest: nearest = d
        self._board.set("enemy_near", nearest < 3.0 * 32)
        self._board.set("skill_ready", True)
        self._board.set("enemies_in_aoe", sum(1 for m in monsters
            if m.combat.is_alive and math.hypot(m.entity.rect.centerx - player.entity.rect.centerx,
                m.entity.rect.centery - player.entity.rect.centery) < 4.0 * 32))

        self._board.set("near_room", False)
        if game_map:
            for sr in getattr(game_map, "special_rooms", []):
                dx = player.entity.rect.centerx - (sr.cx * 32 + 16)
                dy = player.entity.rect.centery - (sr.cy * 32 + 16)
                if math.hypot(dx, dy) < 3.0 * 32:
                    self._board.set("near_room", True)
                    break

    def start(self, player=None):
        self._frame = 0

    def tick(self):
        self._frame += 1

    def is_action_just_pressed(self, name, player, monsters, game_map=None,
                                stairs_active=False, boss_intro=False):
        if not player: return False
        self._sync_state(player, monsters, game_map, stairs_active, boss_intro)
        self._board.set("action", "move_up")
        self._root.tick(self._board)
        return self._board.get("action", "move_up") == name

    def accept_event(self, risk_pct, effect_desc, player):
        if not player: return False
        hp = player.combat.current_hp / max(1, player.combat.max_hp)
        if risk_pct > 0.40 and hp < 0.50: return False
        if risk_pct > 0.25 and hp < 0.30: return False
        if risk_pct > 0.10 and hp < 0.15: return False
        high_value = any(k in effect_desc for k in ("relic", "skill", "legendary"))
        if high_value and hp > 0.60: return True
        if risk_pct == 0: return True
        return hp > risk_pct * 2.0 + 0.25
