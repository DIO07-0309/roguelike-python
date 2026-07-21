"""
G6.2: Landmark system — per-biome room definitions (data-driven).

Each biome has 3-4 landmark rooms that convey environmental storytelling.
Landmarks extend SpecialRoom with biome_id + landmark_id + visuals.
"""

import json
import os
import sys
from dataclasses import dataclass


@dataclass
class LandmarkDef:
    """Immutable landmark definition loaded from JSON."""
    id: str
    biome: str
    weight: int
    tile_color: tuple          # (r,g,b) floor color
    icon: str                  # single emoji/symbol character
    message: str               # room narrative line (on discovery)
    discovery_msg: str         # toast when first entering the room


# ── Registry ─────────────────────────────────────────────────

_landmarks: list[LandmarkDef] = []
_by_biome: dict[str, list[LandmarkDef]] = {}


def _resolve_path(path: str) -> str:
    if os.path.exists(path):
        return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_landmark_defs(json_path: str = "resources/landmarks.json") -> bool:
    """Load landmarks.json into registry. Call once at startup."""
    global _landmarks, _by_biome
    try:
        with open(_resolve_path(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Landmark] Failed to load {json_path}: {e}")
        return False

    _landmarks = []
    _by_biome = {}
    for obj in data:
        lm = LandmarkDef(
            id=obj["id"],
            biome=obj["biome"],
            weight=obj.get("weight", 20),
            tile_color=tuple(obj.get("tile_color", [60, 40, 40])),
            icon=obj.get("icon", "?"),
            message=obj.get("message", ""),
            discovery_msg=obj.get("discovery_msg", ""),
        )
        _landmarks.append(lm)
        _by_biome.setdefault(lm.biome, []).append(lm)

    total = len(_landmarks)
    print(f"[Landmark] Loaded {total} landmarks across {len(_by_biome)} biomes")
    return True


def get_landmarks_for_biome(biome_id: str) -> list[LandmarkDef]:
    """Return all landmarks for a biome."""
    return _by_biome.get(biome_id, [])


def get_landmark_by_id(landmark_id: str) -> LandmarkDef | None:
    for lm in _landmarks:
        if lm.id == landmark_id:
            return lm
    return None


def get_all_landmarks() -> list[LandmarkDef]:
    return list(_landmarks)
