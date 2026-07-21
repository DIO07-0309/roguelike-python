"""
G6.3: Biome Hazard system — environmental gameplay.

Hazards are attached to landmark rooms and affect the player/monsters
during combat via per-frame tick effects.

Types: slow_zone, burn_tick, confuse, deflect_projectiles
"""

import json, os, sys, random
from dataclasses import dataclass, field


@dataclass
class HazardDef:
    """Immutable hazard definition loaded from JSON."""
    id: str
    biome: str
    landmark_id: str              # which landmark room this hazard occupies
    effect: str                   # "slow_zone" | "burn_tick" | "confuse" | "deflect"
    interval: float               # seconds between effect ticks
    damage: int = 0               # per-tick damage for burn_tick
    slow_factor: float = 1.0      # speed multiplier for slow_zone (0.7 = 70% speed)
    param: float = 0.0            # generic param (deflect chance, etc.)
    message: str = ""             # first-time discovery text


# ── Registry ─────────────────────────────────────────────────

_hazards: list[HazardDef] = []
_by_landmark: dict[str, list[HazardDef]] = {}


def _resolve(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_hazard_defs(json_path: str = "resources/hazards.json") -> bool:
    """Load all hazard defs from JSON. Call once at startup."""
    global _hazards, _by_landmark
    try:
        with open(_resolve(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Hazard] Failed to load {json_path}: {e}")
        return False

    _hazards = []
    _by_landmark = {}
    for obj in data:
        h = HazardDef(
            id=obj["id"], biome=obj["biome"], landmark_id=obj["landmark_id"],
            effect=obj["effect"], interval=obj.get("interval", 3.0),
            damage=obj.get("damage", 0), slow_factor=obj.get("slow_factor", 1.0),
            param=obj.get("param", 0.0), message=obj.get("message", ""),
        )
        _hazards.append(h)
        _by_landmark.setdefault(h.landmark_id, []).append(h)

    print(f"[Hazard] Loaded {len(_hazards)} hazards across {len(_by_landmark)} landmarks")
    return True


def get_hazards_for_landmark(landmark_id: str) -> list[HazardDef]:
    return _by_landmark.get(landmark_id, [])


def get_all_hazards() -> list[HazardDef]:
    return list(_hazards)
