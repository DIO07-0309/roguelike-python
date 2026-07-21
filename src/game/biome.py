"""
G6.1: Biome system — floor-based visual/content theming.

Data-driven via resources/biomes.json.
Each biome defines a tile palette, enemy pool, boss, and narrative hook.
Boss floors (5/10/15) inherit the previous biome's visual style.
"""

import json
import os
import sys
from dataclasses import dataclass


@dataclass
class BiomeDef:
    """Immutable biome definition loaded from JSON."""
    id: str
    name: str
    name_en: str
    floor_range: list            # [start, end] inclusive
    tile_palette: dict           # {key: (r,g,b)} for tile_renderer
    enemy_pool: list[str]
    enemy_weights: list[float]
    boss_id: str
    floor_narrative_hook: str
    bgm: str                     # "prison" | "volcano" | "abyss" | "boss"
    ambient: dict                # particle config: count/color/size/speed/rise/life

    def contains_floor(self, floor: int) -> bool:
        return self.floor_range[0] <= floor <= self.floor_range[1]


# ── Registry ─────────────────────────────────────────────────

_biomes: list[BiomeDef] = []
_floor_to_biome: dict[int, BiomeDef] = {}


def _resolve_path(path: str) -> str:
    """Resolve resource path (supports PyInstaller)."""
    if os.path.exists(path):
        return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_biome_defs(json_path: str = "resources/biomes.json") -> bool:
    """Load biomes.json into registry. Call once at startup."""
    global _biomes, _floor_to_biome
    try:
        with open(_resolve_path(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Biome] Failed to load {json_path}: {e}")
        return False

    _biomes = []
    _floor_to_biome = {}
    for obj in data:
        ambient_raw = obj.get("ambient", {})
        ambient = {
            "count": ambient_raw.get("count", 0),
            "color": tuple(ambient_raw.get("color", [160, 140, 220])),
            "size_min": ambient_raw.get("size_min", 1.0),
            "size_max": ambient_raw.get("size_max", 3.0),
            "speed": ambient_raw.get("speed", 10),
            "rise": ambient_raw.get("rise", True),
            "life_min": ambient_raw.get("life_min", 2.0),
            "life_max": ambient_raw.get("life_max", 6.0),
        }
        b = BiomeDef(
            id=obj["id"], name=obj["name"],
            name_en=obj.get("name_en", ""),
            floor_range=obj["floor_range"],
            tile_palette={k: tuple(v) for k, v in obj.get("tile_palette", {}).items()},
            enemy_pool=obj.get("enemy_pool", []),
            enemy_weights=obj.get("enemy_weights", []),
            boss_id=obj.get("boss_id", ""),
            floor_narrative_hook=obj.get("floor_narrative_hook", ""),
            bgm=obj.get("bgm", ""),
            ambient=ambient,
        )
        _biomes.append(b)
        for f in range(b.floor_range[0], b.floor_range[1] + 1):
            _floor_to_biome[f] = b

    print(f"[Biome] Loaded {len(_biomes)} biomes (floors 1-15 mapped)")
    return True


def get_biome_for_floor(floor: int) -> BiomeDef | None:
    """Return the biome active for a given floor (1-based)."""
    return _floor_to_biome.get(floor)


def get_all_biomes() -> list[BiomeDef]:
    return list(_biomes)
