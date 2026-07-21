"""
G6.4: Biome Event Framework — per-biome choice events with risk/reward.

Events trigger on floor entry (25% chance). Player picks 1 of 2 choices.
Each choice has an effect (reward) and a risk (cost).
"""

import json, os, sys, random
from dataclasses import dataclass, field


@dataclass
class EventChoice:
    text: str
    effect: str         # e.g. "buff:attack_up:2", "relic:1", "none"
    risk: str           # e.g. "spawn:elite_orc:1", "hp_loss:15", "none"
    message: str


@dataclass
class BiomeEventDef:
    id: str
    biome: str
    weight: int
    narrative: str
    choices: list[EventChoice]


# ── Registry ─────────────────────────────────────────────────

_events: list[BiomeEventDef] = []
_by_biome: dict[str, list[BiomeEventDef]] = {}


def _resolve(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_biome_event_defs(json_path: str = "resources/biome_events.json") -> bool:
    global _events, _by_biome
    try:
        with open(_resolve(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[BiomeEvent] Failed to load {json_path}: {e}")
        return False
    _events = []; _by_biome = {}
    for obj in data:
        choices = [EventChoice(**c) for c in obj.get("choices", [])]
        ev = BiomeEventDef(
            id=obj["id"], biome=obj["biome"], weight=obj.get("weight", 20),
            narrative=obj.get("narrative", ""), choices=choices,
        )
        _events.append(ev)
        _by_biome.setdefault(ev.biome, []).append(ev)
    print(f"[BiomeEvent] Loaded {len(_events)} events across {len(_by_biome)} biomes")
    return True


def pick_event_for_biome(biome_id: str) -> BiomeEventDef | None:
    """Weighted random pick from a biome's event pool."""
    pool = _by_biome.get(biome_id, [])
    if not pool: return None
    weights = [ev.weight for ev in pool]
    return random.choices(pool, weights=weights)[0]


# ══════════════════════════════════════════════════════════════
#  Effect / Risk executors (G6.4: string-driven)
# ══════════════════════════════════════════════════════════════

def execute_effect(effect: str, player, monsters: list, game_map) -> str:
    """Execute a reward effect. Returns a brief result message."""
    if effect == "none":
        return ""
    parts = effect.split(":")
    kind = parts[0]
    try:
        if kind == "buff":
            name, stacks = parts[1], int(parts[2])
            from src.systems.buff_system import apply_buff
            apply_buff(player, name, stacks)
            return f"获得了 {stacks} 层 {name}"
        elif kind == "relic":
            count = int(parts[1])
            from src.systems.relic_system import try_grant_random_relic
            msgs = []
            for _ in range(count):
                m = try_grant_random_relic(player, 1.0)
                if m: msgs.append(m)
            return "获得了圣物: " + ", ".join(msgs) if msgs else "圣物获取失败"
        elif kind == "equipment":
            rarity_str = parts[1]  # "rare"
            from src.entities.item import generate_random_item, Rarity
            item = generate_random_item()
            tries = 0
            target = {"rare": Rarity.RARE, "epic": Rarity.EPIC, "legendary": Rarity.LEGENDARY}
            tgt = target.get(rarity_str, Rarity.RARE)
            while item and tries < 10:
                if item.rarity.value >= tgt.value:
                    break
                item = generate_random_item()
                tries += 1
            if item and player.inventory.add(item, player):
                return f"获得了 {item.name}"
            return "装备获取失败——背包已满"
        elif kind == "skill_level":
            levels = int(parts[1])
            active = player.skills.active_skills
            if not active: return "没有可升级的技能"
            sk = random.choice(active)
            for _ in range(levels):
                if sk.level < sk.max_level:
                    sk._on_level_up(); sk.level += 1
            return f"{sk.name} 提升了 {levels} 级"
        elif kind == "heal":
            pct = int(parts[1])
            amt = max(1, player.combat.max_hp * pct // 100)
            player.combat.heal(amt)
            return f"恢复了 {amt} HP"
    except Exception as e:
        return f"效果执行失败: {e}"
    return ""


def execute_risk(risk: str, player, monsters: list, game_map) -> str:
    """Execute a risk cost. Returns a brief result message."""
    if risk == "none":
        return ""
    parts = risk.split(":")
    kind = parts[0]
    try:
        if kind == "spawn":
            enemy_id, count = parts[1], int(parts[2])
            from src.entities.monster import spawn_monster
            px, py = player.entity.position.x, player.entity.position.y
            spawned = 0
            for _ in range(count * 3):
                if spawned >= count: break
                off_x, off_y = random.randint(-4, 4), random.randint(-4, 4)
                tx = int((px + off_x * 32) // 32)
                ty = int((py + off_y * 32) // 32)
                if game_map and game_map.is_walkable(tx, ty):
                    sx, sy = game_map.tile_to_pixel(tx, ty)
                    m = spawn_monster(sx, sy, enemy_id)
                    monsters.append(m)
                    spawned += 1
            return f"出现了 {spawned} 只 {enemy_id}" if spawned else ""
        elif kind == "hp_loss":
            pct = int(parts[1])
            loss = max(1, player.combat.current_hp * pct // 100)
            player.combat.take_damage(loss)
            return f"失去了 {loss} HP"
        elif kind == "debuff":
            name, stacks = parts[1], int(parts[2])
            from src.systems.buff_system import apply_buff
            apply_buff(player, name, stacks)
            return f"受到 {stacks} 层 {name}"
        elif kind == "confuse":
            duration = int(parts[1])
            return f"困惑 {duration}s"
    except Exception as e:
        return f"风险执行失败: {e}"
    return ""
