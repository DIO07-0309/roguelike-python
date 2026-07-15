"""
Buff System — B1-B7 unified (Python port)
"""
import json
import math
import random
import os
import sys
from dataclasses import dataclass
from enum import Enum


# ---- BuffInstance ----
@dataclass
class BuffInstance:
    id: str              # "poison"|"slow"|"attack_up"
    stacks: int = 1
    remaining: float = 0.0
    tick_timer: float = 0.0


# ---- BuffDef ----
@dataclass
class BuffDef:
    id: str
    duration: float = 0.0
    max_stacks: int = 1
    tick_interval: float = 0.0
    tick_damage: int = 0
    display_name: str = ""
    short_name: str = ""
    hud_color: tuple = (200, 200, 200)


# ---- BuffTrigger ----
class BuffTarget(Enum):
    SELF = "self"
    ENEMY = "enemy"

@dataclass
class BuffTrigger:
    buff_id: str
    stacks: int = 1
    chance: float = 1.0
    target: BuffTarget = BuffTarget.ENEMY


# ---- Config table ----
_g_buf: dict[str, BuffDef] = {}

# Hardcoded defaults (always loaded first as safety net)
_DEFAULTS = [
    BuffDef("poison", duration=4.0, max_stacks=5, tick_interval=0.5, tick_damage=3,
            display_name="中毒", short_name="毒", hud_color=(100, 220, 80)),
    BuffDef("slow", duration=3.0, max_stacks=3,
            display_name="减速", short_name="慢", hud_color=(120, 180, 255)),
    BuffDef("attack_up", duration=6.0, max_stacks=3,
            display_name="攻击提升", short_name="攻", hud_color=(255, 150, 50)),
]

def _load_defaults():
    for d in _DEFAULTS:
        _g_buf[d.id] = d


def _resolve_path(path: str) -> str:
    """Resolve resource path for both dev and PyInstaller builds."""
    if os.path.exists(path):
        return path
    # PyInstaller: try _MEIPASS
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    if os.path.exists(alt):
        return alt
    return path    # let it fail gracefully


