"""
G6.5: Encounter Framework — unified dialog/event/trade/npc data model.

EncounterDef is the generalization of BiomeEvent: multi-node dialogue trees,
trade nodes, and string-driven effect/risk dispatch. All encounter types
(event, npc, trader, quest_giver) share the same JSON format and runtime state.
"""

import json, os, sys, random
from dataclasses import dataclass, field


@dataclass
class EncounterChoice:
    text: str
    next: str = "end"
    effect: str = "none"       # colon-delimited reward DSL
    risk: str = "none"         # colon-delimited cost DSL


@dataclass
class EncounterNode:
    id: str
    text: str = ""
    type: str = "dialogue"     # "dialogue" | "trade"
    trade_items: list = field(default_factory=list)
    trade_cost: str = ""
    choices: list = field(default_factory=list)


@dataclass
class EncounterDef:
    id: str
    type: str                  # "event" | "npc" | "trader" | "quest_giver"
    name: str
    biome: str
    trigger: str               # "floor_enter" | "room_enter" | "talk"
    room: str                  # "" = any room, "broken_cell" = specific
    repeatable: bool
    narrative: str
    dialogue: list[EncounterNode] = field(default_factory=list)


# ── Registry ─────────────────────────────────────────────────

_encounters: list[EncounterDef] = []
_by_id: dict[str, EncounterDef] = {}
_by_biome: dict[str, list[EncounterDef]] = {}


