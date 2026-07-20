"""
G6 sync: Replay Recorder + Player + StateHash (C++ parity)
"""
import json, math, os, sys, time
from dataclasses import dataclass, field
from typing import Optional

# ── Action ID mapping (must match InputMap defaults) ──
ACTION_NAMES = ["move_up","move_down","move_left","move_right",
    "attack","pickup","inventory","skill_1","skill_2",
    "skill_3","skill_4","descend","confirm","cancel","fullscreen"]

def _action_id(name: str) -> int:
    try: return ACTION_NAMES.index(name)
    except ValueError: return -1

def _action_name(aid: int) -> str:
    if 0 <= aid < len(ACTION_NAMES): return ACTION_NAMES[aid]
    return "?"


@dataclass
class ReplayFile:
    version: int = 1
    game_version: str = "0.9.0"
    seed: int = 0
    mods: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    hash_chain: list[int] = field(default_factory=list)


# ── Recorder ──
class ReplayRecorder:
    def __init__(self):
        self._active = False; self._frame = 0; self._file = ReplayFile()

    def start(self, seed: int, mods: list = None):
        self._active = True; self._frame = 0
        self._file = ReplayFile(seed=seed, mods=mods or [])

    def tick(self):
        if self._active: self._frame += 1

    def record(self, action_name: str):
        if not self._active: return
        aid = _action_id(action_name)
        if aid < 0: return
        self._file.actions.append({"f": self._frame, "a": aid})

    def record_hash(self, h: int):
        if self._active: self._file.hash_chain.append(h)

    @property
    def is_active(self): return self._active

    @property
    def file(self) -> ReplayFile: return self._file

    def save(self, path: str):
        data = {"version":self._file.version,"game_version":self._file.game_version,
            "seed":self._file.seed,"mods":self._file.mods,
            "actions":self._file.actions,"hash_chain":self._file.hash_chain}
        with open(path, "w") as f: json.dump(data, f, indent=2)


# ── Player ──
class ReplayPlayer:
    def __init__(self):
        self._active = False; self._frame = 0; self._cursor = 0; self._file = ReplayFile()

    def load(self, path: str) -> bool:
        try:
            with open(path) as f: data = json.load(f)
            self._file.version = data.get("version", 1)
            self._file.game_version = data.get("game_version", "")
            self._file.seed = data.get("seed", 0)
            self._file.mods = data.get("mods", [])
            self._file.actions = data.get("actions", [])
            self._file.hash_chain = data.get("hash_chain", [])
            return True
        except Exception: return False

    def start(self):
        self._active = True; self._frame = 0; self._cursor = 0

    def tick(self):
        if self._active: self._frame += 1

    @property
    def is_active(self): return self._active

    def is_finished(self) -> bool:
        if not self._active: return False
        if self._cursor >= len(self._file.actions):
            if not self._file.actions: return self._frame > 60
            return self._frame > self._file.actions[-1]["f"] + 10
        return False

    def is_action_just_pressed(self, action_name: str) -> bool:
        if not self._active: return False
        aid = _action_id(action_name)
        if aid < 0: return False
        while self._cursor < len(self._file.actions):
            a = self._file.actions[self._cursor]
            if a["f"] > self._frame: return False
            if a["f"] == self._frame and a["a"] == aid:
                self._cursor += 1; return True
            self._cursor += 1
        return False

    @property
    def replay_seed(self) -> int: return self._file.seed


# ── State Hash ──
def _mix(h: int, v: int) -> int:
    h ^= v + 0x9e3779b97f4a7c15 + (h << 6) + (h >> 2)
    return h & 0xFFFFFFFFFFFFFFFF


def compute_state_hash(prev: int, player, floor: int, monsters: list) -> int:
    h = prev
    h = _mix(h, player.combat.current_hp); h = _mix(h, player.combat.max_hp)
    h = _mix(h, player.level)
    h = _mix(h, int(player.entity.position.x)); h = _mix(h, int(player.entity.position.y))
    h = _mix(h, floor)
    recs = []
    for m in monsters:
        if not m.combat.is_alive: continue
        recs.append(((int)(m.combat.monster_type) if hasattr(m.combat,'monster_type') else 0,
                     m.combat.current_hp, int(m.entity.position.x), int(m.entity.position.y)))
    recs.sort()
    for r in recs:
        h = _mix(h, r[0]); h = _mix(h, r[1]); h = _mix(h, r[2]); h = _mix(h, r[3])
    h = _mix(h, len(recs))
    return h


def verify_hash_chain(expected: list, actual: list) -> bool:
    if len(expected) != len(actual): return False
    for e, a in zip(expected, actual):
        if e != a: return False
    return True
