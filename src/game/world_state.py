"""
D4/G6.7: WorldState — run-layer flag system (RunFlag = per-run state).

Persistent binary state driving NPC dialogue / boss behavior / ending eval.
RunFlag replaces the old WorldFlag name; WorldFlag kept as alias.
"""

from collections import defaultdict


class RunFlag:
    """G6.7: per-run state flags (was WorldFlag)."""
    # Boss kills
    Boss1_Defeated = 5
    Boss2_Defeated = 10
    Boss3_Defeated = 15
    All_Boss_Defeated = 100

    # Events
    Accepted_Curse = 200
    Blood_Ritual = 201
    Merchant_Killed = 202

    # NPC rescues
    Saved_Prisoner = 300
    Saved_Priest = 301
    Met_Solas = 302
    Met_Watcher = 303

    # Ending
    True_Ending_Ready = 400

    # G6.6: secret discoveries
    Vault_Discovered = 500
    Geode_Collected = 501
    Void_Memory_Seen = 502


# Backward compat alias
WorldFlag = RunFlag


class WorldState:
    """Per-run state manager."""

    def __init__(self):
        self._flags: set[int] = set()
        self._counters: dict[str, int] = defaultdict(int)

    def set(self, flag: int):
        self._flags.add(flag)

    def has(self, flag: int) -> bool:
        return flag in self._flags

    def clear(self, flag: int):
        self._flags.discard(flag)

    def counter(self, key: str) -> int:
        return self._counters.get(key, 0)

    def inc_counter(self, key: str, delta: int = 1):
        self._counters[key] = self.counter(key) + delta

    def reset(self):
        self._flags.clear()
        self._counters.clear()

    def get_flags(self):
        return set(self._flags)