def _resolve(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_encounter_defs(json_path: str = "resources/encounters.json") -> bool:
    global _encounters, _by_id, _by_biome
    try:
        with open(_resolve(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Encounter] Failed to load {json_path}: {e}")
        return False
    _encounters = []; _by_id = {}; _by_biome = {}
    for obj in data:
        nodes = []
        for n in obj.get("dialogue", []):
            choices = [EncounterChoice(**c) for c in n.get("choices", [])]
            nodes.append(EncounterNode(
                id=n["id"], text=n.get("text", ""),
                type=n.get("type", "dialogue"),
                trade_items=n.get("trade_items", []),
                trade_cost=n.get("trade_cost", ""),
                choices=choices,
            ))
        enc = EncounterDef(
            id=obj["id"], type=obj["type"],
            name=obj["name"], biome=obj["biome"],
            trigger=obj.get("trigger", "floor_enter"),
            room=obj.get("room", ""),
            repeatable=obj.get("repeatable", False),
            narrative=obj.get("narrative", ""),
            dialogue=nodes,
        )
        _encounters.append(enc)
        _by_id[enc.id] = enc
        _by_biome.setdefault(enc.biome, []).append(enc)

    print(f"[Encounter] Loaded {len(_encounters)} encounters across {len(_by_biome)} biomes")
    return True


def get_encounter(eid: str) -> EncounterDef | None:
    return _by_id.get(eid)


def pick_encounter_for_biome(biome_id: str) -> EncounterDef | None:
    """Weighted random pick (currently uniform)."""
    pool = _by_biome.get(biome_id, [])
    if not pool: return None
    return random.choice(pool)


def get_encounters_for_biome(biome_id: str) -> list[EncounterDef]:
    return _by_biome.get(biome_id, [])


# ══════════════════════════════════════════════════════════════
#  Unified Effect / Risk executors (from biome_event.py, expanded)
# ══════════════════════════════════════════════════════════════

def execute_effect(effect: str, player, monsters: list, game_map) -> str:
    """Execute a reward effect. Returns a brief result message."""
    if effect in ("", "none"): return ""
    parts = effect.split(":") if ":" in effect else [effect]
    kind = parts[0]
    try:
        if kind == "buff":
            name, stacks = parts[1], int(parts[2]) if len(parts) > 2 else 1
            from src.systems.buff_system import apply_buff
            apply_buff(player, name, stacks)
            return f"获得了 {stacks} 层 {name}"
        elif kind == "relic":
            count = int(parts[1]) if len(parts) > 1 else 1
            from src.systems.relic_system import try_grant_random_relic
            msgs = []
            for _ in range(count):
                m = try_grant_random_relic(player, 1.0)
                if m: msgs.append(m)
            return "获得了圣物" if msgs else ""
        elif kind == "equipment":
            rarity_str = parts[1] if len(parts) > 1 else "rare"
            from src.entities.item import generate_random_item, Rarity
            target_map = {"rare": Rarity.RARE, "epic": Rarity.EPIC, "legendary": Rarity.LEGENDARY}
            tgt = target_map.get(rarity_str, Rarity.RARE)
            item = None
            for _ in range(15):
                candidate = generate_random_item()
                if candidate and candidate.rarity.value >= tgt.value:
                    item = candidate; break
            if not item:
                item = generate_random_item()
            if item and player.inventory.add(item, player):
                return f"获得了 {item.name}"
            return "背包已满"
        elif kind == "skill_level":
            levels = int(parts[1]) if len(parts) > 1 else 1
            active = player.skills.active_skills
            if not active: return ""
            sk = random.choice(active)
            gained = 0
            for _ in range(levels):
                if sk.level < sk.max_level:
                    sk._on_level_up(); sk.level += 1; gained += 1
            return f"{sk.name} +{gained}级" if gained else ""
        elif kind == "heal":
            pct = int(parts[1]) if len(parts) > 1 else 30
            amt = max(1, player.combat.max_hp * pct // 100)
            player.combat.heal(amt)
            return f"+{amt}HP"
        elif kind == "relic_from_pool":
            from src.systems.relic_system import try_grant_random_relic
            m = try_grant_random_relic(player, 1.0)
            return m if m else ""
    except Exception as e:
        return f""
    return ""


def execute_risk(risk: str, player, monsters: list, game_map) -> str:
    """Execute a risk cost. Returns a brief result message."""
    if risk in ("", "none"): return ""
    parts = risk.split(":") if ":" in risk else [risk]
    kind = parts[0]
    try:
        if kind == "spawn":
            enemy_id, count = parts[1], int(parts[2]) if len(parts) > 2 else 1
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
                    monsters.append(m); spawned += 1
            return f"敌人出现了！" if spawned else ""
        elif kind == "hp_loss":
            pct = int(parts[1]) if len(parts) > 1 else 10
            loss = max(1, player.combat.current_hp * pct // 100)
            player.combat.take_damage(loss)
            return f"-{loss}HP"
        elif kind == "debuff":
            name, stacks = parts[1], int(parts[2]) if len(parts) > 2 else 1
            from src.systems.buff_system import apply_buff
            apply_buff(player, name, stacks)
            return f"受到 {name}"
        elif kind == "confuse":
            return "困惑！"
    except Exception:
        return ""
    return ""


def execute_trade(trade_items: list, trade_cost: str, player) -> str:
    """Execute a trade: pay cost → receive items."""
    if trade_cost:
        parts = trade_cost.split(":")
        if parts[0] == "hp":
            pct = int(parts[1]) if len(parts) > 1 else 20
            loss = max(1, player.combat.current_hp * pct // 100)
            player.combat.take_damage(loss)
    received = []
    for item_str in trade_items:
        parts = item_str.split(":") if ":" in item_str else [item_str]
        kind = parts[0]
        if kind == "equipment":
            rarity_str = parts[1] if len(parts) > 1 else "rare"
            from src.entities.item import generate_random_item, Rarity
            target_map = {"rare": Rarity.RARE, "epic": Rarity.EPIC, "legendary": Rarity.LEGENDARY}
            tgt = target_map.get(rarity_str, Rarity.RARE)
            item = None
            for _ in range(10):
                c = generate_random_item()
                if c and c.rarity.value >= tgt.value:
                    item = c; break
            if not item: item = generate_random_item()
            if item and player.inventory.add(item, player):
                received.append(item.base_name)
        elif kind == "potion":
            from src.entities.item import ConsumableItem, Rarity
            pot = ConsumableItem("交易药水", Rarity.RARE, "heal", 40)
            if player.inventory.add(pot, player):
                received.append("药水")
        elif kind == "relic":
            from src.systems.relic_system import try_grant_random_relic
            msg = try_grant_random_relic(player, 1.0)
            if msg: received.append("圣物")
    return "交易完成" if received else "交易失败——背包已满"