def load_buff_defs(json_path: str = "resources/buffs.json") -> bool:
    global _g_buf
    _load_defaults()   # safety: always load hardcoded first
    try:
        real_path = _resolve_path(json_path)
        with open(real_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            bid = item.get("id", "")
            if not bid:
                continue
            _g_buf[bid] = BuffDef(
                id=bid,
                duration=float(item.get("duration", 0.0)),
                max_stacks=int(item.get("max_stacks", 1)),
                tick_interval=float(item.get("tick_interval", 0.0)),
                tick_damage=int(item.get("tick_damage", 0)),
                display_name=str(item.get("display_name", "") or bid),
                short_name=str(item.get("short_name", "") or bid),
                hud_color=tuple(item.get("hud_color", [200, 200, 200])),
            )
        print(f"[Buff] Loaded {len(data)} buffs from json")
        return True
    except Exception as e:
        print(f"[Buff] JSON load failed ({e}) — using built-in defaults")
        return True   # defaults already loaded


def get_buff_def(bid: str) -> BuffDef | None:
    return _g_buf.get(bid)


# ---- Display helpers ----
def get_buff_display_name(bid: str) -> str:
    d = _g_buf.get(bid)
    return d.display_name if d else bid

def get_buff_short_name(bid: str) -> str:
    d = _g_buf.get(bid)
    return d.short_name if d else bid

def get_buff_hud_color(bid: str) -> tuple:
    d = _g_buf.get(bid)
    return d.hud_color if d else (200, 200, 200)

def format_buff_time(sec: float) -> str:
    return f"{sec:.1f}s"


# ---- Apply ----
def apply_buff(entity, bid: str, stacks: int = 1):
    if not entity or not hasattr(entity, "active_buffs"):
        return
    c = getattr(entity, "combat", None)
    if c and not c.is_alive:
        return
    d = get_buff_def(bid)
    if not d:
        return
    for b in entity.active_buffs:
        if b.id == bid:
            b.stacks = min(b.stacks + stacks, d.max_stacks)
            b.remaining = d.duration
            if d.tick_interval <= 0:
                b.tick_timer = 0.0
            return
    entity.active_buffs.append(BuffInstance(
        id=bid,
        stacks=min(stacks, d.max_stacks),
        remaining=d.duration,
        tick_timer=d.tick_interval if d.tick_interval > 0 else 0.0,
    ))


# ---- Tick ----
def tick_buffs(entity, dt: float):
    """逐帧结算 buff (B11/B12: 接入 venom_fang / plague_mask)。"""
    if not entity or not hasattr(entity, "active_buffs"):
        return
    c = getattr(entity, "combat", None)
    if not c or not c.is_alive:
        return
    from src.systems.relic_system import player_has_relic
    is_player = hasattr(entity, "inventory")  # heuristic: Player vs Monster
    i = 0
    while i < len(entity.active_buffs):
        b = entity.active_buffs[i]
        d = get_buff_def(b.id)
        removed = False
        b.remaining -= dt
        if d and d.tick_interval > 0 and c.is_alive:
            b.tick_timer -= dt
            while b.tick_timer <= 0 and b.remaining > 0 and c.is_alive:
                dmg = d.tick_damage * b.stacks
                if b.id == "poison":
                    if not is_player:          # B11: venom_fang — monster poison +1
                        dmg += 1  # (approximate: all monster poison is from player)
                    elif player_has_relic(entity, "plague_mask"):  # B12: plague_mask — player poison -1
                        dmg = max(0, dmg - 1)
                c.take_damage(dmg)
                b.tick_timer += d.tick_interval
                if not c.is_alive:
                    break
        if b.remaining <= 0:
            removed = True
        if removed:
            entity.active_buffs[i] = entity.active_buffs[-1]
            entity.active_buffs.pop()
        else:
            i += 1


# ---- Effective stats ----
def _count_stacks(buffs, bid: str) -> int:
    return sum(1 for b in buffs if b.id == bid)

def get_effective_attack(entity) -> int:
    if not entity or not hasattr(entity, "combat"):
        return 1
    from src.systems.relic_system import player_has_relic
    base = entity.combat.get_effective_attack()
    stacks = _count_stacks(getattr(entity, "active_buffs", []), "attack_up")
    berserk_s = _count_stacks(getattr(entity, "active_buffs", []), "berserk")
    blessing_s = _count_stacks(getattr(entity, "active_buffs", []), "blessing")
    momentum_s = _count_stacks(getattr(entity, "active_buffs", []), "momentum")
    adrenaline_s = _count_stacks(getattr(entity, "active_buffs", []), "adrenaline")
    blind_s = _count_stacks(getattr(entity, "active_buffs", []), "blind")
    atk = int(base * (1.0 + 0.30 * stacks + 0.25 * berserk_s + 0.10 * blessing_s
                          + 0.08 * momentum_s + 0.15 * adrenaline_s - 0.15 * blind_s))
    # B12+D8: relic multipliers
    if player_has_relic(entity, "war_drum"): atk = int(atk * 1.15)
    if player_has_relic(entity, "hunter_gloves"): atk = int(atk * 1.10)
    if player_has_relic(entity, "ancient_crown"): atk = int(atk * 1.08)
    if player_has_relic(entity, "dragon_heart"):  atk = int(atk * 1.15)
    if player_has_relic(entity, "infinity_orb"):  atk = int(atk * 1.20)
    # D8: blood_chalice — HP越低攻越高
    if player_has_relic(entity, "blood_chalice"):
        hp_r = entity.combat.current_hp / max(1, get_effective_max_hp(entity))
        bonus = max(0, (1.0 - hp_r) * 0.30)
        atk = int(atk * (1.0 + bonus))
    return max(1, atk)

def get_effective_speed(entity, base_speed: float = 200.0) -> float:
    if not entity or not hasattr(entity, "active_buffs"):
        return base_speed
    from src.systems.relic_system import player_has_relic
    stacks = _count_stacks(entity.active_buffs, "slow")
    speed = base_speed * (0.7 ** stacks)
    # B11+D8: relic speed bonuses
    if player_has_relic(entity, "hunters_eye"):   speed *= 1.10
    if player_has_relic(entity, "traveler_boots"): speed *= 1.08
    if player_has_relic(entity, "ancient_crown"):  speed *= 1.05
    if player_has_relic(entity, "dragon_heart"):   speed *= 1.08
    if player_has_relic(entity, "infinity_orb"):   speed *= 1.10
    # D8: adrenaline +5%/stack
    speed *= 1.05 ** _count_stacks(entity.active_buffs, "adrenaline")
    # D8: freeze → 0
    if _count_stacks(entity.active_buffs, "freeze") > 0:
        return 0.0
    # D8: stun/fear → ×0.30
    if _count_stacks(entity.active_buffs, "stun") > 0 or _count_stacks(entity.active_buffs, "fear") > 0:
        speed *= 0.30
    return speed

# B11/B12+D8: 有效最大生命 (blood_charm +20, iron_heart +10, dragon_heart +30, ancient_crown +8, infinity_orb +25)
def get_effective_max_hp(entity) -> int:
    if not entity or not hasattr(entity, "combat"):
        return 0
    from src.systems.relic_system import player_has_relic
    hp = entity.combat.max_hp
    if player_has_relic(entity, "blood_charm"):  hp += 20
    if player_has_relic(entity, "iron_heart"):   hp += 10
    if player_has_relic(entity, "dragon_heart"): hp += 30
    if player_has_relic(entity, "ancient_crown"): hp += 8
    if player_has_relic(entity, "infinity_orb"):  hp += 25
    return hp


# ---- Triggers ----
def apply_triggers(triggers: list[BuffTrigger], self, enemy):
    if not triggers:
        return
    for tr in triggers:
        if tr.target != BuffTarget.ENEMY:
            continue
        if tr.chance < 1.0 and random.random() >= tr.chance:
            continue
        apply_buff(enemy, tr.buff_id, tr.stacks)

def apply_triggers_self(triggers: list[BuffTrigger], self):
    if not triggers:
        return
    for tr in triggers:
        if tr.target == BuffTarget.ENEMY:
            continue
        if tr.chance < 1.0 and random.random() >= tr.chance:
            continue
        apply_buff(self, tr.buff_id, tr.stacks)
