"""
G6.7: MetaState — cross-run persistent flags (MetaFlag).

Stored in saves/meta_save.json. Survives individual runs.
Unlocks: classes, NPCs, difficulty tiers, secret completions.
"""

import json, os, sys


class MetaFlag:
    """G6.7: cross-run persistent state flags."""
    Necromancer_Unlocked = 1000
    Difficulty_Hard_Unlocked = 1001
    NPC_Solas_Available = 1002
    NPC_Forge_Master_Available = 1003
    All_Secrets_Found = 1004


# ── Module-level state ───────────────────────────────────────

_meta_flags: set = set()
_loaded: bool = False


def _resolve(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def load_meta_state(json_path: str = "saves/meta_save.json") -> bool:
    """Load meta flags from disk. Call once at startup."""
    global _meta_flags, _loaded
    try:
        with open(_resolve(json_path), "r", encoding="utf-8") as f:
            data = json.load(f)
        _meta_flags = set(data.get("flags", []))
    except Exception:
        _meta_flags = set()
    _loaded = True
    print(f"[Meta] Loaded {len(_meta_flags)} meta flags")
    return True


def save_meta_state(json_path: str = "saves/meta_save.json"):
    """Persist meta flags to disk."""
    try:
        data = {"flags": list(_meta_flags)}
        with open(_resolve(json_path), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[Meta] Failed to save: {e}")


def has_meta_flag(flag: int) -> bool:
    return flag in _meta_flags


def set_meta_flag(flag: int):
    _meta_flags.add(flag)
    save_meta_state()


def get_meta_flags() -> set[int]:
    return set(_meta_flags)
