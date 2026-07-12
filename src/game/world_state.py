"""
D4: WorldState — 世界状态标志位系统

持久化二进制状态，驱动 NPC 对话/Boss 行为/结局判定。
与 C++ world_state.h/.cpp 一致。
"""

from collections import defaultdict


class WorldFlag:
    """世界状态标志位枚举。"""
    # Boss 击杀
    Boss1_Defeated = 5
    Boss2_Defeated = 10
    Boss3_Defeated = 15
    All_Boss_Defeated = 100

    # 事件相关
    Accepted_Curse = 200
    Blood_Ritual = 201
    Merchant_Killed = 202

    # NPC 救援
    Saved_Prisoner = 300    # F2
    Saved_Priest = 301      # F7
    Met_Solas = 302          # F9
    Met_Watcher = 303        # F14

    # 结局
    True_Ending_Ready = 400


class WorldState:
    """世界状态管理器。"""

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
