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
    """G6.5: delegate to encounter.py unified effect resolver."""
    from src.game.encounter import execute_effect as _exec
    return _exec(effect, player, monsters, game_map)


def execute_risk(risk: str, player, monsters: list, game_map) -> str:
    """G6.5: delegate to encounter.py unified risk resolver."""
    from src.game.encounter import execute_risk as _exec
    return _exec(risk, player, monsters, game_map)
